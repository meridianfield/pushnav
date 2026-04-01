// Copyright (C) 2026 Arun Venkataswamy
//
// This file is part of PushNav.
//
// PushNav is free software: you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// PushNav is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
// General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with PushNav. If not, see <https://www.gnu.org/licenses/>.

// UVCController.swift — IOKit USB device discovery + UVC control transfers.
//
// Ported from ~/Devel/Learning/webcam/camera_viewer.swift (lines 95–382).
// On macOS 12+, ControlRequest() works WITHOUT USBInterfaceOpen, coexisting
// with UVCAssistant which holds the interface exclusively.

import Foundation
import IOKit
import IOKit.usb

// MARK: - IOKit USB UUID Constants
// These C macros aren't importable in Swift; define them manually.

private let kIOUSBDeviceUserClientTypeID_UUID = CFUUIDGetConstantUUIDWithBytes(
    kCFAllocatorDefault,
    0x9d, 0xc7, 0xb7, 0x80, 0x9e, 0xc0, 0x11, 0xD4,
    0xa5, 0x4f, 0x00, 0x0a, 0x27, 0x05, 0x28, 0x61)!

private let kIOCFPlugInInterfaceID_UUID = CFUUIDGetConstantUUIDWithBytes(
    kCFAllocatorDefault,
    0xC2, 0x44, 0xE8, 0x58, 0x10, 0x9C, 0x11, 0xD4,
    0x91, 0xD4, 0x00, 0x50, 0xE4, 0xC6, 0x42, 0x6F)!

private let kIOUSBDeviceInterfaceID_UUID = CFUUIDGetConstantUUIDWithBytes(
    kCFAllocatorDefault,
    0x5c, 0x81, 0x87, 0xd0, 0x9e, 0xf3, 0x11, 0xD4,
    0x8b, 0x45, 0x00, 0x0a, 0x27, 0x05, 0x28, 0x61)!

private let kIOUSBInterfaceUserClientTypeID_UUID = CFUUIDGetConstantUUIDWithBytes(
    kCFAllocatorDefault,
    0x2d, 0x97, 0x86, 0xc6, 0x9e, 0xf3, 0x11, 0xD4,
    0xad, 0x51, 0x00, 0x0a, 0x27, 0x05, 0x28, 0x61)!

private let kIOUSBInterfaceInterfaceID_UUID = CFUUIDGetConstantUUIDWithBytes(
    kCFAllocatorDefault,
    0x73, 0xc9, 0x7a, 0xe8, 0x9e, 0xf3, 0x11, 0xD4,
    0xb1, 0xd0, 0x00, 0x0a, 0x27, 0x05, 0x28, 0x61)!

// MARK: - UVC Constants

// UVC request codes
private let UVC_SET_CUR: UInt8 = 0x01
private let UVC_GET_CUR: UInt8 = 0x81
private let UVC_GET_MIN: UInt8 = 0x82
private let UVC_GET_MAX: UInt8 = 0x83
private let UVC_GET_RES: UInt8 = 0x84
private let UVC_GET_INFO: UInt8 = 0x86
private let UVC_GET_DEF: UInt8 = 0x87

// Camera Terminal selectors
private let CT_AE_MODE: UInt8 = 0x02
private let CT_EXPOSURE_TIME_ABS: UInt8 = 0x04

// Processing Unit selectors
private let PU_GAIN: UInt8 = 0x04

// Auto-Exposure Mode bitmap values
private let AE_MODE_MANUAL: UInt8 = 0x01
private let AE_MODE_AUTO: UInt8 = 0x02

// openaicam VID/PID
let OPENAICAM_VID: Int = 0x32E6
let OPENAICAM_PID: Int = 0x9251

// MARK: - USB Request Type Builder

private func usbMakeBmRequestType(direction: Int, type: Int, recipient: Int) -> UInt8 {
    return UInt8((direction & 0x01) << 7) |
           UInt8((type & 0x03) << 5) |
           UInt8(recipient & 0x1F)
}

private let kUSBIn = 1
private let kUSBOut = 0
private let kUSBClass = 1
private let kUSBInterface = 1

// MARK: - UVCController

typealias USBInterfacePtr = UnsafeMutablePointer<UnsafeMutablePointer<IOUSBInterfaceInterface190>>

class UVCController {
    let interface: USBInterfacePtr
    let interfaceNumber: UInt16

    // Camera Terminal ID and Processing Unit ID (from UVC descriptors)
    let cameraTerminalID: UInt8 = 1
    let processingUnitID: UInt8 = 2

