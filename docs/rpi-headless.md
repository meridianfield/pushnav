---
title: Raspberry Pi (headless)
---

# Running PushNav headless on a Raspberry Pi

PushNav runs headless on a Raspberry Pi 3A+, 4 or 5 as the `pushnav-headless`
package. There is no window: PushNav runs in the background as a system
service, and you control it from a phone or laptop browser on the same
Wi-Fi at `http://<pi-ip>:8765`. The laptop builds (macOS `.dmg`, Windows
installer, Linux AppImage) are separate and unchanged.

!!! info "Not in a release yet"
    Raspberry Pi support is on the `main` branch but isn't part of a
    published release yet. It will be included in the next release. Until
    then, [build the package yourself](#build-the-package) on the Pi and
    install it as described below.

!!! warning "Beta"
    The Raspberry Pi package is new. It has been tested on a Raspberry Pi 5
    running Raspberry Pi OS (trixie), on a Raspberry Pi 3A+, and in clean
    Debian bookworm and trixie installs. The Pi 4 hasn't been tested yet but
    is expected to work, since it sits between the two. Please
    [report problems](https://github.com/meridianfield/pushnav/issues).

## What you need

- A **Raspberry Pi 3A+, 4 or 5** running **64-bit** Raspberry Pi OS, either
  bookworm or trixie. The Lite (no desktop) edition is enough. In Raspberry
  Pi Imager, pick the 64-bit OS; the package doesn't install on 32-bit.
  PushNav uses about 150 MB of memory, so even the 3A+'s 512 MB is enough.
- **Speed:** a Pi 5 solves the sample frames in under a tenth of a second
  each. A Pi 3A+ manages about 2 solves per second, which is slower but
  still fine for push-to.
- A [supported camera](hardware.md). The Waveshare, Arducam and DECXIN
  OV9281 USB modules are recognised automatically.
- A phone, tablet or laptop on the same network as the Pi.

## Install

1. On the [releases page](https://github.com/meridianfield/pushnav/releases),
   find the newest release that lists `pushnav-headless_<version>_arm64.deb`
   (it may be marked *Pre-release*) and download it onto the Pi. For
   example, copy its link and run `wget <link>` on the Pi. If no release
   lists it yet, build it yourself instead (see the note at the top).
2. Install it:

    ```bash
    sudo apt install ./pushnav-headless_*_arm64.deb
    ```

    apt may print a notice that the download "is performed unsandboxed as
    root". That's normal for a local file and safe to ignore.

3. The install starts PushNav straight away, and it starts again on every
   boot. The last lines of the install show the address to open:

    ```text
    PushNav headless is installed.
      Open on your phone (same Wi-Fi):  http://192.168.0.111:8765
    ```

4. Open that address on your phone. You can plug the camera in before or
   after this; PushNav picks it up within about 10 seconds, and again if it
   is unplugged and plugged back in.

The package includes everything it needs, including its own Python, under
`/usr/lib/pushnav-headless`. It doesn't touch the Pi's system Python.

## Connect planetarium apps

- **SkySafari or Stellarium Mobile:** add a telescope of type *Meade LX200
  Classic* over Wi-Fi/TCP at `<pi-ip>`, port `4030`. See
  [SkySafari & Other Apps](skysafari-setup.md).
- **Stellarium (desktop):** use the Stellarium telescope plugin at
  `<pi-ip>`, port `10001`. See [Stellarium Setup](stellarium-setup.md).

## Managing the service

| Task | Command |
|---|---|
| Is it running? | `systemctl status pushnav-headless` |
| Watch the log | `journalctl -u pushnav-headless -f` |
| Stop / start / restart | `sudo systemctl stop pushnav-headless` (or `start` / `restart`) |
| Don't start at boot | `sudo systemctl disable pushnav-headless` |
| Start at boot again | `sudo systemctl enable pushnav-headless` |

PushNav runs as its own `pushnav` system user. Its files are in
`/var/lib/pushnav-headless`:

- Settings and calibration: `config/electronic-viewfinder/config.json`
- Log file: `state/electronic-viewfinder/logs/evf.log`

Settings you change in the web UI are saved there automatically. If you
edit `config.json` by hand, restart the service afterwards.

## Update

Download the newer `.deb` and install it the same way. Your settings and
calibration are kept, and if you disabled starting at boot, that stays
disabled.

```bash
sudo apt install ./pushnav-headless_<new-version>_arm64.deb
```

## Uninstall

```bash
sudo apt remove pushnav-headless   # remove PushNav, keep settings and calibration
sudo apt purge pushnav-headless    # remove everything, including the pushnav user
```

## Troubleshooting

**The log says "Waiting for camera".** No USB camera is detected. Check the
cable and run `lsusb`: a supported camera appears as `32e6:9251`,
`0c45:6366` or `1bcf:2cd1`. A camera with a different ID can be added in
`config.json` as `"camera": {"extra_camera_ids": ["1234:abcd"], ...}`
(then restart the service).

**USB devices stop being detected at all.** On some Pis the USB controller
can fail until the next reboot. If `lsusb` lists nothing but hubs, check
`journalctl -k | grep "HC died"`, then reboot.

**"PushNav is already running on port 8765" when you run `pushnav-headless`
by hand.** The service is already running. Stop it first with
`sudo systemctl stop pushnav-headless`.

**The phone can't open the address.** The phone and Pi must be on the same
network. A Pi on Ethernet and a phone on Wi-Fi usually works on a home
router. Guest or public Wi-Fi networks often block devices from reaching
each other.

**No sound.** The lock / lost / target sounds play on the Pi itself, which
usually has no speaker. That doesn't affect anything else.

## Limitations

These are planned for a later "appliance" version:

- No Wi-Fi hotspot: the Pi has to join an existing network, set up the
  usual way (Raspberry Pi Imager, `raspi-config` or `nmcli`).
- No `pushnav.local` address: type the Pi's IP into the browser.
- No ready-to-flash SD card image.
- No shutdown button in the web UI: use `sudo shutdown now` over SSH.

## For developers

### Run from source

```bash
sudo apt install -y gcc libjpeg-dev nodejs npm   # Node 20.19+ for the web build
# install uv: https://docs.astral.sh/uv/getting-started/installation/
git clone git@github.com:meridianfield/pushnav.git
cd pushnav
uv sync --no-group desktop     # no pywebview / PyQt6 needed headless
make -C camera/linux
(cd web && npm install && npm run build)
uv run --no-group desktop python -m evf.main --no-window
```

Your user needs to be in the `video` group to open the camera
(`sudo usermod -aG video "$USER"`, then log out and back in). Stop the
`pushnav-headless` service first if it's installed, because both use the
same ports.

### Build the package

```bash
scripts/build_headless_deb.sh            # in a Debian bookworm arm64 container (Docker)
scripts/build_headless_deb.sh --host     # directly on a Pi, for quick iteration
scripts/smoke_test_headless_deb.sh       # install + run test on bookworm and trixie
```

The container build is the release path. It compiles the camera server
against bookworm's C library so one package runs on bookworm and trixie.
On an x86 PC, Docker runs the arm64 image under QEMU, which works but is
slow. CI builds the package on a native ARM runner and attaches it to
each release.
