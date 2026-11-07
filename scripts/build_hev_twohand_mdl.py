#!/usr/bin/env python3
"""Build the two-hand HEV glove model from the Half-Life: VR single right hand.

The source is ``v_hand_hevsuit.mdl`` decompiled to SMD. It contains one right
hand authored in the same convention as the project's previous hand model:
fingers along -Y, palm along +X, thumb up. The compiler applies a global
Rz(+90), so the runtime hand has fingers +X and the palm facing inward.

This is an extraction and mirror, not a redesign:

1. Keep the hand, the five finger chains and the sleeve bone; drop the biped
   torso, which a standalone hand does not need.
2. Add a ``Bip01 <side> Palm`` landmark at the origin so the existing hand gate
   (``scripts/check_hand_asset.py``) and the runtime palm convention keep
   working.
3. Merge the third thumb joint into the second. The previous asset did the same
   to fit the 35-bone contract; the glove has no separate thumb tip.
4. Scale so the wrist to middle fingertip reach is the canonical 6.4558 units
   measured from the weapon asset itself.
5. Mirror the right hand across the sagittal plane to produce the left hand:
   positions and normals get their Y negated, triangle winding is reversed, and
   every bone rest transform is mirrored as S * R * S.
6. Emit ``hand_r.smd`` and ``hand_l.smd`` that share one skeleton, plus the
   bodygroup QC that ``R_DrawHandEntity`` expects (body 0 right, body 3 left).

Usage:
  scripts/build_hev_twohand_mdl.py \
      --input out/hev_hand_src/v_hand_hevsuit_v_gordon_hands_ref.smd \
      --textures out/hev_hand_src \
      --output out/hev_twohand
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smd_lib  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPILER = os.path.join(REPO, "out", "pxstudiomdl", "pxstudiomdl")

TARGET_REACH = 6.4558  # wrist -> middle fingertip, measured on v_9mmhandgun
PALM_BEHIND = 0.576    # wrist sits this far in front of the origin (old asset)

FINGERS = {
    "thumb": ["Finger0", "Finger01", "Finger02"],
    "index": ["Finger1", "Finger11", "Finger12"],
    "middle": ["Finger2", "Finger21", "Finger22"],
    "ring": ["Finger3", "Finger31", "Finger32"],
    "pinky": ["Finger4", "Finger41", "Finger42"],
}

# Bones dropped from the source and the bone their vertices join instead.
MERGE = {"Finger02": "Finger01", "R_Arm_bone": "Forearm"}


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mat_vec(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def mat_transpose(m):
    return [[m[j][i] for j in range(3)] for i in range(3)]


def mirror_matrix(m):
    # S * M * S with S = diag(-1, 1, 1). The mirror plane is the authored X
    # axis: it flips the palm normal and keeps the fingers along -Y, which is
    # what a left hand is relative to a right hand.
    sign = [-1.0, 1.0, 1.0]
    return [[sign[i] * m[i][j] * sign[j] for j in range(3)] for i in range(3)]


def world_matrices(smd: smd_lib.Smd) -> tuple[dict[int, list], dict[int, tuple]]:
    frames = {f.index: f for f in smd.skeleton}
    children: dict[int, list[int]] = {}
    for node in smd.nodes:
        children.setdefault(node.parent, []).append(node.index)

    rotations: dict[int, list] = {}
    positions: dict[int, tuple] = {}
    identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    def visit(index: int, parent_rot, parent_pos) -> None:
        frame = frames[index]
        rot = mat_mul(parent_rot, smd_lib.euler_to_matrix(*frame.rot))
        pos = tuple(parent_pos[k] + mat_vec(parent_rot, frame.pos)[k] for k in range(3))
        rotations[index] = rot
        positions[index] = pos
        for child in children.get(index, []):
            visit(child, rot, pos)

    for node in smd.nodes:
        if node.parent not in frames:
            visit(node.index, identity, (0.0, 0.0, 0.0))
    return rotations, positions


def build_side(smd: smd_lib.Smd, by_name: dict[str, int], side: str,
               origin: tuple, scale: float, mirror: bool) -> dict:
    rotations, positions = world_matrices(smd)
    hand = by_name["Bip01 R Hand"]
    middle_tip = by_name["Bip01 R Finger22"]
    wrist = positions[hand]

    hand_rot = rotations[hand]
    if mirror:
        hand_rot = mirror_matrix(hand_rot)

    def transform_point(point):
        moved = [(point[k] - origin[k]) * scale for k in range(3)]
        if mirror:
            moved[0] = -moved[0]
        return tuple(moved)

    def transform_rotation(matrix):
        return mirror_matrix(matrix) if mirror else matrix

    # Bone table in parent-before-child order. The old 17-bone chain keeps the
    # gate contract; the sleeve bone becomes the forearm.
    layout = [
        ("Palm", None, None),
        ("Hand", "Bip01 R Hand", "Palm"),
        ("Forearm", "R_Arm_bone", "Hand"),
        ("Finger0", "Bip01 R Finger0", "Hand"),
        ("Finger01", "Bip01 R Finger01", "Finger0"),
        ("Finger1", "Bip01 R Finger1", "Hand"),
        ("Finger11", "Bip01 R Finger11", "Finger1"),
        ("Finger12", "Bip01 R Finger12", "Finger11"),
        ("Finger2", "Bip01 R Finger2", "Hand"),
        ("Finger21", "Bip01 R Finger21", "Finger2"),
        ("Finger22", "Bip01 R Finger22", "Finger21"),
        ("Finger3", "Bip01 R Finger3", "Hand"),
        ("Finger31", "Bip01 R Finger31", "Finger3"),
        ("Finger32", "Bip01 R Finger32", "Finger31"),
        ("Finger4", "Bip01 R Finger4", "Hand"),
        ("Finger41", "Bip01 R Finger41", "Finger4"),
        ("Finger42", "Bip01 R Finger42", "Finger41"),
    ]

    world: dict[str, tuple] = {"Palm": transform_point(origin)}
    world_rot: dict[str, list] = {"Palm": hand_rot}

    for label, source, parent in layout:
        if source is None:
            continue
        world[label] = transform_point(positions[by_name[source]])
        world_rot[label] = transform_rotation(rotations[by_name[source]])

    # Local transforms relative to each parent.
    local = {}
    for label, _source, parent in layout:
        if parent is None:
            local[label] = (world[label], smd_lib.matrix_to_euler(world_rot[label]))
            continue

        parent_world = world[parent]
        parent_rot = world_rot[parent]

        if False:
            pass
        else:
            delta = [world[label][k] - parent_world[k] for k in range(3)]
            pos = tuple(mat_vec(mat_transpose(parent_rot), delta))
            rot = mat_mul(mat_transpose(parent_rot), world_rot[label])

        local[label] = (pos, smd_lib.matrix_to_euler(rot))

    return {
        "world": world,
        "local": local,
        "layout": layout,
        "wrist": wrist,
        "middle_tip": middle_tip,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--textures", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--modelname", default="v_hand_hev.mdl")
    parser.add_argument("--no-compile", action="store_true")
    args = parser.parse_args()

    smd = smd_lib.parse_smd(args.input)
    by_name = {node.name: node.index for node in smd.nodes}
    for required in ("Bip01 R Hand", "Bip01 R Finger22", "R_Arm_bone"):
        if required not in by_name:
            print(f"[FAIL] source SMD has no {required}", file=sys.stderr)
            return 1

    positions = smd_lib.world_positions(smd)
    wrist = positions[by_name["Bip01 R Hand"]]
    middle_tip = positions[by_name["Bip01 R Finger22"]]
    source_reach = math.dist(wrist, middle_tip)
    scale = TARGET_REACH / source_reach

    # The origin sits slightly behind the wrist so the controller pose lands on
    # the heel of the palm, matching the previous asset.
    finger_dir = [(middle_tip[k] - wrist[k]) / source_reach for k in range(3)]
    origin = tuple(wrist[k] + finger_dir[k] * PALM_BEHIND for k in range(3))

    sides = {}
    for side, mirror in (("R", False), ("L", True)):
        sides[side] = build_side(smd, by_name, side, origin, scale, mirror)

    # Shared skeleton: root plus both 17-bone chains.
    nodes = [smd_lib.Node(0, "Bip01", -1)]
    frames = [smd_lib.BoneFrame(0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))]
    index_maps: dict[str, dict[str, int]] = {}

    for side in ("R", "L"):
        mapping = {}
        for label, _source, _parent in sides[side]["layout"]:
            mapping[label] = len(nodes)
            pos, rot = sides[side]["local"][label]
            nodes.append(smd_lib.Node(len(nodes), f"Bip01 {side} {label}", 0))
            frames.append(smd_lib.BoneFrame(len(frames), pos, rot))
        # Fix parents now that all indices exist.
        for label, _source, parent in sides[side]["layout"]:
            node = nodes[mapping[label]]
            node.parent = 0 if parent is None else mapping[parent]
        index_maps[side] = mapping

    bone_names = {node.index: node.name for node in smd.nodes}
    vertices = {}
    for side in ("R", "L"):
        mapping = index_maps[side]
        meshes = []
        for tri in smd.triangles:
            if len(tri.verts) < 3:
                continue
            out_verts = []
            for vert in tri.verts:
                source_name = bone_names.get(vert.parent)
                if source_name is None:
                    continue

                short = source_name.replace("Bip01 R ", "").strip()
                short = MERGE.get(short, short)
                if short not in mapping:
                    continue

                pos = [(vert.pos[k] - origin[k]) * scale for k in range(3)]
                normal = list(vert.normal)
                if side == "L":
                    pos[0] = -pos[0]
                    normal[0] = -normal[0]
                out_verts.append(smd_lib.Vertex(mapping[short], tuple(pos), tuple(normal), vert.uv))
            if len(out_verts) == 3:
                if side == "L":
                    out_verts = [out_verts[0], out_verts[2], out_verts[1]]
                meshes.append(smd_lib.Triangle(tri.material, out_verts))
        vertices[side] = meshes

    os.makedirs(args.output, exist_ok=True)
    for side in ("R", "L"):
        mesh = smd_lib.Smd(nodes=nodes, skeleton=frames, triangles=vertices[side])
        smd_lib.write_smd(os.path.join(args.output, f"hand_{side.lower()}.smd"), mesh)

    qc = f"""// Two-hand HEV glove.