    struct ControlRange {
        var min: Int = 0
        var max: Int = 0
        var cur: Int = 0
        var def: Int = 0
        var res: Int = 1
        var capable: Bool = false
    }

    var exposureTimeRange = ControlRange()
    var gainRange = ControlRange()

    init?(vendorID: Int, productID: Int) {
        // Find the USB device by VID/PID
        let matchingDict = IOServiceMatching(kIOUSBDeviceClassName) as NSMutableDictionary
        matchingDict[kUSBVendorID] = vendorID
        matchingDict[kUSBProductID] = productID

        let device = IOServiceGetMatchingService(kIOMainPortDefault, matchingDict)
        guard device != IO_OBJECT_NULL else {
            fputs("ERROR: openaicam not found (VID=0x\(String(vendorID, radix: 16)), PID=0x\(String(productID, radix: 16)))\n", stderr)
            return nil
        }
        defer { IOObjectRelease(device) }

        // Find Video Control interface (class=14, subclass=1) among children
        var childIterator: io_iterator_t = IO_OBJECT_NULL
        IORegistryEntryGetChildIterator(device, kIOServicePlane, &childIterator)
        defer { IOObjectRelease(childIterator) }

        var vcInterface: io_service_t = IO_OBJECT_NULL
        var ifaceNum: UInt16 = 0
        var child = IOIteratorNext(childIterator)
        while child != IO_OBJECT_NULL {
            var props: Unmanaged<CFMutableDictionary>?
            IORegistryEntryCreateCFProperties(child, &props, kCFAllocatorDefault, 0)
            if let dict = props?.takeRetainedValue() as? [String: Any] {
                let ifClass = dict["bInterfaceClass"] as? Int ?? -1
                let ifSubClass = dict["bInterfaceSubClass"] as? Int ?? -1
                if ifClass == 14 && ifSubClass == 1 {
                    vcInterface = child
                    ifaceNum = UInt16(dict["bInterfaceNumber"] as? Int ?? 0)
                    break
                }
            }
            IOObjectRelease(child)
            child = IOIteratorNext(childIterator)
        }

        guard vcInterface != IO_OBJECT_NULL else {
            fputs("ERROR: Video Control interface not found\n", stderr)
            return nil
        }
        defer { IOObjectRelease(vcInterface) }

        self.interfaceNumber = ifaceNum

        // Create plugin interface for the VC interface
        var score: Int32 = 0
        var pluginInterface: UnsafeMutablePointer<UnsafeMutablePointer<IOCFPlugInInterface>?>?

        let kr = IOCreatePlugInInterfaceForService(
            vcInterface,
            kIOUSBInterfaceUserClientTypeID_UUID,
            kIOCFPlugInInterfaceID_UUID,
            &pluginInterface,
            &score
        )

        guard kr == KERN_SUCCESS, let plugin = pluginInterface?.pointee?.pointee else {
            fputs("ERROR: Failed to create plugin interface: \(kr)\n", stderr)
            return nil
        }

        // Query for IOUSBInterfaceInterface190
        var ifacePtr: USBInterfacePtr?
        let uuidBytes = CFUUIDGetUUIDBytes(kIOUSBInterfaceInterfaceID_UUID)
        let result = withUnsafeMutablePointer(to: &ifacePtr) { ptr in
            plugin.QueryInterface(
                pluginInterface,
                uuidBytes,
                UnsafeMutableRawPointer(ptr).assumingMemoryBound(to: LPVOID?.self)
            )
        }

        _ = plugin.Release(pluginInterface)

        guard result == S_OK, let iface = ifacePtr else {
            fputs("ERROR: Failed to get IOUSBInterfaceInterface190\n", stderr)
            return nil
        }

        self.interface = iface
        print("UVC controller initialized (interface \(interfaceNumber))")

        // Probe control ranges
        probeControls()
    }

    deinit {
        _ = interface.pointee.pointee.Release(interface)
    }

    // MARK: - Low-level USB control transfer

    func sendRequest(direction: Int, request: UInt8, selector: UInt8,
                     unitID: UInt8, size: Int, value: inout Int) -> Bool {
        let bmRequestType = usbMakeBmRequestType(
            direction: direction, type: kUSBClass, recipient: kUSBInterface)

        return withUnsafeMutablePointer(to: &value) { ptr in
            var req = IOUSBDevRequest(
                bmRequestType: bmRequestType,
                bRequest: request,
                wValue: UInt16(selector) << 8,
                wIndex: (UInt16(unitID) << 8) | UInt16(interfaceNumber),
                wLength: UInt16(size),
                pData: ptr,
                wLenDone: 0
            )
            let kr = interface.pointee.pointee.ControlRequest(interface, 0, &req)
            return kr == kIOReturnSuccess
        }
    }

