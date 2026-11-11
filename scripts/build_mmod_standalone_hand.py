#!/usr/bin/env python3
"""Extract the MMOD baked hand mesh as a standalone 35-bone hand model.

The source SMD is the hand mesh embedded in a viewmodel. This script keeps the
weapon-space orientation and places the wrist at the origin, so the standalone
entity can be drawn at the exact baked `Bip01 R/L Hand` bone transform.

It is a mesh/rig extraction, not a redesign: triangles and UVs are preserved,
UpperArm weights merge into Forearm, and the third thumb segment merges into
Finger01 to fit the 35-bone contract.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
sys.dont_write_bytecode = True
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smd_lib  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO / "out/mmod_import/decompiled/v_crossbow_check/HEV_hands_reference.smd"
DEFAULT_OUT = REPO / "out/mmod_standalone"
COMPILER = REPO / "out/pxstudiomdl/pxstudiomdl"

QC = """// MMOD baked hand extracted as a standalone 35-bone model.
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

SIDES = ("R", "L")
FINGERS = {
    "Finger0": ["Finger0", "Finger01"],
    "Finger1": ["Finger1", "Finger11", "Finger12"],
    "Finger2": ["Finger2", "Finger21", "Finger22"],
    "Finger3": ["Finger3", "Finger31", "Finger32"],
    "Finger4": ["Finger4", "Finger41", "Finger42"],
}
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def world_transforms(smd):
    frames = {f.index: f for f in smd.skeleton}
    children = {}
    for node in smd.nodes:
        children.setdefault(node.parent, []).append(node.index)
    pos, mat = {}, {}

    def visit(idx, parent_pos, parent_mat):
        frame = frames[idx]
        offset = smd_lib.mat_vec(parent_mat, frame.pos)
        pos[idx] = tuple(parent_pos[k] + offset[k] for k in range(3))
        mat[idx] = smd_lib.mat_mul(parent_mat, smd_lib.euler_to_matrix(*frame.rot))
        for child in children.get(idx, []):
            visit(child, pos[idx], mat[idx])

    for node in smd.nodes:
        if node.parent == -1:
            visit(node.index, (0.0, 0.0, 0.0), IDENTITY)
    return pos, mat


def inverse_rot(mat):
    return [[mat[j][i] for j in range(3)] for i in range(3)]


