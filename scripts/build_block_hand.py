#!/usr/bin/env python3
"""Build a simple blocky black glove on the 35-bone hand contract.

The mesh is generated from boxes around the existing contract skeleton. It is
intentionally not a detailed hand model: it provides an unambiguous hand
presence for unarmed/free-offhand states and cannot be mistaken for a baked
weapon hand.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smd_lib  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "out/twohand/hand_r.smd"
OUT = REPO / "out/block_hand"
COMPILER = REPO / "out/pxstudiomdl/pxstudiomdl"
TEXTURE = "block_hand.bmp"

QC = """// Blocky black glove generated on the 35-bone hand contract.
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

FINGERS = {
    "Finger0": ["Finger0", "Finger01"],
    "Finger1": ["Finger1", "Finger11", "Finger12"],
    "Finger2": ["Finger2", "Finger21", "Finger22"],
    "Finger3": ["Finger3", "Finger31", "Finger32"],
    "Finger4": ["Finger4", "Finger41", "Finger42"],
}


def norm(v):
    n = math.sqrt(sum(x * x for x in v))
    return tuple(x / n for x in v) if n > 1e-9 else (0.0, 0.0, 0.0)


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def add_box(tris, parent, a, b, radius=0.28, material=TEXTURE):
    a = tuple(a); b = tuple(b)
    d = tuple(b[i]-a[i] for i in range(3))
    length = math.sqrt(sum(x*x for x in d))
    if length < 1e-5:
        return
    f = norm(d)
    up = (0.0, 0.0, 1.0) if abs(f[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = norm(cross(f, up))
    v = norm(cross(f, u))
    c = tuple((a[i]+b[i])*0.5 for i in range(3))
    hx, hy, hz = length*0.5, radius, radius

    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                corners.append(tuple(
                    c[i] + f[i]*hx*sx + u[i]*hy*sy + v[i]*hz*sz
                    for i in range(3)
                ))
    # index: sx*4 + sy*2 + sz mapping
    def idx(sx, sy, sz):
        return (0 if sx < 0 else 1)*4 + (0 if sy < 0 else 1)*2 + (0 if sz < 0 else 1)
    faces = [
        (idx(-1,-1,-1), idx(-1,1,-1), idx(-1,1,1), idx(-1,-1,1)),
        (idx(1,-1,-1), idx(1,-1,1), idx(1,1,1), idx(1,1,-1)),
        (idx(-1,-1,-1), idx(-1,-1,1), idx(1,-1,1), idx(1,-1,-1)),
        (idx(-1,1,-1), idx(1,1,-1), idx(1,1,1), idx(-1,1,1)),
        (idx(-1,-1,-1), idx(1,-1,-1), idx(1,1,-1), idx(-1,1,-1)),
        (idx(-1,-1,1), idx(-1,1,1), idx(1,1,1), idx(1,-1,1)),
    ]
    for quad in faces:
        p0, p1, p2, p3 = [corners[i] for i in quad]
        n = norm(cross(tuple(p1[i]-p0[i] for i in range(3)),
                       tuple(p2[i]-p0[i] for i in range(3))))
        for tri in ((p0, p1, p2), (p0, p2, p3)):
            verts = [smd_lib.Vertex(parent, p, n, (0.0, 0.0)) for p in tri]
            tris.append(smd_lib.Triangle(material, verts))


def build_side(base, side):
    nodes = base.nodes
    frames = {f.index: f for f in base.skeleton}
    world = smd_lib.world_positions(base)
    names = {n.name: n.index for n in nodes}
    tris = []

    def head(name):
        return world[names[f"Bip01 {side} {name}"]]

    # Short wrist cuff instead of a full forearm slab. The blocky hand is a
    # presence placeholder, not an anatomical arm.
    forearm = head("Forearm")
    hand = head("Hand")
    cuff_start = tuple(forearm[i] * 0.5 + hand[i] * 0.5 for i in range(3))
    add_box(tris, names[f"Bip01 {side} Forearm"], cuff_start, hand, 0.45)

    # Keep the palm wide enough to read as a hand but flat enough that it does
    # not become a large rectangular slab in the first-person view.
    palm = head("Palm")
    add_box(tris, names[f"Bip01 {side} Palm"],
            tuple(palm[i] + (0.5 if i == 0 else 0.0) for i in range(3)),
            tuple(palm[i] - (0.5 if i == 0 else 0.0) for i in range(3)), 0.6)

    for chain in FINGERS.values():
        # Connect the palm to the first finger bone. Boxes only around the
        # finger bones leave a visible gap at the metacarpals.
        add_box(tris, names[f"Bip01 {side} {chain[0]}"], palm, head(chain[0]), 0.20)
        for depth, suffix in enumerate(chain):
            a = head(suffix)
            if depth + 1 < len(chain):
                b = head(chain[depth + 1])
            else:
                # Extend the last segment along its own direction.
                if depth > 0:
                    prev = head(chain[depth - 1])
                    d = norm(tuple(a[i] - prev[i] for i in range(3)))
                else:
                    d = (0.0, -1.0, 0.0)
                b = tuple(a[i] + d[i] * 0.8 for i in range(3))
            add_box(tris, names[f"Bip01 {side} {suffix}"], a, b, 0.20)

    mesh = smd_lib.Smd()
    mesh.nodes = nodes
    mesh.skeleton = [frames[n.index] for n in nodes]
    mesh.triangles = tris
    return mesh


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    base = smd_lib.parse_smd(str(SRC))
    for side, name in (("R", "hand_r"), ("L", "hand_l")):
        smd_lib.write_smd(str(OUT / f"{name}.smd"), build_side(base, side))
    Image.new("RGB", (64, 64), (0, 0, 0)).save(OUT / TEXTURE)
    (OUT / "v_hand.qc").write_text(QC, encoding="utf-8")

    result = subprocess.run([str(COMPILER), "v_hand.qc"], cwd=OUT, text=True, capture_output=True)
    mdl = OUT / "v_hand.mdl"
    print(result.stdout[-400:])
    print(result.stderr[-400:])
    print("mdl", mdl.exists())
    return 0 if mdl.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
