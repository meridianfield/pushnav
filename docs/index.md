---
title: Home
description: Cross-platform plate-solving push-to system for manual telescopes
---

# PushNav
Plate-Solving Push-To System for Manual Telescopes

A cross-platform plate-solving push-to system for manual telescopes. PushNav uses a live camera feed to continuously plate-solve and determine where your telescope is pointing, reporting coordinates to Stellarium in real-time. Point your scope at any bright star, sync, and PushNav will track your pointing as you push to your next target — no encoders, no motors, no GOTO mount required. Just a USB camera, a lens, and your laptop — under **$50** in total hardware.

![PushNav Mounted](assets/mounted.jpeg)

PushNav uses the European Space Agency's [tetra3](https://github.com/esa/tetra3) fast lost-in-space plate solver — the same algorithm family that powers spacecraft navigation. This efficient solver produces near real-time solutions on a live video feed, enabling seamless push-to navigation even in light-polluted urban skies.

![Screenshot](assets/pushnav_aldebran.png)

## Cross platform from ground up

Supports **Windows**, **macOS**, and **Linux**. The core app is written in Python, while the camera server is a native binary for each platform (Swift on macOS, C/V4L2 on Linux, C/DirectShow on Windows) to achieve maximum performance and compatibility with UVC cameras.


## How It Works

1. Observer selects an object in Stellarium and "Slews" (Cmd+1 or Ctrl+1)
2. PushNav shows how to push the telescope to reach the target in its UI. A built-in mobile web interface lets you view the same guidance on your phone — scan a QR code and you're connected.
3. Alternatively the telescope's pointing is also shown in Stellarium as a telescope crosshair that moves in real-time as you push the scope.

#### Internal workflow

1. A USB camera in place of your telescope's finder captures the star field
2. PushNav plate-solves frames using the [tetra3](https://github.com/esa/tetra3) star pattern recognition library in near real-time
3. The difference in pointing is calculated and translated into directional guidance which is shown in the UI
4. Solved RA/Dec coordinates are also broadcast to Stellarium via its telescope protocol, so you can see your telescope's pointing in Stellarium's sky chart in real-time as you push.

## Features

- Near real-time plate solving (~20–140 ms per frame)
- One time, simple calibration. No named stars, just point at any bright star and sync
- GOTO navigation guidance from Stellarium
- Audio feedback for lock/lost/GOTO events
- Mobile web interface — scan a QR code on the PushNav screen with your phone for at-the-eyepiece push direction, no app install needed
- Saves calibration for quick re-sync
- Works from urban light-polluted skies with the right camera/lens combo (see hardware guide)
