---
title: Raspberry Pi (headless)
---

# Running PushNav headless on a Raspberry Pi

PushNav runs headless on a Raspberry Pi 3A+, 4 or 5 as the `pushnav-headless`
package. There is no window: PushNav runs in the background as a system
service, and you control it from a phone or laptop browser at
`http://<pi-address>:8765`. The laptop builds (macOS `.dmg`, Windows
installer, Linux AppImage) are separate and unchanged.

!!! info "Where to get it"
    The Pi package comes with the PushNav releases from `v0.3.0-beta6` on.
    On the [releases page](https://github.com/meridianfield/pushnav/releases),
    pick the newest release that lists `pushnav-headless_<version>_arm64.deb`
    (it may be marked *Pre-release*). It sits next to `user-data`, which
    method B below uses. If no release lists it yet,
    [build the package yourself](#build-the-package).

!!! warning "Beta"
    The Raspberry Pi package is new. It has been tested on a Raspberry Pi 5
    and a Raspberry Pi 3A+ running Raspberry Pi OS (trixie), including the
    ready-made SD card on the 3A+, and in clean Debian bookworm and trixie
    installs. The Pi 4 hasn't been tested yet but is expected to work, since
    it sits between the two. Please
    [report problems](https://github.com/meridianfield/pushnav/issues).

## Which way to install?

There are two ways to set up the Pi. Both install the same package, and
everything after the install (status light, debug mode, updates) works
the same.

| | **A. Install with apt** | **B. Ready-made PushNav SD card** |
|---|---|---|
| **Best for** | People used to setting up a Pi, or a Pi that also does other things | A dedicated PushNav box, with no command line needed |
| **Network** | Your existing Wi-Fi or Ethernet | The Pi's own Wi-Fi hotspot, `PushNav-XXXX` (no internet needed) |
| **Open PushNav at** | `http://<pi-address>:8765` | `http://192.168.77.1:8765` |
| **Setup** | Flash the card the usual way, SSH in, `apt install` the package | Flash the card, copy two files onto it, boot |
| **Raspberry Pi OS** | 64-bit, bookworm or trixie | 64-bit **Lite**, **trixie** only |

## What you need

- A **Raspberry Pi 3A+, 4 or 5** with **64-bit** Raspberry Pi OS. The Lite
  (no desktop) edition is enough. In Raspberry Pi Imager, pick a 64-bit
  OS; the package doesn't install on 32-bit. PushNav uses about 150 MB of
  memory, so even the 3A+'s 512 MB is enough.
- **Speed:** a Pi 5 solves the sample frames in under a tenth of a second
  each. A Pi 3A+ manages about 2 solves per second, which is slower but
  still fine for push-to.
- A [supported camera](hardware.md). The Waveshare, Arducam and DECXIN
  OV9281 USB modules are recognised automatically.
- A phone, tablet or laptop to open PushNav in a browser.

## A. Install with apt

For a Pi you set up yourself, on your own Wi-Fi or Ethernet.

1. Set up the Pi as usual with 64-bit Raspberry Pi OS (bookworm or trixie),
   networking and SSH, for example with Raspberry Pi Imager's OS
   customisation.
2. On the [releases page](https://github.com/meridianfield/pushnav/releases),
   download `pushnav-headless_<version>_arm64.deb` onto the Pi. For
   example, copy its link and run `wget <link>` on the Pi.
3. Install it:

    ```bash
    sudo apt install ./pushnav-headless_*_arm64.deb
    ```

    apt may print a notice that the download "is performed unsandboxed as
    root". That's normal for a local file and safe to ignore.

4. The install starts PushNav straight away, and it starts again on every
   boot. The last lines of the install show the address to open:

    ```text
    PushNav headless is installed.
      Open on your phone (same Wi-Fi):  http://192.168.0.111:8765
    ```

5. Open that address on your phone. You can plug the camera in before or
   after this; PushNav picks it up within about 10 seconds, and again if it
   is unplugged and plugged back in.

The package includes everything it needs, including its own Python, under
`/usr/lib/pushnav-headless`. It doesn't touch the Pi's system Python.

## B. Ready-made PushNav SD card

Turns a fresh SD card into a dedicated PushNav box with its own Wi-Fi
hotspot, so it works anywhere, with no router and no internet. You copy
two files onto the card after flashing it, and the Pi sets itself up on
the first boot.

Use **Raspberry Pi OS Lite**: the box has no screen, so a desktop would
only take memory away from PushNav (the 3A+ has just 512 MB) and slow the
boot. Lite is also what this setup was tested with.

1. **Download two files** from the same release on the
   [releases page](https://github.com/meridianfield/pushnav/releases):
   `pushnav-headless_<version>_arm64.deb` and `user-data`.
2. **Edit `user-data`** in a plain-text editor. Lines marked `CHANGE`:
    - the Wi-Fi **country code** (`IN` is India; use yours, e.g. `US`, `GB`,
      `DE`, `AU`). The wrong country can stop the hotspot from working.
    - the hotspot password (`pushnav123`) and the login password
      (`pushnav`), if other people may be within Wi-Fi range.

    Keep the file name exactly `user-data`, with no `.txt` or other
    extension. Some editors add one when saving.
3. **Flash the card** with [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   choose your Pi model and **Raspberry Pi OS Lite (64-bit)**, which is
   under *Raspberry Pi OS (other)*. **Skip OS customisation**: when Imager
   offers it, choose *No*.
4. **Copy the two files onto the card.** After flashing, take the card out
   and put it back in. Open the partition called `bootfs` (it contains
   `config.txt` and `cmdline.txt`) and copy both files to its **top
   level**, replacing the `user-data` that's already there.
5. **Boot the Pi** with the card and, if you have it, the camera. The first
   boot sets everything up and takes a few minutes. When PushNav is
   running, the Pi's [status light](#status-light) blinks red slowly (no
   camera) or green slowly (ready).
6. **Connect your phone** to the Wi-Fi network `PushNav-XXXX` (password
   `pushnav123`, unless you changed it) and open
   **`http://192.168.77.1:8765`**. Your phone may warn that the network has
   no internet: stay connected anyway. `http://pushnav.local:8765` also
   works on phones that support `.local` names (iPhones do; many Android
   phones don't).

To log in to the Pi, connect to the hotspot and run `ssh pi@192.168.77.1`
(password `pushnav`, unless you changed it).

The setup in `user-data` runs **only on the first boot**. To install a
newer PushNav later, see [For power users](#for-power-users-installing-a-deb-yourself),
or flash the card again with the new files.

## Connect planetarium apps

Use the Pi's address: `192.168.77.1` with the ready-made SD card (B), or
the Pi's address on your network with apt (A). The Connectivity section of
the PushNav page shows the exact addresses to use.

- **SkySafari or Stellarium Mobile:** add a telescope of type *Meade LX200
  Classic* over Wi-Fi/TCP at the Pi's address, port `4030`. See
  [SkySafari & Other Apps](skysafari-setup.md).
- **Stellarium (desktop):** use the Stellarium telescope plugin at the Pi's
  address, port `10001`. See [Stellarium Setup](stellarium-setup.md).

## Status light

With no screen attached, the Pi's own LEDs show what PushNav is doing.
**Red means it needs your attention; green means it's working.**

| What you see | What it means | What to do |
|---|---|---|
| Red, slow blink | No camera found, or PushNav is trying to reconnect to it | Check the camera cable |
| Red, steady | The camera was unplugged while in use, and reconnecting failed | Plug the camera back in: PushNav finds it within about 10 seconds |
| Green, slow blink | Ready, needs a sync | Open the page and run the sync wizard |
| Green, short flash every 3 seconds | Tracking, all good | Nothing: enjoy observing |
| Green, fast blink | Lost the stars | Check where the scope points, or for dew on the lens |
| Three quick green blinks, once | A phone, Stellarium or SkySafari just connected, or sent a target | Nothing: PushNav got it |

The "all good" flash is deliberately brief, so it doesn't spoil your
night vision. After a target or a new connection's three quick blinks,
the light goes back to its pattern.

While the Pi boots, and whenever PushNav isn't running, the LEDs behave
as they normally do on a Pi. When PushNav starts, they go dark for a few
seconds (up to about 20 seconds on a Pi 3A+) until it's ready and the
status light takes over.

On a Pi with only a green LED (such as the Pi Zero 2 W), "no camera" is
a green double blink and "camera unplugged while in use" is steady green.

Good to know:

- Some Pi cases hide the LEDs. A case with a window or light pipe over
  them makes the status light visible.
- While PushNav runs, the green LED no longer flickers with SD card
  activity. On a Pi 4, the red LED also stops warning about a weak power
  supply.
- To turn the status light off, set `"led": {"enabled": false}` in
  `config.json` (see below), then run
  `sudo systemctl restart pushnav-headless`.

## Debug mode

Debug mode adds a Debug panel at the bottom of the PushNav page. Its
sample star images stand in for the camera, so you can try the sync
wizard indoors or check a setup without a clear sky. The panel can also
save the current camera frame (to `/var/lib/pushnav-headless/Downloads`
on the Pi).

To turn it on, put a jumper across **pin 39 (GND) and pin 40 (GPIO21)**,
the last two pins of the 40-pin header, at the opposite end from pin 1:

```text
            pin 1 end ...  37  ●  ●  38
                           39  ●  ●  40   ← jumper across these two
                               GND  GPIO21
```

Then restart PushNav: power-cycle the Pi, or run
`sudo systemctl restart pushnav-headless`. To turn debug mode off, remove
the jumper and restart again. PushNav checks the jumper only when it
starts.

- Use only pins 39 and 40. Never connect a GPIO pin to the 5 V pins.
- A HAT that uses GPIO21 (some I2S audio boards do) leaves debug mode
  off, because PushNav can't read the pin.
- To see what the Pi reads, run
  `sudo /usr/lib/pushnav-headless/python/bin/python3 -m evf.engine.debug_pin --check`.

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

## For power users: installing a .deb yourself

These work the same with both setups. Log in to the Pi over SSH first
(`ssh pi@192.168.77.1` on the hotspot of a ready-made card).

### Get the .deb onto the Pi

- **Over the network**, from a laptop on the same network or hotspot:
  `scp pushnav-headless_<version>_arm64.deb pi@<pi-address>:`
- **On the SD card**, from a PC: copy it to the boot partition. On the Pi
  it is then in `/boot/firmware/`.

A ready-made card installs the `.deb` it finds **only on its first boot**.
A `.deb` you copy onto it later has to be installed with the commands
below.

### Install, update or reinstall

| What | Command |
|---|---|
| Install, or update to a newer version | `sudo apt install ./pushnav-headless_<version>_arm64.deb` |
| Install the same version again | add `--reinstall` |
| Go back to an older version, or install a local build | add `--allow-downgrades` |
| Install a copy from the boot partition | `sudo apt install /boot/firmware/pushnav-headless_<version>_arm64.deb` |
| Which version is installed? | `dpkg-query -W pushnav-headless` |

Settings and calibration are kept, and if you disabled starting at boot,
that stays disabled.

- **No internet needed:** the package depends only on `libjpeg62-turbo`,
  `adduser` and `libc6` (2.36 or newer), which Raspberry Pi OS already has.
- **File names:** a release download is named `…0.3.0.beta6-1…` where a
  local build is named `…0.3.0~beta6-1…`. Both are fine: apt reads the
  version from inside the file.

### More settings

- **Verbose logging:** set `"logging": {"verbose": true}` in `config.json`
  (see [Managing the service](#managing-the-service)), then restart the
  service.
- **Debug mode without the jumper:** add a systemd override.

    ```bash
    sudo mkdir -p /etc/systemd/system/pushnav-headless.service.d
    printf '[Service]\nEnvironment=PUSHNAV_DEBUG=1\n' | \
        sudo tee /etc/systemd/system/pushnav-headless.service.d/debug.conf
    sudo systemctl daemon-reload && sudo systemctl restart pushnav-headless
    ```

    To turn it off again, `sudo rm -r /etc/systemd/system/pushnav-headless.service.d`,
    then the same `daemon-reload` and `restart`.
- **Status light off:** see [Status light](#status-light).

### Ready-made card: going online

The hotspot has no internet. To update Raspberry Pi OS or download a
release directly on the Pi, put it on your home Wi-Fi for a while:

```bash
sudo nmcli con add type wifi ifname wlan0 con-name home \
    ssid "<your Wi-Fi name>" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "<password>"
sudo nmcli con mod hotspot connection.autoconnect no
sudo nmcli con up home    # the SSH session drops here
```

The Pi is then on your home network, as `pushnav.local` or at the address
your router shows. When you're done, switch back to the hotspot:

```bash
sudo nmcli con mod home connection.autoconnect no
sudo nmcli con mod hotspot connection.autoconnect yes
sudo nmcli con up hotspot    # the SSH session drops again
```

## Uninstall

```bash
sudo apt remove pushnav-headless   # remove PushNav, keep settings and calibration
sudo apt purge pushnav-headless    # remove everything, including the pushnav user
```

## Troubleshooting

**Ready-made card: no `PushNav-XXXX` network appears.** Give the first
boot a few minutes. Then check that the card has Raspberry Pi OS Lite
(64-bit, trixie), that `user-data` is at the top level of `bootfs` with
exactly that name (no `.txt`), and that the country code in it is right.

**Ready-made card: the hotspot works but PushNav doesn't open.** If the
Pi's LEDs show their normal behaviour instead of the
[status light](#status-light), PushNav wasn't installed, usually because
the `.deb` wasn't on the card. Log in with `ssh pi@192.168.77.1`, check
`sudo grep -n "PushNav .deb" /var/log/cloud-init-output.log`, and
[install the `.deb` by hand](#for-power-users-installing-a-deb-yourself).

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

Not there yet:

- No single ready-to-flash image: the [ready-made SD card](#b-ready-made-pushnav-sd-card)
  needs two files copied onto it after flashing.
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

A run from source leaves the LEDs alone, because only the service is
given access to them. To try the status light from source, hand the
LEDs to your user first, then give them back when you're done:

```bash
sudo .venv/bin/python -s -m evf.engine.led_helper take --group "$(id -gn)"
# ... run PushNav as above ...
sudo .venv/bin/python -s -m evf.engine.led_helper restore
```

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

The ready-made SD card's first-boot configuration is
`packaging/headless/user-data`; CI attaches it to each release next to the
`.deb`, and `tests/test_headless_user_data.py` checks it.
