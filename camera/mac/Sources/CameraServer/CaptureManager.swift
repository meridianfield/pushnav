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

// CaptureManager.swift — AVFoundation capture session with MJPEG JPEG extraction.
//
// Discovers the openaicam by name or modelID, configures for MJPEG at 1280x720/30fps,
// and extracts JPEG frames from CMBlockBuffer (zero-copy when MJPEG) or falls back
// to CIContext JPEG encoding.

import AVFoundation
import CoreImage
import CoreMedia
import CoreVideo
import Foundation

class CaptureManager: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    private let session = AVCaptureSession()
    private let frameQueue = DispatchQueue(label: "com.evf.camera.frameQueue")
    private let jpegLock = NSLock()
    private var _latestJPEG: Data?
    private var ciContext: CIContext?
    var onFrame: ((Data) -> Void)?

    /// Thread-safe access to the latest JPEG frame.
    var latestJPEG: Data? {
        jpegLock.lock()
        defer { jpegLock.unlock() }
        return _latestJPEG
    }

    /// Start the capture session. Returns true on success.
    func start() -> Bool {
        guard let camera = findCamera() else {
            fputs("ERROR: openaicam not found in AVFoundation\n", stderr)
            return false
        }
        print("Found camera: \(camera.localizedName) [\(camera.modelID)]")

        session.beginConfiguration()

        // Add input
        do {
            let input = try AVCaptureDeviceInput(device: camera)
            guard session.canAddInput(input) else {
                fputs("ERROR: Cannot add camera input to session\n", stderr)
                return false
            }
            session.addInput(input)
        } catch {
            fputs("ERROR: Could not create capture input: \(error)\n", stderr)
            return false
        }

        // Configure format: prefer MJPEG at 1280x720, 30fps
        configureFormat(device: camera)

        // Add video data output
        let output = AVCaptureVideoDataOutput()
        output.setSampleBufferDelegate(self, queue: frameQueue)
        output.alwaysDiscardsLateVideoFrames = true
        guard session.canAddOutput(output) else {
            fputs("ERROR: Cannot add video output to session\n", stderr)
            return false
        }
        session.addOutput(output)

        session.commitConfiguration()
        session.startRunning()
        print("Capture session started")
        return true
    }

    func stop() {
        session.stopRunning()
        print("Capture session stopped")
    }

    // MARK: - AVCaptureVideoDataOutputSampleBufferDelegate

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        guard let jpeg = extractJPEG(from: sampleBuffer) else { return }
        jpegLock.lock()
        _latestJPEG = jpeg
        jpegLock.unlock()
        onFrame?(jpeg)
    }

    // MARK: - Private

    private func findCamera() -> AVCaptureDevice? {
        var deviceTypes: [AVCaptureDevice.DeviceType] = [.builtInWideAngleCamera]
        if #available(macOS 14.0, *) {
            deviceTypes.append(.external)
        }
        let discovery = AVCaptureDevice.DiscoverySession(
            deviceTypes: deviceTypes, mediaType: .video, position: .unspecified)

        // Try by name first, then by modelID
        return discovery.devices.first(where: { $0.localizedName.contains("openaicam") })
            ?? discovery.devices.first(where: { $0.modelID.contains("0x9251") })
    }

    private func configureFormat(device: AVCaptureDevice) {
        let targetWidth: Int32 = 1280
        let targetHeight: Int32 = 720

        // Log all available formats for diagnostics
        print("Available formats:")
        for format in device.formats {
            let desc = format.formatDescription
            let dims = CMVideoFormatDescriptionGetDimensions(desc)
            let subType = CMFormatDescriptionGetMediaSubType(desc)
            let fourCC = fourCharCode(subType)
            let fpsRanges = format.videoSupportedFrameRateRanges.map {
                "\(Int($0.minFrameRate))-\(Int($0.maxFrameRate))fps"
            }.joined(separator: ", ")
            print("  \(dims.width)x\(dims.height) \(fourCC) (0x\(String(subType, radix: 16))) [\(fpsRanges)]")
        }

        // Match MJPEG formats: kCMVideoCodecType_JPEG ('jpeg') or JPEG_OpenDML ('dmb1')
        // Many USB cameras advertise as JPEG_OpenDML rather than plain JPEG
        let jpegTypes: Set<CMVideoCodecType> = [
            kCMVideoCodecType_JPEG,
            kCMVideoCodecType_JPEG_OpenDML,
        ]

        var bestFormat: AVCaptureDevice.Format?
        for format in device.formats {
            let desc = format.formatDescription
            let dims = CMVideoFormatDescriptionGetDimensions(desc)
            let subType = CMFormatDescriptionGetMediaSubType(desc)

            if jpegTypes.contains(subType) &&
               dims.width == targetWidth && dims.height == targetHeight {
                bestFormat = format
                break
            }
        }

        // Fallback: any JPEG format at any resolution
        if bestFormat == nil {
            bestFormat = device.formats.first { format in
                let subType = CMFormatDescriptionGetMediaSubType(format.formatDescription)
                return jpegTypes.contains(subType)
            }
            if bestFormat != nil {
                let dims = CMVideoFormatDescriptionGetDimensions(bestFormat!.formatDescription)
                print("WARNING: MJPEG 1280x720 not available, using MJPEG \(dims.width)x\(dims.height)")
            }
        }

        // Final fallback: pick any format at target resolution (will use CIContext JPEG encoding)
        if bestFormat == nil {
            bestFormat = device.formats.first { format in
                let dims = CMVideoFormatDescriptionGetDimensions(format.formatDescription)
                return dims.width == targetWidth && dims.height == targetHeight
            }
            if bestFormat != nil {
                let subType = CMFormatDescriptionGetMediaSubType(bestFormat!.formatDescription)
                print("No MJPEG available, using \(fourCharCode(subType)) \(targetWidth)x\(targetHeight) (CIContext JPEG encoding)")
            }
        }

        guard let format = bestFormat else {
            print("WARNING: No suitable format found, using AVFoundation default")
            return
        }

        do {
            try device.lockForConfiguration()
            device.activeFormat = format

            // Pick the lowest supported frame rate (saves CPU/bandwidth for astronomy)
            // Fall back to whatever the format supports if our preferred rate isn't available
            let dims = CMVideoFormatDescriptionGetDimensions(format.formatDescription)
            if let bestRange = format.videoSupportedFrameRateRanges
                .sorted(by: { $0.minFrameRate < $1.minFrameRate }).first {
                device.activeVideoMinFrameDuration = bestRange.minFrameDuration
                device.activeVideoMaxFrameDuration = bestRange.minFrameDuration
                print("Configured \(dims.width)x\(dims.height) @ \(Int(bestRange.minFrameRate))fps")
            }

            device.unlockForConfiguration()
        } catch {
            fputs("WARNING: Could not lock device for configuration: \(error)\n", stderr)
        }
    }

    /// Extract JPEG data from a sample buffer.
    /// Zero-copy from CMBlockBuffer when the source is MJPEG; fallback to CIContext encoding.
    private func extractJPEG(from sampleBuffer: CMSampleBuffer) -> Data? {
        let formatDesc = CMSampleBufferGetFormatDescription(sampleBuffer)
        let subType = formatDesc.map { CMFormatDescriptionGetMediaSubType($0) } ?? 0

        // If source is MJPEG, extract JPEG directly from CMBlockBuffer (zero-copy)
        let jpegTypes: Set<CMVideoCodecType> = [kCMVideoCodecType_JPEG, kCMVideoCodecType_JPEG_OpenDML]
        if jpegTypes.contains(subType) {
            if let blockBuffer = CMSampleBufferGetDataBuffer(sampleBuffer) {
                var length: Int = 0
                var dataPointer: UnsafeMutablePointer<CChar>?
                let status = CMBlockBufferGetDataPointer(
                    blockBuffer, atOffset: 0, lengthAtOffsetOut: nil,
                    totalLengthOut: &length, dataPointerOut: &dataPointer)
                if status == kCMBlockBufferNoErr, let ptr = dataPointer, length > 0 {
                    return Data(bytes: ptr, count: length)
                }
            }
        }

        // Fallback: encode from pixel buffer using CIContext
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else {
            return nil
        }

        if ciContext == nil {
            ciContext = CIContext()
        }

        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        return ciContext?.jpegRepresentation(of: ciImage, colorSpace: colorSpace,
                                             options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: 0.85])
    }
}

/// Convert a FourCC code to a readable string (e.g. 0x6A706567 → "jpeg").
private func fourCharCode(_ code: FourCharCode) -> String {
    let bytes = [
        UInt8((code >> 24) & 0xFF),
        UInt8((code >> 16) & 0xFF),
        UInt8((code >> 8) & 0xFF),
        UInt8(code & 0xFF),
    ]
    if let str = String(bytes: bytes, encoding: .ascii), str.allSatisfy({ $0.isASCII && $0 >= " " }) {
        return str
    }
    return String(format: "0x%08X", code)
}