def local_from_world(parent_pos, parent_mat, pos, mat):
    inv = inverse_rot(parent_mat)
    local_pos = smd_lib.mat_vec(inv, [pos[i] - parent_pos[i] for i in range(3)])
    local_mat = smd_lib.mat_mul(inv, mat)
    return local_pos, smd_lib.matrix_to_euler(local_mat)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    source = Path(args.input).resolve()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    smd = smd_lib.parse_smd(str(source))
    names = {n.name: n.index for n in smd.nodes}
    by_index = {n.index: n.name for n in smd.nodes}
    pos, mat = world_transforms(smd)

    # Build the new 35-bone hierarchy. Root + 17 per side.
    new_nodes = [smd_lib.Node(0, "Bip01", -1)]
    new_world = {0: ((0.0, 0.0, 0.0), IDENTITY)}
    parent_of = {0: -1}
    index_of = {"Bip01": 0}

    for side in SIDES:
        wrist_name = f"Bip01 {side} Hand"
        forearm_name = f"Bip01 {side} Forearm"
        wrist = pos[names[wrist_name]]
        wrist_mat = mat[names[wrist_name]]

        # Palm: one wrist-to-palm offset along the hand's local finger axis.
        # The MMOD hand is authored with the fingers along local -Z.
        offset = smd_lib.mat_vec(wrist_mat, (0.0, 0.0, -0.5756))
        palm = tuple(wrist[k] + offset[k] for k in range(3))

        def add(name, parent, world_pos, world_mat):
            idx = len(new_nodes)
            index_of[name] = idx
            parent_of[idx] = parent
            new_nodes.append(smd_lib.Node(idx, name, parent))
            new_world[idx] = (world_pos, world_mat)
            return idx

        # Shift the wrist to the origin. The upper-arm sleeve is intentionally
        # dropped: remapping it to Forearm stretches the sleeve into a plane and
        # is not needed for a hand-presence asset.
        shift = lambda p: tuple(p[k] - wrist[k] for k in range(3))
        forearm = add(f"Bip01 {side} Forearm", 0, shift(pos[names[forearm_name]]), mat[names[forearm_name]])
        hand = add(wrist_name, forearm, (0.0, 0.0, 0.0), wrist_mat)
        add(f"Bip01 {side} Palm", hand, shift(palm), wrist_mat)
        palm_idx = index_of[f"Bip01 {side} Palm"]

        for base, chain in FINGERS.items():
            parent = palm_idx
            for suffix in chain:
                name = f"Bip01 {side} {suffix}"
                src_idx = names.get(name)
                if src_idx is None:
                    continue
                child = add(name, parent, shift(pos[src_idx]), mat[src_idx])
                parent = child

    # New local frames relative to the new hierarchy.
    new_frames = {}
    for node in new_nodes:
        world_pos, world_mat = new_world[node.index]
        if node.parent < 0:
            new_frames[node.index] = smd_lib.BoneFrame(node.index, world_pos, (0.0, 0.0, 0.0))
        else:
            parent_pos, parent_mat = new_world[node.parent]
            local_pos, local_rot = local_from_world(parent_pos, parent_mat, world_pos, world_mat)
            new_frames[node.index] = smd_lib.BoneFrame(node.index, local_pos, local_rot)

    # Map source hand/arm bones to the new indices.
    def map_parent(src_name):
        if "UpperArm" in src_name:
            src_name = src_name.replace("UpperArm", "Forearm")
        if "Finger02" in src_name:
            src_name = src_name.replace("Finger02", "Finger01")
        return index_of.get(src_name)

    meshes = {"R": smd_lib.Smd(), "L": smd_lib.Smd()}
    for side in SIDES:
        meshes[side].nodes = new_nodes
        meshes[side].skeleton = [new_frames[n.index] for n in new_nodes]

    wrist_shift = {side: pos[names[f"Bip01 {side} Hand"]] for side in SIDES}

    for tri in smd.triangles:
        vert_parents = [by_index.get(v.parent, "") for v in tri.verts]
        if any(("UpperArm" in p or "Forearm" in p) for p in vert_parents):
            continue
        src_parent = vert_parents[0]
        side = "R" if " R " in src_parent else ("L" if " L " in src_parent else None)
        if side is None:
            continue
        if any((" R " in p) != (side == "R") for p in vert_parents):
            continue
        mapped = map_parent(src_parent)
        if mapped is None:
            continue
        verts = []
        for v in tri.verts:
            vp = v.parent
            vname = by_index.get(vp, "")
            if "UpperArm" in vname:
                vname = vname.replace("UpperArm", "Forearm")
            if "Finger02" in vname:
                vname = vname.replace("Finger02", "Finger01")
            vp_new = index_of.get(vname)
            if vp_new is None:
                vp_new = mapped
            shift = wrist_shift[side]
            verts.append(smd_lib.Vertex(vp_new,
                tuple(v.pos[k] - shift[k] for k in range(3)), v.normal, v.uv))
        meshes[side].triangles.append(smd_lib.Triangle(tri.material, verts))

    smd_lib.write_smd(str(out / "hand_r.smd"), meshes["R"])
    smd_lib.write_smd(str(out / "hand_l.smd"), meshes["L"])
    (out / "v_hand.qc").write_text(QC, encoding="utf-8")
    for texture in ("HEV_hands.bmp", "HEV_chrome.bmp", "HEV_forearm_Chrome.bmp"):
        src = source.parent / texture
        if src.exists():
            shutil.copyfile(src, out / texture)

    compile_result = subprocess.run([str(COMPILER), "v_hand.qc"], cwd=out, text=True, capture_output=True)
    report = {
        "input": str(source.relative_to(REPO)) if source.is_relative_to(REPO) else str(source),
        "output": str(out.relative_to(REPO)),
        "bones": len(new_nodes),
        "right_triangles": len(meshes["R"].triangles),
        "left_triangles": len(meshes["L"].triangles),
        "compile_returncode": compile_result.returncode,
        "compile_tail": (compile_result.stdout + compile_result.stderr).splitlines()[-8:],
        "mdl": str((out / "v_hand.mdl").relative_to(REPO)) if (out / "v_hand.mdl").exists() else None,
    }
    (out / "build_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["mdl"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
