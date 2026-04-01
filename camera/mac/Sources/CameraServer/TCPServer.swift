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

// TCPServer.swift — Network.framework TCP server, single client, message recv/send.
//
// Uses NWListener bound to 127.0.0.1:port, accepts a single client connection.
// Completion-based receive: chain receiveHeader → receivePayload → dispatch.

import Foundation
import Network

class TCPServer {
    private let port: UInt16
    private var listener: NWListener?
    private var connection: NWConnection?
    private let serverQueue = DispatchQueue(label: "com.evf.camera.tcp")

    /// Called when a client connects.
    var onClientConnected: (() -> Void)?
    /// Called when the client disconnects.
    var onClientDisconnected: (() -> Void)?
    /// Called when a complete message is received.
    var onMessage: ((MessageType, Data) -> Void)?

    init(port: UInt16) {
        self.port = port
    }

    /// Start listening for connections.
    func start() -> Bool {
        let params = NWParameters.tcp
        // Bind to localhost only
        params.requiredLocalEndpoint = NWEndpoint.hostPort(host: "127.0.0.1", port: NWEndpoint.Port(rawValue: port)!)

        do {
            listener = try NWListener(using: params)
        } catch {
            fputs("ERROR: Failed to create TCP listener: \(error)\n", stderr)
            return false
        }

        listener?.stateUpdateHandler = { [weak self] state in
            switch state {
            case .ready:
                if let port = self?.listener?.port {
                    print("TCP server listening on 127.0.0.1:\(port)")
                }
            case .failed(let error):
                fputs("ERROR: TCP listener failed: \(error)\n", stderr)
            default:
                break
            }
        }

        listener?.newConnectionHandler = { [weak self] newConnection in
            guard let self = self else { return }
            if self.connection != nil {
                // Reject additional connections — single client only
                print("Rejecting additional connection (single client mode)")
                newConnection.cancel()
                return
            }
            self.acceptConnection(newConnection)
        }

        listener?.start(queue: serverQueue)
        return true
    }

    func stop() {
        connection?.cancel()
        connection = nil
        listener?.cancel()
        listener = nil
    }

    // MARK: - Send

    /// Send a raw encoded message.
    func send(type: MessageType, payload: Data = Data()) {
        let data = encodeMessage(type: type, payload: payload)
        sendRaw(data)
    }

    /// Send a JSON message.
    func sendJSON(type: MessageType, object: [String: Any]) {
        guard let data = encodeJSONMessage(type: type, object: object) else {
            fputs("ERROR: Failed to encode JSON message\n", stderr)
            return
        }
        sendRaw(data)
    }

    /// Send a FRAME message with JPEG data.
    func sendFrame(_ jpegData: Data) {
        send(type: .frame, payload: jpegData)
    }

    // MARK: - Private

    private func acceptConnection(_ conn: NWConnection) {
        self.connection = conn
        print("Client connecting from \(conn.endpoint)")

        conn.stateUpdateHandler = { [weak self] state in
            switch state {
            case .ready:
                print("Client connected")
                self?.onClientConnected?()
                self?.receiveHeader()
            case .failed(let error):
                print("Client connection failed: \(error)")
                self?.handleDisconnect()
            case .cancelled:
                print("Client connection cancelled")
                self?.handleDisconnect()
            default:
                break
            }
        }

        conn.start(queue: serverQueue)
    }

    private func handleDisconnect() {
        connection = nil
        onClientDisconnected?()
    }

    private func receiveHeader() {
        guard let conn = connection else { return }

        conn.receive(minimumIncompleteLength: protocolHeaderSize,
                     maximumLength: protocolHeaderSize) { [weak self] content, _, isComplete, error in
            guard let self = self else { return }

            if isComplete || error != nil {
                if let error = error {
                    print("Receive error: \(error)")
                }
                self.handleDisconnect()
                return
            }

            guard let data = content, data.count == protocolHeaderSize else {
                self.handleDisconnect()
                return
            }

            guard let header = parseHeader(from: data) else {
                print("WARNING: Unknown message type, disconnecting")
                self.handleDisconnect()
                return
            }

            if header.length == 0 {
                // No payload — dispatch immediately
                self.onMessage?(header.type, Data())
                self.receiveHeader()
            } else {
                self.receivePayload(type: header.type, remaining: Int(header.length))
            }
        }
    }

    private func receivePayload(type: MessageType, remaining: Int) {
        guard let conn = connection else { return }

        conn.receive(minimumIncompleteLength: remaining,
                     maximumLength: remaining) { [weak self] content, _, isComplete, error in
            guard let self = self else { return }

            if isComplete || error != nil {
                self.handleDisconnect()
                return
            }

            guard let data = content, data.count == remaining else {
                self.handleDisconnect()
                return
            }

            self.onMessage?(type, data)
            self.receiveHeader()
        }
    }

    private func sendRaw(_ data: Data) {
        guard let conn = connection else { return }
        conn.send(content: data, completion: .contentProcessed { error in
            if let error = error {
                fputs("Send error: \(error)\n", stderr)
            }
        })
    }
}
