#!/usr/bin/env python3
"""Build a black ghost-hand variant from the current standalone hand rig.

This is a material-only variant: the 35-bone rig, bodygroups and mesh are kept,
but every triangle uses a flat black texture. It is the portable fallback for
mods/expansions without a matching baked hand set.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smd_lib  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "out/twohand"
OUT = REPO / "out/ghost_hand"
COMPILER = REPO / "out/pxstudiomdl/pxstudiomdl"
TEXTURE = "ghost_black.bmp"

QC = """// Black ghost-hand fallback built from the standalone 35-bone rig.
$modelname "v_hand_ghost.mdl"
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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    for name in ("hand_r", "hand_l"):
        smd = smd_lib.parse_smd(str(SRC / f"{name}.smd"))
        for tri in smd.triangles:
            tri.material = TEXTURE
        smd_lib.write_smd(str(OUT / f"{name}.smd"), smd)

    image = Image.new("RGB", (64, 64), (0, 0, 0))
    image.save(OUT / TEXTURE)
    (OUT / "v_hand.qc").write_text(QC, encoding="utf-8")

    result = subprocess.run([str(COMPILER), "v_hand.qc"], cwd=OUT, text=True, capture_output=True)
    mdl = OUT / "v_hand_ghost.mdl"
    report = {
        "output": str(OUT.relative_to(REPO)),
        "compile_returncode": result.returncode,
        "compile_tail": (result.stdout + result.stderr).splitlines()[-8:],
        "mdl": str(mdl.relative_to(REPO)) if mdl.exists() else None,
    }
    (OUT / "build_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if mdl.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
