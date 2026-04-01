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

// main.swift — Entry point for the EVF camera server.
//
// Orchestrates UVC controller, capture session, TCP server, and frame streaming.
// Runs headless using dispatchMain() to keep alive for AVFoundation + Network callbacks.

import Foundation

let serverVersion = "0.1.0"
let protocolVersion: Int = 1
let defaultPort: UInt16 = 8764

print("EVF Camera Server v\(serverVersion)")

// MARK: - 1. Initialize UVC Controller

guard let uvc = UVCController(vendorID: OPENAICAM_VID, productID: OPENAICAM_PID) else {
    fputs("FATAL: Camera not found. Ensure openaicam is connected.\n", stderr)
    exit(1)
}

// MARK: - 2. Force auto-exposure OFF (spec §6.1)

uvc.forceAutoExposureOff()

// MARK: - 3. Start capture

let capture = CaptureManager()
guard capture.start() else {
    fputs("FATAL: Failed to start capture session.\n", stderr)
    exit(1)
}

// MARK: - 4. Start TCP server

let controlManager = ControlManager(uvc: uvc)
let server = TCPServer(port: defaultPort)

var frameTimer: DispatchSourceTimer?

server.onClientConnected = {
    print("Client connected, sending HELLO")

    // Send HELLO
    let hello: [String: Any] = [
        "protocol_version": protocolVersion,
        "backend": "mac-swift",
        "backend_version": serverVersion,
        "camera_model": "openaicam",
        "stream_format": "MJPEG",
        "default_width": 1280,
        "default_height": 720,
        "default_fps": 30,
    ]
    server.sendJSON(type: .hello, object: hello)
}

server.onMessage = { msgType, payload in
    switch msgType {
    case .hello:
        // Client HELLO response — validate version, then send CONTROL_INFO and start streaming
        if let json = try? JSONSerialization.jsonObject(with: payload) as? [String: Any] {
            let clientVersion = json["protocol_version"] as? Int ?? -1
            if clientVersion != protocolVersion {
                fputs("ERROR: Protocol version mismatch: client=\(clientVersion), server=\(protocolVersion)\n", stderr)
                server.send(type: .error,
                            payload: "Protocol version mismatch".data(using: .utf8) ?? Data())
                return
            }
            print("Client HELLO OK (version \(clientVersion))")
        }

        // Send CONTROL_INFO
        let controlInfo = controlManager.buildControlInfo()
        server.sendJSON(type: .controlInfo, object: controlInfo)
        print("Sent CONTROL_INFO: \(controlInfo)")

        // Start frame timer (~30fps = 33ms)
        startFrameTimer()

    case .setControl:
        if let json = try? JSONSerialization.jsonObject(with: payload) as? [String: Any],
           let controlId = json["id"] as? String,
           let value = json["value"] as? Int {
            _ = controlManager.applySetControl(id: controlId, value: value)
            // Respond with updated CONTROL_INFO
            server.sendJSON(type: .controlInfo, object: controlManager.buildControlInfo())
        } else {
            fputs("WARNING: Bad SET_CONTROL payload\n", stderr)
        }

    case .getControls:
        server.sendJSON(type: .controlInfo, object: controlManager.buildControlInfo())

    default:
        print("Ignoring message type: \(msgType.name)")
    }
}

server.onClientDisconnected = {
    print("Client disconnected, exiting")
    stopFrameTimer()
    capture.stop()
    exit(0)
}

guard server.start() else {
    fputs("FATAL: Failed to start TCP server.\n", stderr)
    exit(1)
}

// MARK: - Frame Timer

func startFrameTimer() {
    stopFrameTimer()

    let timer = DispatchSource.makeTimerSource(queue: DispatchQueue(label: "com.evf.camera.frameTimer"))
    timer.schedule(deadline: .now(), repeating: .milliseconds(33))
    timer.setEventHandler {
        if let jpeg = capture.latestJPEG {
            server.sendFrame(jpeg)
        }
    }
    timer.resume()
    frameTimer = timer
    print("Frame streaming started (~30fps)")
}

func stopFrameTimer() {
    frameTimer?.cancel()
    frameTimer = nil
}

// MARK: - Keep process alive

print("Camera server ready, waiting for connections on port \(defaultPort)")
dispatchMain()