    func getValue(request: UInt8, selector: UInt8, unitID: UInt8, size: Int) -> Int? {
        var value = 0
        if sendRequest(direction: kUSBIn, request: request, selector: selector,
                       unitID: unitID, size: size, value: &value) {
            // Sign-extend for 2-byte signed values
            if size == 2 {
                let raw = UInt16(truncatingIfNeeded: value)
                value = Int(Int16(bitPattern: raw))
            }
            return value
        }
        return nil
    }

    func setValue(selector: UInt8, unitID: UInt8, size: Int, value: Int) -> Bool {
        var val = value
        return sendRequest(direction: kUSBOut, request: UVC_SET_CUR, selector: selector,
                           unitID: unitID, size: size, value: &val)
    }

    // MARK: - Control range probing

    func probeRange(selector: UInt8, unitID: UInt8, size: Int) -> ControlRange {
        var range = ControlRange()

        // Check if control is capable (GET_INFO)
        if let info = getValue(request: UVC_GET_INFO, selector: selector, unitID: unitID, size: 1) {
            range.capable = info != 0
        }
        guard range.capable else { return range }

        if let min = getValue(request: UVC_GET_MIN, selector: selector, unitID: unitID, size: size) {
            range.min = min
        }
        if let max = getValue(request: UVC_GET_MAX, selector: selector, unitID: unitID, size: size) {
            range.max = max
        }
        if let cur = getValue(request: UVC_GET_CUR, selector: selector, unitID: unitID, size: size) {
            range.cur = cur
        }
        if let def = getValue(request: UVC_GET_DEF, selector: selector, unitID: unitID, size: size) {
            range.def = def
        }
        if let res = getValue(request: UVC_GET_RES, selector: selector, unitID: unitID, size: size) {
            range.res = Swift.max(res, 1)
        }

        if range.min > range.max { range.capable = false }

        return range
    }

    func probeControls() {
        print("Probing UVC controls...")

        exposureTimeRange = probeRange(selector: CT_EXPOSURE_TIME_ABS, unitID: cameraTerminalID, size: 4)
        if exposureTimeRange.capable {
            print("  Exposure Time: \(exposureTimeRange.min)...\(exposureTimeRange.max) (cur=\(exposureTimeRange.cur), def=\(exposureTimeRange.def), res=\(exposureTimeRange.res))")
        }

        gainRange = probeRange(selector: PU_GAIN, unitID: processingUnitID, size: 2)
        if gainRange.capable {
            print("  Gain: \(gainRange.min)...\(gainRange.max) (cur=\(gainRange.cur), def=\(gainRange.def), res=\(gainRange.res))")
        }

        print("Control probing complete.")
    }

    // MARK: - High-level control accessors

    /// Force auto exposure off (mandatory per spec §6.1).
    func forceAutoExposureOff() {
        _ = setValue(selector: CT_AE_MODE, unitID: cameraTerminalID, size: 1, value: Int(AE_MODE_MANUAL))
        // Verify
        if let val = getValue(request: UVC_GET_CUR, selector: CT_AE_MODE,
                              unitID: cameraTerminalID, size: 1) {
            let isManual = val == Int(AE_MODE_MANUAL)
            print("Auto exposure forced OFF: \(isManual ? "confirmed" : "FAILED (got \(val))")")
        }
    }

    func setExposureTime(_ value: Int) {
        let clamped = Swift.max(exposureTimeRange.min, Swift.min(value, exposureTimeRange.max))
        _ = setValue(selector: CT_EXPOSURE_TIME_ABS, unitID: cameraTerminalID, size: 4, value: clamped)
    }

    func getExposureTime() -> Int {
        return getValue(request: UVC_GET_CUR, selector: CT_EXPOSURE_TIME_ABS,
                        unitID: cameraTerminalID, size: 4) ?? exposureTimeRange.cur
    }

    func setGain(_ value: Int) {
        let clamped = Swift.max(gainRange.min, Swift.min(value, gainRange.max))
        _ = setValue(selector: PU_GAIN, unitID: processingUnitID, size: 2, value: clamped)
    }

    func getGain() -> Int {
        return getValue(request: UVC_GET_CUR, selector: PU_GAIN,
                        unitID: processingUnitID, size: 2) ?? gainRange.cur
    }
}
