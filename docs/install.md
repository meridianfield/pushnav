---
title: Install PushNav
---

# Install PushNav

PushNav runs on macOS, Windows, and Linux. Pick your platform below, and you'll be up and running in a few minutes.

## Download

Grab the latest release from GitHub:

[:material-download: Download PushNav](https://github.com/meridianfield/pushnav/releases/latest){ .md-button .md-button--primary }

| Platform | What to download |
|---|---|
| **Windows** | `PushNav-windows-x64-setup.exe` |
| **macOS** (Apple Silicon — M1/M2/M3/M4) | `PushNav-macOS-arm64.dmg` |
| **Linux** | `PushNav-linux-x86_64.AppImage` |

---

## Windows

### Install

1. Run the downloaded `PushNav-windows-x64-setup.exe`
2. Click **Yes** when Windows asks for permission to install
3. Follow the installer — the defaults are fine
4. PushNav appears in your **Start Menu**

### First launch — firewall prompt

The first time PushNav starts, Windows Firewall will ask if you want to allow PushNav to communicate on your network. **Tick "Private networks"** and click **Allow access**. This lets other devices on your Wi-Fi — your phone for the mobile companion view, and telescope apps like SkySafari — connect to PushNav.

!!! note "If PushNav won't start at all"
    If you see an error about a missing `.dll` file, you may need to install the [Microsoft Visual C++ Runtime](https://aka.ms/vs/17/release/vc_redist.x64.exe) (a one-time, free download from Microsoft). Most Windows 10/11 machines already have it.

---

## macOS

### Install

1. Open the downloaded `.dmg` file
2. Drag **PushNav** into your **Applications** folder

### First launch — security prompts

Because PushNav is a free, open-source app and isn't sold through the Mac App Store, macOS will show a couple of prompts the first time you open it. This is normal.

**Security warning** — macOS will say it can't verify the developer:

- **macOS 14 and earlier**: Right-click PushNav in Applications → click **Open** → click **Open** again in the confirmation dialog
- **macOS 15 (Sequoia) and later**: Double-click PushNav (it will be blocked), then go to **System Settings → Privacy & Security**, scroll down, and click **Open Anyway**

You only need to do this once.

**Camera access** — macOS will ask if PushNav can use your camera. Click **Allow**. PushNav needs the camera to see the stars.

**Network access** — macOS will ask if PushNav can accept incoming network connections. Click **Allow**. This lets other devices on your Wi-Fi — your phone for the mobile companion view, and telescope apps like SkySafari — connect to PushNav.

---

## Linux

### Install

1. Download the `.AppImage` file
2. Make it executable and run it:
   ```bash
   chmod +x PushNav-linux-*.AppImage
   ./PushNav-linux-*.AppImage
   ```

The AppImage is self-contained — everything PushNav needs is bundled inside.

### Camera permission

If PushNav can't find your camera, you may need to add yourself to the `video` group (this is a one-time step):

```bash
sudo usermod -a -G video $USER
```

Log out and back in for the change to take effect.

---

## Before you launch

**Plug in your USB camera before starting PushNav.** The app looks for the camera at startup and won't continue without one.

When PushNav starts, you'll see a brief loading screen, then the main window with a live camera feed on the left and a step-by-step panel on the right. The panel walks you through alignment — no prior experience needed.

## Phone companion

PushNav has a built-in mobile view so you can check your push direction from your phone while you're at the eyepiece. No app to install — just scan a QR code.

1. Open the **Settings** section in PushNav's side panel
2. Point your phone's camera at the **QR code** shown there
3. Tap the link that pops up — a live view opens in your phone's browser

Your phone and laptop need to be on the same Wi-Fi network. That's it.

!!! tip "If your phone can't connect"
    You probably clicked "Deny" or "Cancel" on the firewall/network prompt when PushNav first launched. See the macOS or Windows sections above for how to fix it.

---

## What's next

Now that PushNav is running, connect it to Stellarium so you can pick targets from a sky chart and have PushNav guide you to them. See [Stellarium Setup](stellarium-setup.md).
