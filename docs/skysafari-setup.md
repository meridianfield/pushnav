---
title: SkySafari & Other Apps
---

# Using PushNav with SkySafari, Stellarium Mobile, INDI, and ASCOM

If you'd rather use your phone (or a desktop planetarium) to pick targets and see your telescope's pointing, PushNav can talk to **SkySafari**, **Stellarium Mobile PLUS**, **INDI** (KStars), or an **ASCOM** client.

PushNav appears as an **LX200-compatible telescope** on your local Wi-Fi network. Any of the four apps above can connect to it using their standard LX200 setup — you just configure the app you prefer.

## What you'll get

- A live **scope crosshair** on SkySafari's star chart, moving in real time as you push the telescope
- **Tap-to-goto** from your phone — pick any object in SkySafari, tap GoTo, and PushNav's screen shows you the push direction
- The same LX200 integration already works with Stellarium Mobile PLUS, KStars (via INDI), and ASCOM-compatible desktop planetariums — detailed walkthroughs for those are coming soon

## Find PushNav's telescope address

Open PushNav and look at the **Settings** section in the side panel. You'll see a **Telescope Control** block with two addresses:

- **LX200** — this is the one you want. Format: `192.168.x.y:4030` (your laptop's Wi-Fi IP followed by port 4030).
- *Stellarium (desktop, same machine only)* — for desktop Stellarium on the same computer, covered in [Stellarium Setup](stellarium-setup.md) instead.

Next to each address there's a small dot that lights up when a client is actively talking to PushNav — a quick visual confirmation once you're connected.

!!! tip "Make sure your phone and laptop are on the same Wi-Fi network"
    PushNav doesn't need the internet, but it does need your phone and laptop to be on the same local network. If they can't see each other, the apps below won't connect.

    **No Wi-Fi at your observing site?** Turn on your phone's personal hotspot and connect your laptop to it. The phone and laptop are still on the same local network, so everything works identically — the phone just plays the role of both Wi-Fi router and telescope client.

    **Important:** connect the laptop to the hotspot **before** launching PushNav. PushNav reads the LAN IP at startup and shows it in the Telescope Control panel; if you start PushNav first and then switch networks, the displayed address will be stale and SkySafari won't reach it. If this happens, just quit PushNav and relaunch.

!!! tip "Moving between networks: update the app's preset each time"
    PushNav's IP address is assigned by whichever network you're on, so it changes between your home Wi-Fi, an observing-site Wi-Fi, and a phone hotspot. A SkySafari / Stellarium Mobile / INDI / ASCOM preset saved on one network won't connect on another. The IP in the preset points to an address that doesn't exist on the new network.

    Each time you switch networks, check PushNav's current IP in the **Telescope Control** panel and **update your app's preset IP to match** (or keep a separate preset per network you observe from).

---

## SkySafari (iOS, Android, macOS, Windows)

**Note:** Telescope control requires **SkySafari Plus** or **SkySafari Pro**. The free SkySafari doesn't include it.

### Setup

1. In SkySafari, open **Settings → Telescope → Presets → Add Device → Other**.
2. Fill in:

    | Setting | Value |
    |---|---|
    | Mount Type | **AltAz GoTo** — the **GoTo** part matters; Push-To modes in SkySafari don't drive the Stop/GoTo button transitions correctly |
    | Scope Type | **Meade LX200 Classic** |
    | IP Address | PushNav's LAN IP (from PushNav's Settings panel) |
    | Port | `4030` (default) |

3. Tap **Check Connection Now**. You should see **Connection verified**.
4. **Save Preset**.

No Communication Settings section to configure — SkySafari handles the TCP details internally once the preset is saved.

### Making the crosshair visible

SkySafari won't draw the scope crosshair on the star chart until you enable a FOV indicator.

Tap the **FOV display** at the top right of the star chart and pick the FOV / rings / preset you want. Only after this does the telescope pointing crosshair appear on the chart.

### Sending a target (GoTo)

