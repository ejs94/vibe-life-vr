#!/usr/bin/env python3
"""Measure the thumb chain in the standalone Rimrook hand and the baked MMOD hand.

Reads SMD files only. Writes a JSON evidence file with:
  * Rimrook thumb rest frame, curl axis and positions at curl 0 / 0.5 / 1.
  * MMOD baked thumb bone rotations relative to the hand/palm (grip pose).

No mesh or asset is modified.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smd_lib  # noqa: E402


REPO = Path(__file__).resolve().parent.parent
RIMROOK_R = REPO / "out/twohand/hand_r.smd"
MMOD = REPO / "out/mmod_import/decompiled/v_9mmhandgun/HEV_hands_reference.smd"
OUT = REPO / "out/evidence/gate0c/thumb_pose_measurements.json"
MMOD_OUT = REPO / "out/evidence/gate0c/thumb_pose_mmod.json"

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def world_transforms(smd, local_rotations=None):
    """Return (positions, matrices) with optional local matrix replacements."""
    frames = {f.index: f for f in smd.skeleton}
    children = {}
    for node in smd.nodes:
        children.setdefault(node.parent, []).append(node.index)

    pos = {}
    mat = {}

    def visit(idx, parent_pos, parent_mat):
        frame = frames[idx]
        if local_rotations and idx in local_rotations:
            local = local_rotations[idx]
        else:
            local = smd_lib.euler_to_matrix(*frame.rot)
        offset = smd_lib.mat_vec(parent_mat, frame.pos)
        pos[idx] = tuple(parent_pos[k] + offset[k] for k in range(3))
        mat[idx] = smd_lib.mat_mul(parent_mat, local)
        for child in children.get(idx, []):
            visit(child, pos[idx], mat[idx])

    for node in smd.nodes:
        if node.parent == -1:
            visit(node.index, (0.0, 0.0, 0.0), IDENTITY)
    return pos, mat


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def norm(v):
    length = math.sqrt(sum(x * x for x in v))
    if length < 1e-9:
        return (0.0, 0.0, 0.0)
    return tuple(x / length for x in v)


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def angle_between(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(norm(a), norm(b))))))


def mat_to_euler_deg(m):
    rx, ry, rz = smd_lib.matrix_to_euler(m)
    return [round(math.degrees(v), 3) for v in (rx, ry, rz)]


def local_axis(mat, axis):
    return norm(smd_lib.mat_vec(mat, axis))


def rimrook_thumb():
    smd = smd_lib.parse_smd(str(RIMROOK_R))
    names = {n.name: n.index for n in smd.nodes}
    palm = names["Bip01 R Palm"]
    base = names["Bip01 R Finger0"]
    distal = names["Bip01 R Finger01"]
    tip = names.get("Bip01 R Finger02", distal)

    rest_pos, rest_mat = world_transforms(smd)
    samples = []
    for curl in (0.0, 0.5, 1.0):
        local = {
            base: smd_lib.mat_mul(
                smd_lib.euler_to_matrix(*{f.index: f for f in smd.skeleton}[base].rot),
                smd_lib.rot_y(0.35 * curl),
            ),
            distal: smd_lib.mat_mul(
                smd_lib.euler_to_matrix(*{f.index: f for f in smd.skeleton}[distal].rot),
                smd_lib.rot_y(0.55 * curl),
            ),
        }
        pos, mat = world_transforms(smd, local)
        base_dir = sub(pos[distal], pos[base])
        distal_dir = sub(pos[tip], pos[distal]) if tip != distal else (0.0, 0.0, 0.0)
        palm_fwd = local_axis(rest_mat[palm], (1.0, 0.0, 0.0))
        palm_up = local_axis(rest_mat[palm], (0.0, 0.0, 1.0))
        samples.append(
            {
                "curl": curl,
                "angles_deg": {"base": 0.35 * curl * 180.0 / math.pi,
                               "distal": 0.55 * curl * 180.0 / math.pi},
                "base": [round(v, 4) for v in pos[base]],
                "distal": [round(v, 4) for v in pos[distal]],
                "tip": [round(v, 4) for v in pos[tip]],
                "base_dir": [round(v, 4) for v in base_dir],
                "distal_dir": [round(v, 4) for v in distal_dir],
                "base_to_distal_angle_vs_palm_fwd": round(angle_between(base_dir, palm_fwd), 2),
                "base_to_distal_angle_vs_palm_up": round(angle_between(base_dir, palm_up), 2),
                "distal_angle_vs_palm_fwd": round(angle_between(distal_dir, palm_fwd), 2),
            }
        )

    axes = {
        "base_local_y_world": [round(v, 4) for v in local_axis(rest_mat[base], (0.0, 1.0, 0.0))],
        "distal_local_y_world": [round(v, 4) for v in local_axis(rest_mat[distal], (0.0, 1.0, 0.0))],
        "base_local_z_world": [round(v, 4) for v in local_axis(rest_mat[base], (0.0, 0.0, 1.0))],
        "distal_local_z_world": [round(v, 4) for v in local_axis(rest_mat[distal], (0.0, 0.0, 1.0))],
    }
    return {
        "source": str(RIMROOK_R.relative_to(REPO)),
        "chain": ["Bip01 R Palm", "Bip01 R Finger0", "Bip01 R Finger01"],
        "engine_axis": "bone-local Y",
        "engine_limits_rad": {"base": 0.35, "distal": 0.55},
        "rest_base": [round(v, 4) for v in rest_pos[base]],
        "rest_distal": [round(v, 4) for v in rest_pos[distal]],
        "rest_tip": [round(v, 4) for v in rest_pos[tip]],
        "axes": axes,
        "samples": samples,
    }


def mmod_thumb():
    smd = smd_lib.parse_smd(str(MMOD))
    names = {n.name: n.index for n in smd.nodes}
    hand = names["Bip01 R Hand"]
    palm = names.get("Bip01 R Palm", hand)
    chain = ["Bip01 R Finger0", "Bip01 R Finger01", "Bip01 R Finger02"]
    pos, mat = world_transforms(smd)
    hand_mat = mat[hand]

    # Thumb bone rotations relative to the hand bone (the palm frame).
    bones = []
    for name in chain:
        idx = names[name]
        relative = smd_lib.mat_mul(
            [[hand_mat[j][i] for j in range(3)] for i in range(3)], mat[idx]
        )
        bones.append(
            {
                "bone": name,
                "head": [round(v, 4) for v in pos[idx]],
                "euler_rel_hand_deg": mat_to_euler_deg(relative),
                "y_axis_world": [round(v, 4) for v in local_axis(mat[idx], (0.0, 1.0, 0.0))],
                "z_axis_world": [round(v, 4) for v in local_axis(mat[idx], (0.0, 0.0, 1.0))],
            }
        )

    # Segment directions in the hand frame.
    hand_inv = [[hand_mat[j][i] for j in range(3)] for i in range(3)]
    segments = []
    for a, b in zip(chain, chain[1:]):
        ia, ib = names[a], names[b]
        world_dir = sub(pos[ib], pos[ia])
        local_dir = smd_lib.mat_vec(hand_inv, world_dir)
        segments.append(
            {
                "from": a,
                "to": b,
                "dir_hand_space": [round(v, 4) for v in local_dir],
                "angle_vs_hand_x_deg": round(angle_between(local_dir, (1.0, 0.0, 0.0)), 2),
                "angle_vs_hand_y_deg": round(angle_between(local_dir, (0.0, 1.0, 0.0)), 2),
                "angle_vs_hand_z_deg": round(angle_between(local_dir, (0.0, 0.0, 1.0)), 2),
            }
        )

    return {
        "source": str(MMOD.relative_to(REPO)),
        "side": "R",
        "palm_frame": "Bip01 R Hand",
        "chain": chain,
        "bones": bones,
        "segments": segments,
        "note": "Baked weapon-grip pose; not a neutral rest pose.",
    }


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rim = rimrook_thumb()
    mm = mmod_thumb()
    data = {"rimrook": rim, "mmod_thumb": mm}
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    MMOD_OUT.write_text(json.dumps(mm, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {OUT.relative_to(REPO)}")
    print(f"Wrote {MMOD_OUT.relative_to(REPO)}")
    print("Rimrook thumb local Y axis (base):", rim["axes"]["base_local_y_world"])
    for sample in rim["samples"]:
        print(
            f"  curl={sample['curl']:.1f} base_angle={sample['base_to_distal_angle_vs_palm_fwd']} "
            f"base_vs_up={sample['base_to_distal_angle_vs_palm_up']} "
            f"distal_vs_fwd={sample['distal_angle_vs_palm_fwd']}"
        )
    for bone in mm["bones"]:
        print(f"MMOD {bone['bone']} euler_rel_hand={bone['euler_rel_hand_deg']}")


if __name__ == "__main__":
    main()
