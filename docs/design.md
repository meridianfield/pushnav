---
title: Design Philosophy
---

## Keep It Simple

- Use off-the-shelf hardware
- Stand on the shoulders of giants : Stellarium is the primary UI/UX. Stellarium is ubiquitous, free, open-source, and has a fantastic interface. Available for all platforms - Windows, macOS, and Linux. PushNav is setup as a telescope plugin for Stellarium, so you can use Stellarium's interface to select targets and PushNav will show you which way to push. No need to reinvent the wheel with a custom UI. Stellarium also shows where your telescope is pointing in the sky.
- Use the user's laptop for all processing. No custom hardware or microcontrollers to program. Just a USB camera and your laptop is all you need. The app runs on your laptop and communicates with the camera over USB. No need for an Arduino or Raspberry Pi or custom PCB. This keeps the cost down and makes it accessible for anyone with a laptop and a USB camera.
- Extremely simple one time alignment. Point and center the eyepiece of the scope to **any** bright star and press "next". Most amateur astronomers starting out with the hobby don't know how to locate named stars in the sky. The idea is to keep alignment as simple as possible.

## Why Stellarium

Stellarium is the primary UI/UX for PushNav. It is ubiquitous, free, open-source, and available on Windows, macOS, and Linux with a fantastic interface. PushNav connects as a telescope plugin, so Stellarium's sky chart shows where your telescope is pointing in real-time. You select targets in Stellarium and PushNav shows you which way to push. No need to reinvent the wheel with a custom planetarium UI.

## Why No Custom Hardware

PushNav uses the user's laptop for all processing. No custom hardware, microcontrollers, Arduino, Raspberry Pi, or custom PCB is required. Just a USB camera and your laptop is all you need. The app communicates with the camera over USB. This keeps the cost down and makes it accessible for anyone with a laptop and a USB camera.

## Why a Mobile Web Interface

When you're at the eyepiece pushing a Dobsonian, your laptop is usually a few feet away on a table or the ground. Squinting at a laptop screen in the dark while nudging a heavy tube is awkward. PushNav solves this with a built-in mobile web interface — your phone becomes a second screen showing the push direction, target name, and live pointing.

Why a browser page served from the laptop, and not a native iOS / Android app?

- **No app store, no install.** Scan a QR code with your phone's camera and you're connected in under two seconds. No app store download, no app approval process, no version compatibility matrix. Works on any phone with a browser — iPhone, Android, even a tablet.
- **Zero logic on the phone.** The phone is purely a display. All plate-solving, coordinate math, and Stellarium communication happen on the laptop. The phone receives a lightweight JSON stream over WebSocket and renders it — nothing to compute, nothing to cache, nothing to crash.
- **One codebase.** A native mobile app would mean maintaining an iOS codebase, an Android codebase, and the desktop app — tripling the surface area for a one-person project. The web interface is a single HTML page served by the same Python process that runs the solver. One language, one deploy, one thing to debug.
- **No pairing, no Bluetooth, no setup.** The phone and laptop just need to be on the same Wi-Fi. The QR code encodes the laptop's local IP and port. No Bluetooth handshake, no cloud relay, no account creation.
