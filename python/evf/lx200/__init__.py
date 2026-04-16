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

"""LX200 Classic TCP server package.

Speaks a minimal LX200 command subset on port 4030, serving SkySafari,
Stellarium Mobile PLUS, INDI lx200basic, and ASCOM Meade Generic clients.
See specs/start/SPEC_PROTOCOL_LX200.md for wire-format details.
"""
