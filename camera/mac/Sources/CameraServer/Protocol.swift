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

// Protocol.swift — Camera binary protocol message envelope and type constants.
//
// Mirrors python/evf/camera/protocol.py.
// Every message: type (u32 LE) | length (u32 LE) | payload (length bytes)

import Foundation

// MARK: - Message Types

enum MessageType: UInt32 {
    // Camera → App
    case hello        = 0x00
    case frame        = 0x01
    case controlInfo  = 0x02
    case error        = 0x03

    // App → Camera
    case setControl   = 0x11
    case getControls  = 0x12

    var name: String {
        switch self {
        case .hello:       return "HELLO"
        case .frame:       return "FRAME"
        case .controlInfo: return "CONTROL_INFO"
        case .error:       return "ERROR"
        case .setControl:  return "SET_CONTROL"
        case .getControls: return "GET_CONTROLS"
        }
    }
}

// MARK: - Header Constants

let protocolHeaderSize = 8  // type (4) + length (4)

// MARK: - Encode

/// Encode a protocol message: 8-byte header (type u32 LE + length u32 LE) + payload.
func encodeMessage(type: MessageType, payload: Data = Data()) -> Data {
    var data = Data(capacity: protocolHeaderSize + payload.count)
    var typeVal = type.rawValue.littleEndian
    var lengthVal = UInt32(payload.count).littleEndian
    data.append(Data(bytes: &typeVal, count: 4))
    data.append(Data(bytes: &lengthVal, count: 4))
    data.append(payload)
    return data
}

/// Encode a protocol message with a JSON-serializable dictionary payload.
func encodeJSONMessage(type: MessageType, object: [String: Any]) -> Data? {
    guard let jsonData = try? JSONSerialization.data(withJSONObject: object) else {
        return nil
    }
    return encodeMessage(type: type, payload: jsonData)
}

// MARK: - Parse Header

/// Parse an 8-byte header, returning (messageType, payloadLength).
/// Returns nil if data is too short or type is unrecognized.
func parseHeader(from data: Data) -> (type: MessageType, length: UInt32)? {
    guard data.count >= protocolHeaderSize else { return nil }
    let typeRaw = data.withUnsafeBytes { $0.load(fromByteOffset: 0, as: UInt32.self) }
    let length = data.withUnsafeBytes { $0.load(fromByteOffset: 4, as: UInt32.self) }
    let typeVal = UInt32(littleEndian: typeRaw)
    let lengthVal = UInt32(littleEndian: length)
    guard let msgType = MessageType(rawValue: typeVal) else { return nil }
    return (msgType, lengthVal)
}
