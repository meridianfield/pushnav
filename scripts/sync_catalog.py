#!/usr/bin/env python3
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

"""Sync the catalog JSON from the Stargazing Buddy site repo.

Reads ~/Devel/Github/stargazing-buddy-site/src/content/objects/*.md,
parses YAML frontmatter + body, writes web/src/data/objects.json.

Run manually whenever the buddy-site catalog changes:

    python scripts/sync_catalog.py

The output JSON is sorted by id for stable diffs.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BUDDY_SITE = Path.home() / "Devel" / "Github" / "stargazing-buddy-site"
SOURCE_DIR = BUDDY_SITE / "src" / "content" / "objects"
OUTPUT = REPO_ROOT / "web" / "src" / "data" / "objects.json"

# Required frontmatter keys we depend on; entries missing any of these are
# logged and skipped rather than corrupting the JSON.
REQUIRED = (
    "name", "designation", "type", "constellation",
    "difficulty", "visualReward", "lpTolerance", "minEquipment",
    "rightAscension", "declination",
)

# Cap each description body to keep the bundle small and the detail
# panel rendering quick.
DESCRIPTION_MAX_CHARS = 600


def parse_markdown(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter (---…---) from body. Returns ({}, '') on failure."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, ""
    front = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)
    return front, body


def strip_markdown(body: str) -> str:
    """Reduce markdown body to plain prose: drop HTML tags, tables, headings,
    image refs, and code blocks. Collapse blank lines, return up to
    DESCRIPTION_MAX_CHARS."""
    # Drop fenced code blocks
    body = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    # Drop HTML blocks (img, div, p tags)
    body = re.sub(r"<[^>]+>", "", body)
    # Drop image references ![alt](url)
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)
    # Drop reference-style tables (lines starting with | )
    body = "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith("|")
    )
    # Drop heading lines
    body = re.sub(r"^#+ .*$", "", body, flags=re.MULTILINE)
    # Drop "Finder map for ..." caption lines (figure caption, no value as prose)
    body = re.sub(r"^Finder map for .*$", "", body, flags=re.MULTILINE)
    # Drop link syntax keep text: [text](url) -> text
    body = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", body)
    # Collapse multiple blank lines and trim
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if len(body) > DESCRIPTION_MAX_CHARS:
        body = body[: DESCRIPTION_MAX_CHARS - 1].rsplit(" ", 1)[0] + "…"
    return body


def build_entry(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    front, body = parse_markdown(text)

    missing = [k for k in REQUIRED if k not in front]
    if missing:
        print(
            f"  SKIP {path.name}: missing required keys {missing}",
            file=sys.stderr,
        )
        return None

    return {
        "id": path.stem,
        "name": front["name"],
        "designation": front["designation"],
        "type": front["type"],
        "subtype": front.get("subtype"),
        "constellation": front["constellation"],
        "magnitude": front.get("magnitude"),
        "distance": front.get("distance"),
        "bestViewing": front.get("bestViewing"),
        "difficulty": front["difficulty"],
        "visualReward": front["visualReward"],
        "lpTolerance": front["lpTolerance"],
        "minEquipment": front["minEquipment"],
        "rightAscension": front["rightAscension"],
        "declination": front["declination"],
        "description": strip_markdown(body),
    }


def main() -> int:
    if not SOURCE_DIR.exists():
        print(f"ERROR: buddy-site source dir not found at {SOURCE_DIR}", file=sys.stderr)
        return 1

    md_files = sorted(SOURCE_DIR.glob("*.md"))
    print(f"Reading {len(md_files)} markdowns from {SOURCE_DIR}")

    entries: list[dict] = []
    for path in md_files:
        entry = build_entry(path)
        if entry is not None:
            entries.append(entry)

    entries.sort(key=lambda e: e["id"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {len(entries)} objects to {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
