#!/usr/bin/env python3
"""Repose only the Rimrook thumb rest bones and rebuild a test hand MDL.

The thumb base and distal rest frames are rotated around their local Z axis
(the same axis the runtime thumb curl uses). Mesh vertices are not edited; the
GoldSrc bone transform re-poses the thumb through the existing weights.

Outputs a new test model under out/twohand_thumb_rest/; assets/ is untouched.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smd_lib  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "out/twohand"
OUT = REPO / "out/twohand_thumb_rest"
COMPILER = REPO / "out/pxstudiomdl/pxstudiomdl"

QC = """// Two-hand VR first-person model with a relaxed thumb rest pose.
$modelname "v_hand.mdl"
$cd "."
$cdtexture "."
$cliptotextures
$scale 1.0

$bodygroup rhand
{
    studio "hand_r"
    blank
}

$bodygroup lhand
{
    blank
    studio "hand_l"
}

$sequence "idle1" "hand_r" fps 1 loop
"""


def update_thumb(smd: smd_lib.Smd, base_deg: float, distal_deg: float) -> dict:
    frames = {f.index: f for f in smd.skeleton}
    nodes = {n.name: n.index for n in smd.nodes}
    changed = {}
    for side, sign in (("R", -1.0), ("L", 1.0)):
        for suffix, degrees in (("Finger0", base_deg), ("Finger01", distal_deg)):
            name = f"Bip01 {side} {suffix}"
            idx = nodes.get(name)
            if idx is None:
                continue
            frame = frames[idx]
            rest = smd_lib.euler_to_matrix(*frame.rot)
            posed = smd_lib.mat_mul(rest, smd_lib.rot_z(math.radians(sign * degrees)))
            frame.rot = smd_lib.matrix_to_euler(posed)
            changed[name] = {
                "base_deg": degrees,
                "sign": sign,
                "rest_euler_before_deg": [round(math.degrees(v), 3) for v in (
                    smd_lib.matrix_to_euler(rest))],
                "rest_euler_after_deg": [round(math.degrees(v), 3) for v in frame.rot],
            }
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=float, default=12.0)
    parser.add_argument("--distal", type=float, default=6.0)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    report = {"base_deg": args.base, "distal_deg": args.distal, "changed": {}}

    for name in ("hand_r", "hand_l"):
        src = smd_lib.parse_smd(str(SRC / f"{name}.smd"))
        changed = update_thumb(src, args.base, args.distal)
        report["changed"][name] = changed
        smd_lib.write_smd(str(OUT / f"{name}.smd"), src)

    (OUT / "v_hand.qc").write_text(QC, encoding="utf-8")
    for texture in ("glove_texture.bmp", "gordon_sleeve.bmp"):
        source = SRC / texture
        if source.exists():
            shutil.copyfile(source, OUT / texture)

    check = subprocess.run(
        [str(COMPILER), "v_hand.qc"], cwd=OUT, text=True, capture_output=True
    )
    report["compile_returncode"] = check.returncode
    report["compile_tail"] = (check.stdout + check.stderr).splitlines()[-12:]
    mdl = OUT / "v_hand.mdl"
    report["mdl"] = str(mdl.relative_to(REPO)) if mdl.exists() else None
    (OUT / "repose_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if mdl.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