// bodygroup 0 (rhand): studio "hand_r", blank   -> curstate.body 0
// bodygroup 1 (lhand): blank, studio "hand_l"   -> curstate.body 3
$modelname "{args.modelname}"
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

$texrendermode "gordon_glove_Chrome.bmp" "flatshade"
$texrendermode "gordon_glove_Chrome.bmp" "chrome"

$sequence "idle1" "hand_r" fps 1 loop
"""
    qc_path = os.path.join(args.output, "v_hand_hev.qc")
    with open(qc_path, "w", encoding="utf-8") as handle:
        handle.write(qc)

    for material in sorted({t.material for t in smd.triangles}):
        src = os.path.join(args.textures, material)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(args.output, material))
        else:
            print(f"[warn] missing texture {material}", file=sys.stderr)

    report = {
        "source_reach": round(source_reach, 4),
        "target_reach": TARGET_REACH,
        "scale": round(scale, 6),
        "origin": [round(v, 4) for v in origin],
        "bones": len(nodes),
        "right_triangles": len(vertices["R"]),
        "left_triangles": len(vertices["L"]),
        "materials": sorted({t.material for t in smd.triangles}),
        "bone_names": [node.name for node in nodes],
    }
    with open(os.path.join(args.output, "build_report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(report, indent=2))

    if args.no_compile:
        return 0

    if not os.path.isfile(COMPILER):
        print(f"[FAIL] compiler not found: {COMPILER}", file=sys.stderr)
        return 1

    result = subprocess.run([COMPILER, os.path.basename(qc_path)], cwd=args.output,
                            capture_output=True, text=True)
    with open(os.path.join(args.output, "pxstudiomdl.log"), "w", encoding="utf-8") as handle:
        handle.write(result.stdout + result.stderr)
    if result.returncode != 0:
        print("[FAIL] pxstudiomdl failed; see pxstudiomdl.log", file=sys.stderr)
        return result.returncode

    print(f"[PASS] compiled {args.modelname} in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
