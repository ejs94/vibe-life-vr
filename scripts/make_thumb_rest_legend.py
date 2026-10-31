#!/usr/bin/env python3
"""Build the labeled Rimrook thumb rest comparison sheet."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
OLD = REPO / "out/evidence/gate0c_thumb/monado_20261024_204953"
NEW = REPO / "out/evidence/gate0c_thumb_rest/monado_20261024_221700"
OUT = REPO / "out/evidence/gate0c_thumb_rest/legend_thumb_rest_crops.png"
CROP = (40, 250, 720, 700)

FONT = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 18)
TITLE = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 28)
CW, CH, PAD = 520, 345, 16


def main() -> None:
    rows = [("ORIGINAL rest", OLD), ("REPOSED rest (12/6)", NEW)]
    width = PAD + 3 * (CW + PAD)
    height = 76 + len(rows) * (CH + 56 + PAD) + PAD
    sheet = Image.new("RGB", (width, height), (20, 22, 27))
    draw = ImageDraw.Draw(sheet)
    draw.text((PAD, 18), "Rimrook thumb rest re-pose . lateral crop . curl 0 / 0.5 / 1",
              fill=(255, 190, 70), font=TITLE)

    for row, (label, base) in enumerate(rows):
        y = 76 + row * (CH + 56 + PAD)
        for col, (suffix, curl) in enumerate((("curl0", "0.0"), ("curl05", "0.5"), ("curl1", "1.0"))):
            x = PAD + col * (CW + PAD)
            path = base / f"gate0c_thumb_{suffix}_lat.png"
            image = Image.open(path).convert("RGB").crop(CROP).resize((CW, CH), Image.Resampling.LANCZOS)
            sheet.paste(image, (x, y))
            draw.rectangle([x, y, x + CW, y + CH], outline=(70, 75, 85), width=2)
            draw.text((x + 2, y + CH + 6), f"{label} . curl {curl}",
                      fill=(232, 235, 240), font=FONT)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT)
    print(f"Wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
