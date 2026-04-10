---
title: Design Philosophy
---

## KISS — Keep It Simple, Stupid

- Use off-the-shelf hardware
- Stand on the soulders of giants : Stellarium is the primary UI/UX. Stellarium is ubiquitous, free, open-source, and has a fantastic interface. Available for all platforms - Windows, macOS, and Linux. PushNav is setup as a telescope plugin for Stellarium, so you can use Stellarium's interface to select targets and PushNav will show you which way to push. No need to reinvent the wheel with a custom UI. Stellarium also shows where your telescope is pointing in the sky.
- Use the user's laptop for all processing. No custom hardware or microcontrollers to program. Just a USB camera and your laptop is all you need. The app runs on your laptop and communicates with the camera over USB. No need for an Arduino or Raspberry Pi or custom PCB. This keeps the cost down and makes it accessible for anyone with a laptop and a USB camera.
- Extremely simple one time alignment. Point and center the eyepiece of the scope to **any** bright star and press "next". Most amateur astronomers starting out with the hobby don't know how to locate named stars in the sky. The idea is to keep alignment as simple as possible.

## Why Stellarium

Stellarium is the primary UI/UX for PushNav. It is ubiquitous, free, open-source, and available on Windows, macOS, and Linux with a fantastic interface. PushNav connects as a telescope plugin, so Stellarium's sky chart shows where your telescope is pointing in real-time. You select targets in Stellarium and PushNav shows you which way to push. No need to reinvent the wheel with a custom planetarium UI.

## Why No Custom Hardware

PushNav uses the user's laptop for all processing. No custom hardware, microcontrollers, Arduino, Raspberry Pi, or custom PCB is required. Just a USB camera and your laptop is all you need. The app communicates with the camera over USB. This keeps the cost down and makes it accessible for anyone with a laptop and a USB camera.
