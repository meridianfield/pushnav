# Copyright (C) 2026 Arun Venkataswamy
#
# This file is part of PushNav.
#
# PushNav is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PushNav is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PushNav. If not, see <https://www.gnu.org/licenses/>.

"""dmgbuild settings for the PushNav release DMG.

Driven by `scripts/build_mac.sh` via two environment variables:

    PUSHNAV_APP_PATH  – absolute path to the built PushNav.app
    PUSHNAV_BG_PATH   – absolute path to marketing/dmg-background.png
                         (the @2x sibling is auto-detected by name)

We avoid create-dmg / appdmg because their AppleScript-driven Finder
layout step is unreliable on macOS Sequoia (Apple's tighter Automation
permissions cause silent failures). dmgbuild writes the .DS_Store
directly via ds-store + mac-alias and produces a stable layout.
"""

import os

app_path = os.environ["PUSHNAV_APP_PATH"]
bg_path  = os.environ["PUSHNAV_BG_PATH"]

# Files included as-is in the DMG root.
files = [app_path]

# Applications drop-target. Listed under "symlinks" so dmgbuild creates
# Applications -> /Applications inside the volume; on Sequoia the system
# folder icon may not render over the symlink, so the background image
# carries the visual cue (folder silhouette + arrow).
symlinks = {"Applications": "/Applications"}

# Icon positions in the icon-view window. (0,0) is top-left of the
# window's content area; window_rect below sizes the window to match
# the 660x400 background.
icon_locations = {
    os.path.basename(app_path): (180, 220),
    "Applications":             (480, 220),
}

# Window background — dmgbuild composes the @2x sibling automatically
# when present (marketing/dmg-background@2x.png).
background = bg_path

# Window placement (x, y) and size (w, h). 660x400 matches the bg image.
window_rect = ((100, 100), (660, 400))

icon_size = 128
text_size = 14
default_view = "icon-view"
show_status_bar  = False
show_tab_view    = False
show_toolbar     = False
show_pathbar     = False
show_sidebar     = False

# Compressed read-only DMG, same format hdiutil's UDZO produces.
format = "UDZO"
