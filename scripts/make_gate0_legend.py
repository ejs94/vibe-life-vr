#!/usr/bin/env python3
"""Compose labeled evidence sheets from the fixed-camera Gate 0 captures."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "out/evidence/gate0c/monado_20261024_205048"
THUMB = REPO / "out/evidence/gate0c_thumb/monado_20261024_204953"

FONT = ImageFont.load_default()
TITLE_FONT = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 30)
CAPTION_FONT = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 17)
BG = (20, 22, 27)
FG = (232, 235, 240)
ACCENT = (255, 190, 70)
CELL_W, CELL_H = 420, 473
PAD = 18
CAP_H = 62


def load(path: Path, cell_h: int = CELL_H) -> Image.Image:
    image = Image.open(path).convert("RGB")
    return image.resize((CELL_W, cell_h), Image.Resampling.LANCZOS)


def make_sheet(title: str, rows: list[list[tuple[Path, str]]], out: Path, cell_h: int = CELL_H) -> None:
    cols = max(len(row) for row in rows)
    width = PAD + cols * (CELL_W + PAD)
    height = 86 + len(rows) * (cell_h + CAP_H + PAD) + PAD
    sheet = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(sheet)
    draw.text((PAD, 24), title, fill=ACCENT, font=TITLE_FONT)

    for row_idx, row in enumerate(rows):
        y = 86 + row_idx * (CELL_H + CAP_H + PAD)
        for col_idx, (path, caption) in enumerate(row):
            x = PAD + col_idx * (CELL_W + PAD)
            if not path.exists():
                draw.rectangle([x, y, x + CELL_W, y + cell_h], outline=(180, 60, 60), width=3)
                draw.text((x + 8, y + 8), f"missing:\n{path.name}", fill=(255, 120, 120), font=CAPTION_FONT)
                continue
            sheet.paste(load(path, cell_h), (x, y))
            draw.rectangle([x, y, x + CELL_W, y + cell_h], outline=(60, 65, 75), width=2)
            # Wrap the caption to two short lines if needed.
            words = caption.split()
            lines, current = [], ""
            for word in words:
                probe = (current + " " + word).strip()
                if draw.textlength(probe, font=CAPTION_FONT) > CELL_W - 8 and current:
                    lines.append(current)
                    current = word
                else:
                    current = probe
            if current:
                lines.append(current)
            for line_idx, line in enumerate(lines[:2]):
                draw.text((x + 2, y + cell_h + 6 + line_idx * 22), line, fill=FG, font=CAPTION_FONT)

    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"Wrote {out.relative_to(REPO)} ({width}x{height})")


def crossbow_sheet() -> None:
    rows = []
    for angle, suffix in (("lateral", "lat"), ("top", "top")):
        rows.append(
            [
                (GATE / f"gate0c_crossbow_hide0_curloff_{suffix}.png",
                 f"Crossbow . hide 0 baked MMOD . curling OFF . {angle}"),
                (GATE / f"gate0c_crossbow_hide0_indexonly_{suffix}.png",
                 f"Crossbow . hide 0 baked MMOD . INDEX ONLY . {angle}"),
                (GATE / f"gate0c_crossbow_hide0_current_{suffix}.png",
                 f"Crossbow . hide 0 baked MMOD . CURRENT . {angle}"),
            ]
        )
    make_sheet("Crossbow baked hand . fixed camera . hide/curling/angle", rows,
               GATE / "legend_crossbow_hide0.png")

    rows = [[
        (GATE / "gate0c_crossbow_hide2_current_lat.png",
         "Crossbow . hide 2 standalone Rimrook . current . lateral"),
        (GATE / "gate0c_crossbow_hide2_current_top.png",
         "Crossbow . hide 2 standalone Rimrook . current . top"),
    ]]
    make_sheet("Crossbow standalone Rimrook . fixed camera", rows,
               GATE / "legend_crossbow_hide2.png")


def thumb_sheet() -> None:
    rows = []
    for angle, suffix in (("lateral", "lat"), ("top", "top")):
        rows.append(
            [
                (THUMB / f"gate0c_thumb_curl0_{suffix}.png",
                 f"Rimrook primary . thumb local -Z . CURL 0.0 (rest) . {angle}"),
                (THUMB / f"gate0c_thumb_curl05_{suffix}.png",
                 f"Rimrook primary . thumb local -Z . CURL 0.5 . {angle}"),
                (THUMB / f"gate0c_thumb_curl1_{suffix}.png",
                 f"Rimrook primary . thumb local -Z . CURL 1.0 . {angle}"),
                (THUMB / f"gate0c_thumb_legacyY_curl1_{suffix}.png",
                 f"Rimrook primary . LEGACY local Y . CURL 1.0 . {angle}"),
            ]
        )
    make_sheet("Rimrook thumb . fixed camera . weapon hidden . 0 / 0.5 / 1 vs legacy Y", rows,
               THUMB / "legend_thumb.png")


def crossbow_crop_sheet() -> None:
    crops = GATE / "crops"
    rows = [[
        (crops / "crossbow_hide0_curloff_crop.png",
         "Crossbow . hide 0 baked MMOD . curling OFF . same lateral crop"),
        (crops / "crossbow_hide0_indexonly_crop.png",
         "Crossbow . hide 0 baked MMOD . INDEX ONLY . same lateral crop"),
        (crops / "crossbow_hide0_current_crop.png",
         "Crossbow . hide 0 baked MMOD . CURRENT . same lateral crop"),
    ]]
    make_sheet("Crossbow baked hand . hand-region crop . curling comparison", rows,
               GATE / "legend_crossbow_hide0_crops.png", cell_h=304)


if __name__ == "__main__":
    crossbow_sheet()
    crossbow_crop_sheet()
    thumb_sheet()