1. Tap any object in SkySafari's star chart.
2. Tap the **GoTo** button (in the Scope Control panel).
3. The button changes to **Stop** while you push — PushNav's on-screen arrows and the mobile companion view guide you.
4. When your plate-solve lands within ~0.5° of the target, the button automatically flips back to **GoTo**. Center the target in the eyepiece by eye.

### Troubleshooting

**"Target is below the horizon" when you try to GoTo something you can see.**
SkySafari computes altitude from **its own Observer location and clock**, not PushNav's. Open SkySafari → Settings → Observer and set your real location. After that, GoTo will let you slew to anything that's actually above your horizon.

**Scope crosshair doesn't appear anywhere.**
FOV indicator hasn't been enabled. Tap the **FOV display** at the top right of the star chart and pick a preset — see *"Making the crosshair visible"* above.

**SkySafari says it's connected but the crosshair never moves.**
PushNav isn't in the Track state yet — go through the Sync and Roll steps (or hit **Use Previous Calibration** if you've synced before). Until PushNav has a valid plate-solve, it returns a zero position and the SkySafari crosshair sits at RA 00:00, Dec 0°.

---

## Stellarium Mobile PLUS (iOS, Android)

*Setup walkthrough coming soon.* Stellarium Mobile PLUS supports the LX200 telescope protocol, so it should connect to PushNav out of the box — but we haven't yet field-tested and documented the exact setup flow. If you try it and something works (or doesn't), please [share your experience on the issue tracker](https://github.com/meridianfield/pushnav/issues).

---

## INDI (KStars)

*Setup walkthrough coming soon.* KStars connects to PushNav via INDI's `indi_lx200basic` driver over TCP, but the full setup walkthrough hasn't been field-tested yet. If you try it, please [share your experience on the issue tracker](https://github.com/meridianfield/pushnav/issues).

---

## ASCOM (Windows)

*Setup walkthrough coming soon.* Windows planetariums that use ASCOM (for example Stellarium-on-Windows via the ASCOM telescope plugin, or TheSkyX as a sky chart) can connect to PushNav through a Meade LX200 ASCOM driver in TCP mode — but the full setup walkthrough hasn't been field-tested yet. If you try it, please [share your experience on the issue tracker](https://github.com/meridianfield/pushnav/issues).

!!! note "ASCOM and astrophotography tools"
    Most ASCOM clients on Windows (N.I.N.A., SharpCap, APT, etc.) are astrophotography workflows that expect a motorized mount. PushNav is a visual-observing helper — it can't move a scope — so those tools aren't a natural fit. The ASCOM integration is meant for visual-only planetarium apps.

---

## Important things to know

**PushNav does not control motors.** It's a push-to helper. The GoTo button in SkySafari doesn't physically move the scope — it just tells PushNav where you're aiming, and PushNav guides you there with the on-screen arrows and the live crosshair. Same for every client above.

**PushNav is the source of truth for pointing.** If you "sync" or "align" from SkySafari / INDI / ASCOM, that sync is ignored — PushNav owns its own calibration (done in the main app during the Sync and Roll steps). This is intentional: plate-solving is more accurate than star-hopping through a finder.

**One Wi-Fi network, any number of clients.** PushNav's LX200 server accepts multiple connections at once, so you can have SkySafari on your phone and another LX200-compatible app on a tablet or laptop connected simultaneously — everyone sees the same live pointing.

## What's next

- [Using PushNav](using-pushnav.md) — calibration and push-to workflow (the same whether you use Stellarium, SkySafari, or anything else)
- [Stellarium Setup](stellarium-setup.md) — if you prefer the desktop Stellarium planetarium on the same machine

## Open source — please report issues

PushNav is free and open source under the GPLv3. It's been tested in real observing sessions with **Stellarium** (desktop) and **SkySafari Plus/Pro**. The Stellarium Mobile, INDI, and ASCOM paths follow the same LX200 protocol and should work out of the box, but haven't yet been field-tested against every client version.

If something doesn't work as described — or you'd like to see an app supported that isn't listed — please open an issue on the [GitHub issue tracker](https://github.com/meridianfield/pushnav/issues). Reports from real observing sessions are the best way for the project to improve.
