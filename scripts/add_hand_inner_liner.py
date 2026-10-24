#!/usr/bin/env python3
"""Add a dark inner liner to the two-hand VR hand model.

The Rimrook hand is a single-sided glove shell. The inside of the glove/sleeve
is visible through the wrist opening and reads as the same bright surface as
the outside. This script duplicates every glove and sleeve triangle with a
black material, offsets the duplicate slightly along the inward normal, flips
its winding/normal, and recompiles the MDL.

Usage:
  scripts/add_hand_inner_liner.py \
      --input out/twohand --output out/twohand_liner --compile
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smd_lib  # noqa: E402

INNER_MATERIAL = "glove_inner.bmp"
INNER_COLOR = (10, 10, 10)


def make_inner_texture(path: str) -> None:
    from PIL import Image

    img = Image.new("P", (64, 64), 0)
    palette = []
    for i in range(256):
        palette.extend(INNER_COLOR if i == 0 else (0, 0, 0))
    img.putpalette(palette)
    img.save(path)


def add_liner(src: smd_lib.Smd, inset: float) -> smd_lib.Smd:
    out = smd_lib.Smd(nodes=list(src.nodes), skeleton=list(src.skeleton),
                      triangles=list(src.triangles))

    for tri in src.triangles:
        if not tri.verts:
            continue
        if tri.material not in ("glove_texture.bmp", "gordon_sleeve.bmp"):
            continue

        verts = []
        # Reverse the winding and negate the normals so the new surface faces
        # into the glove. Insetting along the normal keeps it just behind the
        # outer shell, avoiding z-fighting.
        for vert in reversed(tri.verts):
            n = vert.normal
            length = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) ** 0.5
            if length > 1e-6:
                n = (n[0] / length, n[1] / length, n[2] / length)
            else:
                n = (0.0, 0.0, 0.0)
            pos = (
                vert.pos[0] - n[0] * inset,
                vert.pos[1] - n[1] * inset,
                vert.pos[2] - n[2] * inset,
            )
            verts.append(smd_lib.Vertex(vert.parent, pos,
                                        (-n[0], -n[1], -n[2]), vert.uv))

        out.triangles.append(smd_lib.Triangle(INNER_MATERIAL, verts))

    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="out/twohand", help="directory with hand_r.smd, hand_l.smd, textures and v_hand.qc")
    parser.add_argument("--output", default="out/twohand_liner", help="output directory")
    parser.add_argument("--inset", type=float, default=0.08, help="inward offset in model units")
    parser.add_argument("--compile", action="store_true", help="run pxstudiomdl after writing the SMDs")
    parser.add_argument("--pxstudiomdl", default="out/pxstudiomdl/pxstudiomdl")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    for name in ("hand_r.smd", "hand_l.smd"):
        src = smd_lib.parse_smd(os.path.join(args.input, name))
        smd_lib.write_smd(os.path.join(args.output, name), add_liner(src, args.inset))

    for name in ("glove_texture.bmp", "gordon_sleeve.bmp", "v_hand.qc"):
        source_path = os.path.join(args.input, name)
        if os.path.isfile(source_path):
            shutil.copyfile(source_path, os.path.join(args.output, name))

    make_inner_texture(os.path.join(args.output, INNER_MATERIAL))

    if args.compile:
        subprocess.run([os.path.abspath(args.pxstudiomdl), "v_hand.qc"],
                       cwd=args.output, check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
