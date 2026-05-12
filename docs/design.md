---
title: Design Philosophy
---

## Keep It Simple

- Use off-the-shelf hardware
- Stand on the shoulders of giants: PushNav plugs into whatever planetarium or astronomy app you already use (Stellarium on the desktop, SkySafari or Stellarium Mobile PLUS on the phone, or INDI/ASCOM for advanced setups). You pick targets in *your* app; PushNav shows you how to push. Your telescope's pointing appears live as a crosshair right in the same app. No new sky chart to learn.
- Use the user's laptop for all processing. No custom hardware or microcontrollers to program. Just a USB camera and your laptop is all you need. The app runs on your laptop and communicates with the camera over USB. No need for an Arduino or Raspberry Pi or custom PCB. This keeps the cost down and makes it accessible for anyone with a laptop and a USB camera.
- Extremely simple one time alignment. Point and center the eyepiece of the scope to **any** bright star and press "next". Most amateur astronomers starting out with the hobby don't know how to locate named stars in the sky. The idea is to keep alignment as simple as possible.

## Why We Piggyback On Existing Apps

Every amateur astronomer already has a planetarium app they know. Great ones exist for every platform: Stellarium is free, open-source, and ubiquitous on the desktop; SkySafari Plus/Pro is the iOS/Android gold standard; Stellarium Mobile PLUS is a solid alternative for users who prefer Stellarium's look on a phone; and serious astrophotographers anchor around KStars/Ekos (via INDI) or N.I.N.A. (via ASCOM).

Rather than build our own sky chart and fight to keep star catalogs up to date, PushNav implements two well-established telescope-control protocols (the **Stellarium binary protocol** for desktop Stellarium, and **Meade LX200** for everything else) and gets the entire ecosystem for near-zero maintenance cost. Each app is maintained by its own team; PushNav just needs to speak the protocols correctly.

The upshot: users aren't buying into *our* UI. They connect to whatever they already use. That's a more durable position than picking one winner.

## Curated and Comprehensive

For *target picking*, PushNav doesn't make you choose between simplicity and reach. The built-in **What to See** tab gives you both side by side:

- **Buddy** — 161 hand-picked deep-sky objects with filters for equipment, light pollution and visual reward. The "what should I look at tonight?" answer for a new observer who doesn't know the sky yet.
- **Advanced** — fuzzy search across 12,522 NGC objects (OpenNGC) and 8,825 bright stars (HYG). The "give me M81" answer when you already know what you want.
- **Manual coordinates** — RA/Dec entry for the rest: comets, asteroids, satellites, anything ephemeris-driven that no catalog covers.

This isn't a contradiction of "keep it simple"; it's an acknowledgement that simplicity at first launch shouldn't cap what the same user does six months later. The curated path stays the easy default, and the comprehensive path stays a click away. It's the piggyback principle extended one level: stand on the shoulders of the planetarium apps for sky browsing, and on the shoulders of the open star/DSO catalogs (OpenNGC, HYG, both CC-BY-SA) for target lookup.

## Spatial Context, Not a Sky Chart

The wizard's right column shows a small interactive **Sky View** — a 3D hemispheric dome with cardinal directions, a horizon, and up to two markers (where the scope is currently pointing, where the active target sits).

This is *spatial orientation*, not a planetarium. You can't browse the sky in it, you can't search for targets, you won't see deep-sky labels or constellation lines. The dome answers exactly one question: *is my target up and to the right, or down and to the left, relative to where I'm currently aimed?* Anything more than that — star fields, DSO catalogs, magnitude limits — already lives in Stellarium / SkySafari / Stellarium Mobile, which do that work far better than PushNav could on its own.

The "don't build a sky chart" stance from the previous section still holds. The dome is a small embedded compass that happens to share the window with the camera feed and the wizard; it isn't an attempt to compete with the planetarium apps.

## Why No Custom Hardware

PushNav uses the user's laptop for all processing. No custom hardware, microcontrollers, Arduino, Raspberry Pi, or custom PCB is required. Just a USB camera and your laptop is all you need. The app communicates with the camera over USB. This keeps the cost down and makes it accessible for anyone with a laptop and a USB camera.

## Why a Mobile Web Interface

When you're at the eyepiece pushing a Dobsonian, your laptop is usually a few feet away on a table or the ground. Squinting at a laptop screen in the dark while nudging a heavy tube is awkward. PushNav solves this with a built-in mobile web interface: your phone becomes a second screen showing the push direction, target name, and live pointing.

Why a browser page served from the laptop, and not a native iOS / Android app?

- **No app store, no install.** Scan a QR code with your phone's camera and you're connected in under two seconds. No app store download, no app approval process, no version compatibility matrix. Works on any phone with a browser (iPhone, Android, even a tablet).
- **Zero logic on the phone.** The phone is purely a display. All plate-solving, coordinate math, and telescope-app communication happen on the laptop. The phone receives a lightweight JSON stream over WebSocket and renders it. Nothing to compute, nothing to cache, nothing to crash.
- **One codebase.** A native mobile app would mean maintaining an iOS codebase, an Android codebase, and the desktop app, tripling the surface area for a one-person project. The web interface is a single HTML page served by the same Python process that runs the solver. One language, one deploy, one thing to debug.
- **No pairing, no Bluetooth, no setup.** The phone and laptop just need to be on the same Wi-Fi. The QR code encodes the laptop's local IP and port. No Bluetooth handshake, no cloud relay, no account creation.

If you'd rather run a full planetarium on your phone, SkySafari Plus/Pro and Stellarium Mobile PLUS both connect to PushNav directly over Wi-Fi (see [SkySafari & Other Apps](skysafari-setup.md)). The built-in web interface stays focused on the one thing those apps don't do: large, clear push-direction arrows at the eyepiece with zero setup.
