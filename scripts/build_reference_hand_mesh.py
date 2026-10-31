#!/usr/bin/env python3
"""Generate a thin reference hand mesh on the existing 35-bone hand rig.

The old Rimrook glove cannot close around a realistic controller handle: its
finger pads bottom out at ~1.20u radial distance, so a 0.72u handle leaves a
visible gap, while curling further pushes the pads through the handle. This
script keeps the proven skeleton/naming/bodygroup contract but rebuilds the
mesh with thin finger cylinders that can wrap the handle.

Outputs (all under out/viewmodel_work/hand_ref/):
  hand_r.smd, hand_l.smd, v_hand.qc, v_hand.mdl, compile.log

The generated MDL is a pilot/reference asset. It is not copied into
assets/valve_vr/models until the Blender and Monado gates pass.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import smd_lib  # noqa: E402

SRC_SMD = REPO_DIR / "out" / "twohand" / "hand_r.smd"
OUT_DIR = REPO_DIR / "out" / "viewmodel_work" / "hand_ref"
STUDIOMDL = REPO_DIR / "out" / "pxstudiomdl" / "pxstudiomdl"
TEX_DIR = REPO_DIR / "out" / "twohand"

GLOVE = "glove_texture.bmp"
SLEEVE = "gordon_sleeve.bmp"


def vadd(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def vsub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def vmul(a, s):
    return tuple(a[i] * s for i in range(3))


def vlen(a):
    return math.sqrt(sum(a[i] * a[i] for i in range(3)))


def vnorm(a):
    n = vlen(a)
    return tuple(a[i] / n for i in range(3)) if n > 1e-9 else (0.0, 0.0, 1.0)


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def basis(axis):
    axis = vnorm(axis)
    ref = (0.0, 0.0, 1.0) if abs(axis[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = vnorm(cross(axis, ref))
    v = cross(axis, u)
    return u, v


def add_cylinder(tris, p0, p1, radius, parent, material, sides=8):
    axis = vsub(p1, p0)
    u, v = basis(axis)
    ring0 = []
    ring1 = []
    for i in range(sides):
        ang = 2.0 * math.pi * i / sides
        radial = vadd(vmul(u, math.cos(ang) * radius), vmul(v, math.sin(ang) * radius))
        ring0.append(vadd(p0, radial))
        ring1.append(vadd(p1, radial))
    for i in range(sides):
        j = (i + 1) % sides
        n0 = vnorm(vsub(ring0[i], p0))
        n1 = vnorm(vsub(ring0[j], p0))
        # Two triangles per quad; normals point radially outward.
        tris.append(smd_lib.Triangle(material, [
            smd_lib.Vertex(parent, ring0[i], n0, (0.5, 0.5)),
            smd_lib.Vertex(parent, ring1[i], n0, (0.5, 0.5)),
            smd_lib.Vertex(parent, ring1[j], n1, (0.5, 0.5)),
        ]))
        tris.append(smd_lib.Triangle(material, [
            smd_lib.Vertex(parent, ring0[i], n0, (0.5, 0.5)),
            smd_lib.Vertex(parent, ring1[j], n1, (0.5, 0.5)),
            smd_lib.Vertex(parent, ring0[j], n1, (0.5, 0.5)),
        ]))


def add_box(tris, center, half, parent, material):
    cx, cy, cz = center
    hx, hy, hz = half
    corners = [
        (cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz),
    ]
    faces = [
        ((0, 3, 2, 1), (0, 0, -1)), ((4, 5, 6, 7), (0, 0, 1)),
        ((0, 1, 5, 4), (0, -1, 0)), ((1, 2, 6, 5), (1, 0, 0)),
        ((2, 3, 7, 6), (0, 1, 0)), ((3, 0, 4, 7), (-1, 0, 0)),
    ]
    for quad, normal in faces:
        a, b, c, d = (corners[i] for i in quad)
        tris.append(smd_lib.Triangle(material, [
            smd_lib.Vertex(parent, a, normal, (0.5, 0.5)),
            smd_lib.Vertex(parent, b, normal, (0.5, 0.5)),
            smd_lib.Vertex(parent, c, normal, (0.5, 0.5)),
        ]))
        tris.append(smd_lib.Triangle(material, [
            smd_lib.Vertex(parent, a, normal, (0.5, 0.5)),
            smd_lib.Vertex(parent, c, normal, (0.5, 0.5)),
            smd_lib.Vertex(parent, d, normal, (0.5, 0.5)),
        ]))


def build_side(template, side, world):
    prefix = "R" if side == "r" else "L"
    idx = {n.name: n.index for n in template.nodes}
    wpos = {n.name: world[n.index] for n in template.nodes}
    tris = []

    palm = idx[f"Bip01 {prefix} Palm"]
    wrist = idx[f"Bip01 {prefix} Hand"]
    forearm = idx[f"Bip01 {prefix} Forearm"]

    # Palm block: fingers leave the front edge (negative Y in SMD space).
    # It is slightly wider than the 0.94u reference handle so the palm is
    # visible around the handle instead of disappearing inside it.
    add_box(tris, (0.0, -0.20, 0.0), (0.95, 1.05, 0.95), palm, GLOVE)

    # Wrist and sleeve.
    add_cylinder(tris, wpos[f"Bip01 {prefix} Hand"],
                 wpos[f"Bip01 {prefix} Forearm"], 0.42, wrist, GLOVE)
    add_cylinder(tris, wpos[f"Bip01 {prefix} Forearm"],
                 vadd(wpos[f"Bip01 {prefix} Forearm"], (0.0, 2.2, 0.0)),
                 0.55, forearm, SLEEVE)

    chains = {
        "thumb": ["Finger0", "Finger01"],
        "index": ["Finger1", "Finger11", "Finger12"],
        "middle": ["Finger2", "Finger21", "Finger22"],
        "ring": ["Finger3", "Finger31", "Finger32"],
        "pinky": ["Finger4", "Finger41", "Finger42"],
    }
    radius = 0.16
    for chain in chains.values():
        for depth, suffix in enumerate(chain):
            bone = f"Bip01 {prefix} {suffix}"
            if bone not in wpos:
                continue
            if depth + 1 < len(chain):
                nxt = f"Bip01 {prefix} {chain[depth + 1]}"
                if nxt in wpos:
                    add_cylinder(tris, wpos[bone], wpos[nxt], radius, idx[bone], GLOVE)
            else:
                # Final segment points toward the fingertip; the tip is just
                # past the last bone head in the open reference pose.
                prev = f"Bip01 {prefix} {chain[depth - 1]}"
                direction = vnorm(vsub(wpos[bone], wpos[prev]))
                tip = vadd(wpos[bone], vmul(direction, 0.55))
                add_cylinder(tris, wpos[bone], tip, radius, idx[bone], GLOVE)
    return tris


def main() -> int:
    if not SRC_SMD.is_file():
        print(f"error: missing {SRC_SMD}", file=sys.stderr)
        return 1
    if not STUDIOMDL.is_file():
        print(f"error: missing {STUDIOMDL}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    template = smd_lib.parse_smd(str(SRC_SMD))
    world = smd_lib.world_positions(template)

    right = smd_lib.Smd(nodes=template.nodes, skeleton=template.skeleton,
                        triangles=build_side(template, "r", world))
    left = smd_lib.Smd(nodes=template.nodes, skeleton=template.skeleton,
                       triangles=build_side(template, "l", world))

    smd_lib.write_smd(str(OUT_DIR / "hand_r.smd"), right)
    smd_lib.write_smd(str(OUT_DIR / "hand_l.smd"), left)

    for name in (GLOVE, SLEEVE):
        src = TEX_DIR / name
        if not src.is_file():
            print(f"error: missing texture {src}", file=sys.stderr)
            return 1
        shutil.copyfile(src, OUT_DIR / name)

    qc = """// Reference hand pilot: thin mesh on the proven 35-bone contract.
$modelname "v_hand.mdl"
$cd "."
$cdtexture "."
$cliptotextures
$scale 1.0

$bodygroup rhand
{{
    studio "hand_r"
    blank
}}

$bodygroup lhand
{{
    blank
    studio "hand_l"
}}

$sequence "idle1" "hand_r" fps 1 loop
"""
    (OUT_DIR / "v_hand.qc").write_text(qc, encoding="latin1")

    log = OUT_DIR / "compile.log"
    with log.open("w", encoding="latin1") as fh:
        proc = subprocess.run(
            [str(STUDIOMDL), "v_hand.qc"],
            cwd=OUT_DIR,
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
    if proc.returncode != 0 or not (OUT_DIR / "v_hand.mdl").is_file():
        print(f"error: compilation failed; see {log}", file=sys.stderr)
        return 1

    print(f"built {OUT_DIR / 'v_hand.mdl'}")
    print(f"  triangles: right={len(right.triangles)} left={len(left.triangles)}")
    print(f"  compile log: {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
