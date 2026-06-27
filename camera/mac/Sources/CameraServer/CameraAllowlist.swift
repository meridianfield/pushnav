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

// CameraAllowlist.swift — known USB cameras, matched by VID/PID.

import Foundation

/// One allowlisted USB camera, identified by its USB VID/PID.
///
/// Keep this list in sync with the Linux and Windows C servers
/// (camera/linux/camera_server.c, camera/windows/camera_server.c).
struct CameraID {
    let vid: Int
    let pid: Int
    let label: String
}

let builtinCameras: [CameraID] = [
    CameraID(vid: 0x32E6, pid: 0x9251, label: "Waveshare OV9281"),
    CameraID(vid: 0x0C45, pid: 0x6366, label: "Arducam OV9281"),
    CameraID(vid: 0x1BCF, pid: 0x2CD1, label: "DECXIN OV9281"),
]

/// Built-in cameras plus any `PUSHNAV_CAMERA_IDS` entries — a comma-separated
/// list of `vid:pid` hex pairs (e.g. `"1bcf:2cd1,0c45:6366"`). Lets a user
/// register a new camera at runtime without recompiling.
func cameraAllowlist() -> [CameraID] {
    var list = builtinCameras

    if let env = ProcessInfo.processInfo.environment["PUSHNAV_CAMERA_IDS"],
       !env.isEmpty {
        let separators = CharacterSet(charactersIn: ", ;")
        for token in env.components(separatedBy: separators) where !token.isEmpty {
            let parts = token.split(separator: ":")
            guard parts.count == 2,
                  let vid = Int(hexDigits(parts[0]), radix: 16),
                  let pid = Int(hexDigits(parts[1]), radix: 16),
                  vid > 0, pid > 0 else {
                logStderr("Ignoring malformed PUSHNAV_CAMERA_IDS entry '\(token)'\n")
                continue
            }
            if !list.contains(where: { $0.vid == vid && $0.pid == pid }) {
                list.append(CameraID(vid: vid, pid: pid,
                                     label: "user-configured (PUSHNAV_CAMERA_IDS)"))
            }
        }
    }

    logStderr("Camera allowlist (\(list.count) entries):\n")
    for cam in list {
        logStderr(String(format: "  %04X:%04X  ", cam.vid, cam.pid) + cam.label + "\n")
    }
    return list
}

private func hexDigits(_ s: Substring) -> String {
    var t = s.lowercased()
    if t.hasPrefix("0x") { t = String(t.dropFirst(2)) }
    return t
}

func logStderr(_ message: String) {
    FileHandle.standardError.write(Data(message.utf8))
}
