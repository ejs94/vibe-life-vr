#!/usr/bin/env python3
"""Reject empty or black weapon captures before they are judged by eye.

A contact sheet is only useful if every cell actually contains a rendered
weapon. This check fails when a capture is missing, is almost entirely one
colour (black screen, failed dump, camera inside the map), or when the
foreground does not cover enough pixels to be inspected.

Usage:
    python3 scripts/check_weapon_captures.py <capture_dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image, ImageStat
except ImportError:
    print("[FAIL] Pillow is required", file=sys.stderr)
    raise SystemExit(1)

VIEWS = ("right", "front", "left")
MIN_STDDEV = 12.0        # a flat frame has no weapon on it
MIN_FOREGROUND = 0.005   # 0.5% of pixels must differ from the modal colour


def inspect(path: Path):
    image = Image.open(path).convert("RGB")
    stat = ImageStat.Stat(image)
    stddev = sum(stat.stddev) / 3.0

    small = image.resize((160, 160))
    counts = small.getcolors(160 * 160)
    if not counts:
        return 0.0, stddev
    modal = max(counts, key=lambda item: item[0])[1]
    if hasattr(small, "get_flattened_data"):
        pixels = list(small.get_flattened_data())
    else:
        pixels = list(small.getdata())
    background = sum(1 for p in pixels if sum(abs(p[i] - modal[i]) for i in range(3)) < 24)
    return 1.0 - background / len(pixels), stddev


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_weapon_captures.py <capture_dir>")
        return 2

    run_dir = Path(sys.argv[1])
    rights = sorted(run_dir.glob("w_*_right.png"))
    failures: list[str] = []

    if not rights:
        print(f"[FAIL] no captures under {run_dir}")
        return 1

    for right in rights:
        base = right.name[: -len("_right.png")]
        for view in VIEWS:
            path = run_dir / f"{base}_{view}.png"
            if not path.is_file():
                failures.append(f"{base}: missing {view} capture")
                continue
            foreground, stddev = inspect(path)
            if stddev < MIN_STDDEV or foreground < MIN_FOREGROUND:
                failures.append(
                    f"{base}/{view}: empty frame (stddev={stddev:.1f}, "
                    f"foreground={foreground:.2%})"
                )

    sheet = run_dir / "contact_sheet.png"
    if not sheet.is_file():
        failures.append("contact_sheet.png was not generated")

    for failure in failures:
        print(f"[FAIL] {failure}")

    if failures:
        print(f"WEAPON CAPTURE CHECKS FAILED ({len(failures)} issue(s))")
        return 1
    print(f"WEAPON CAPTURE CHECKS PASSED ({len(rights)} weapons, {len(rights) * len(VIEWS)} captures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
