#!/usr/bin/env python3
"""Assemble the weapon sweep captures into one labelled contact sheet.

Rows are weapons, columns are the fixed comparison cameras (right lateral,
front, top). Every cell is labelled with the model name so a capture can be
judged without opening the run directory.

Usage:
    python3 scripts/make_weapon_contact_sheet.py <capture_dir> [--out sheet.png]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[FAIL] Pillow is required for the contact sheet", file=sys.stderr)
    raise SystemExit(1)

VIEWS = ("right", "front", "left")
CELL_W = 420
LABEL_H = 26
LABEL_W = 190


def load_font(size: int):
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_dir")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    run_dir = Path(args.capture_dir)
    pngs = sorted(run_dir.glob("w_*_right.png"))
    if not pngs:
        print(f"[FAIL] no w_*_right.png captures under {run_dir}")
        return 1

    font = load_font(16)
    small = load_font(13)

    rows = []
    for lat in pngs:
        base = lat.name[: -len("_right.png")]
        cells = {view: run_dir / f"{base}_{view}.png" for view in VIEWS}
        if not all(path.is_file() for path in cells.values()):
            continue
        rows.append((base, cells))
    if not rows:
        print("[FAIL] no complete capture triples found")
        return 1

    sample = Image.open(rows[0][1]["right"]).convert("RGB")
    scale = CELL_W / sample.width
    cell_h = int(sample.height * scale)

    width = LABEL_W + CELL_W * len(VIEWS)
    height = LABEL_H + len(rows) * (cell_h + LABEL_H)
    sheet = Image.new("RGB", (width, height), (12, 12, 14))
    draw = ImageDraw.Draw(sheet)

    for column, view in enumerate(VIEWS):
        draw.text((LABEL_W + column * CELL_W + 8, 4), view.upper(),
                  fill=(240, 240, 240), font=font)

    for row_index, (base, cells) in enumerate(rows):
        y = LABEL_H + row_index * (cell_h + LABEL_H)
        draw.text((10, y + LABEL_H + 6), base, fill=(255, 210, 90), font=font)
        for column, view in enumerate(VIEWS):
            image = Image.open(cells[view]).convert("RGB").resize((CELL_W, cell_h))
            sheet.paste(image, (LABEL_W + column * CELL_W, y + LABEL_H))

    out_path = Path(args.out) if args.out else run_dir / "contact_sheet.png"
    sheet.save(out_path)
    print(f"[info] {len(rows)} weapons, {len(VIEWS)} views")
    print(f"[PASS] contact sheet: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
