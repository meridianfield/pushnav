---
title: Home
description: Cross-platform plate-solving push-to system for manual telescopes
---

# PushNav
Plate-Solving Push-To System for Manual Telescopes

A cross-platform plate-solving push-to system for manual telescopes. PushNav uses a live camera feed to continuously plate-solve and determine where your telescope is pointing, reporting coordinates to Stellarium, SkySafari, and other planetarium apps in real-time. Point your scope at any bright star, sync, and PushNav will track your pointing as you push to your next target — no encoders, no motors, no GOTO mount required. Just a USB camera, a lens, and your laptop — under **$50** in total hardware.

!!! info "What is plate-solving?"
    Any part of the night sky has a unique arrangement of stars. Plate-solving is a technique that takes a photo, matches that arrangement against a catalog, and reports exactly where the camera is pointing, down to a fraction of a degree. PushNav runs it continuously on the live camera feed, so the app always knows where your telescope is aimed.

![PushNav Mounted](assets/mounted.jpeg)

PushNav uses the European Space Agency's [tetra3](https://github.com/esa/tetra3) fast lost-in-space plate solver — the same algorithm family that powers spacecraft navigation. This efficient solver produces near real-time solutions on a live video feed, enabling seamless push-to navigation even in light-polluted urban skies.

![Screenshot](assets/pushnav_aldebran.png)

## Push-to ops

Pick a target in any planetarium app (Stellarium on the desktop, or SkySafari, Stellarium Mobile, INDI, or ASCOM on a phone or tablet) and PushNav guides you to push the telescope there. At the same time, your scope's live pointing moves on every connected app's sky chart, staying in sync across all clients.

![PushNav tracking M42 across Stellarium and SkySafari](assets/pushnav_ops.png)

Above: **M42 (Orion Nebula)** is the active target on both **Stellarium** (desktop) and **SkySafari** (phone). As the scope is pushed, each plate-solve updates the telescope crosshair on every connected client simultaneously. No motors, no encoders, just a camera and Wi-Fi.

## Cross platform from ground up

Supports **Windows**, **macOS**, and **Linux**. The core app is written in Python, while the camera server is a native binary for each platform (Swift on macOS, C/V4L2 on Linux, C/DirectShow on Windows) to achieve maximum performance and compatibility with UVC cameras.


## How It Works

1. Observer picks a target in a planetarium app — Stellarium on the desktop, or SkySafari / Stellarium Mobile PLUS on a phone — and sends it to PushNav.
2. PushNav shows how to push the telescope to reach the target in its UI. A built-in mobile web interface lets you view the same guidance on your phone — scan a QR code and you're connected.
3. The telescope's pointing is also shown as a live crosshair in the planetarium app's sky chart, moving in real-time as you push the scope.

#### Internal workflow

1. A USB camera in place of your telescope's finder captures the star field
2. PushNav plate-solves frames using the [tetra3](https://github.com/esa/tetra3) star pattern recognition library in near real-time
3. The difference in pointing is calculated and translated into directional guidance which is shown in the UI
4. Solved RA/Dec coordinates are exposed to connected planetarium apps over standard telescope-control protocols, so your telescope's pointing moves on the app's sky chart in real-time as you push.

## Features

- Near real-time plate solving (~20–140 ms per frame)
- One time, simple calibration. No named stars, just point at any bright star and sync
- GOTO navigation guidance from your planetarium app (Stellarium, SkySafari, Stellarium Mobile, etc.)
- Works with **SkySafari**, **Stellarium Mobile**, **INDI**, and **ASCOM** clients over Wi-Fi via the LX200 protocol — see [SkySafari & Other Apps](skysafari-setup.md)
- Audio feedback for lock/lost/GOTO events
- Mobile web interface — scan a QR code on the PushNav screen with your phone for at-the-eyepiece push direction, no app install needed
- Saves calibration for quick re-sync
- Works from urban light-polluted skies with the right camera/lens combo (see hardware guide)

## Open source — please report issues

PushNav is free and open source under the GPLv3. It's been tested in real observing sessions with **Stellarium** (desktop) and **SkySafari Plus/Pro**. The Stellarium Mobile, INDI, and ASCOM paths follow the same LX200 protocol and should work out of the box, but haven't yet been field-tested against every client version.

If something doesn't work as described — or you'd like to see an app supported that isn't listed — please open an issue on the [GitHub issue tracker](https://github.com/meridianfield/pushnav/issues). Reports from real observing sessions are the best way for the project to improve.
