#!/usr/bin/env python3
"""Build the two-hand VR hand model (models/v_hand.mdl) from the Rimrook pair.

The source ``hev_reference.smd`` (public domain, "HEV Arms That Don't Suck" by
Rimrook) contains both hands as separate subtrees of a shared root. That lets
us author a single MDL with a right chain and a left chain, instead of shipping
a single hand and reflecting it at runtime.

What this script does, deterministically:

1. Scales both hands so the wrist-to-middle-fingertip reach matches the
   canonical GoldSrc first-person hand size (6.4558 units, measured from the
   Valve HD ``v_hand.mdl``). GoldSrc renders models at their native scale, so
   this is the on-screen size.
2. Recenters each hand on a chosen origin (palm by default, so the grip wraps
   the tracked controller) so both chains sit at the model origin; the engine
   draws each hand entity at its own controller pose.
3. Renames the Rimrook bones to the Valve convention
   (``Bip01 R Hand`` / ``Bip01 R Finger0`` / ``Bip01 R Finger01`` ...), which
   is what R_StudioApplyFingerCurling matches.
4. Emits two reference SMDs that share one skeleton, each with only its own
   triangles, and a QC with two bodygroups using ``blank``.

Body selection relies on the bodygroup base arithmetic:
    bodygroup rhand { studio "hand_r" blank }   base 1, 2 variants
    bodygroup lhand { blank studio "hand_l" }   base 2, 2 variants
    curstate.body = 0 -> right hand, 3 -> left hand

Usage:
  scripts/build_twohand_mdl.py \
      --input  /path/to/hev_reference.smd \
      --textures /path/to/textures \
      --output out/twohand
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smd_lib  # noqa: E402

# Canonical wrist -> middle-fingertip reach in GoldSrc units, measured from the
# Valve HD v_hand.mdl (Bip01 R Hand -> Bip01 R Finger22).
DEFAULT_TARGET_REACH = 6.4558

# pxstudiomdl applies a built-in +90 degree Z rotation to every model
# (g_defaultrotation in studiomdl.cpp) to the animation, so the runtime
# geometry is rotated +90 degrees relative to the authored SMD. Authoring the
# source 180 degrees off therefore makes the fingers point along +X, GoldSrc's
# forward axis.
DEFAULT_MODEL_YAW_DEG = 180.0

# The Rimrook pair is authored palms-down (palm normal -Z on both hands). A
# yaw alone leaves the palms facing down ("lying on a table"). The per-hand
# pitch rolls each palm inward so the hands look like they are gripping a
# controller. GoldSrc has +Y = left, so the right hand sits at -Y and its
# inward direction is +Y; the left hand's inward direction is -Y. This also
# puts both thumbs up (+Z).
DEFAULT_PITCH_RIGHT_DEG = 90.0
DEFAULT_PITCH_LEFT_DEG = -90.0

# Rimrook's rig, as verified from hev_reference.smd. Bone01/Bone19 are the two
# parentless wrists; Bone18/Bone20 are the forearms; Bone17/Bone21 the palms.
SIDES = {
    "right": {
        "prefix": "R",
        "wrist": "Bone01",
        "forearm": "Bone18",
        "palm": "Bone17",
        "fingers": {
            "thumb": ["Bone02", "Bone03"],
            "index": ["Bone05", "Bone06", "Bone07"],
            "middle": ["Bone08", "Bone09", "Bone10"],
            "ring": ["Bone11", "Bone12", "Bone13"],
            "pinky": ["Bone14", "Bone15", "Bone16"],
        },
    },
    "left": {
        "prefix": "L",
        "wrist": "Bone19",
        "forearm": "Bone20",
        "palm": "Bone21",
        "fingers": {
            "thumb": ["Bone22", "Bone23"],
            "index": ["Bone24", "Bone25", "Bone26"],
            "middle": ["Bone27", "Bone28", "Bone29"],
            "ring": ["Bone30", "Bone31", "Bone32"],
            "pinky": ["Bone33", "Bone34", "Bone35"],
        },
    },
}

# Valve finger bone suffixes. The Rimrook thumb has two joints, so it only uses
# the first two names; the third (Finger02) is intentionally absent.
FINGER_SUFFIXES = {
    "thumb": ["0", "01"],
    "index": ["1", "11", "12"],
    "middle": ["2", "21", "22"],
    "ring": ["3", "31", "32"],
    "pinky": ["4", "41", "42"],
}


def build(smd: smd_lib.Smd, target_reach: float, origin: str,
          yaw_deg: float = DEFAULT_MODEL_YAW_DEG,
          pitch_right_deg: float = DEFAULT_PITCH_RIGHT_DEG,
          pitch_left_deg: float = DEFAULT_PITCH_LEFT_DEG,
          rotate_bones: bool = True) -> tuple[smd_lib.Smd, smd_lib.Smd, dict]:
    by_name = {node.name: node.index for node in smd.nodes}
    world = smd_lib.world_positions(smd)
    frames = {f.index: f for f in smd.skeleton}

    # Scale from the right hand; both hands are the same size in the source.
    right_middle_tip = SIDES["right"]["fingers"]["middle"][-1]
    source_reach = smd_lib.reach(smd, by_name[SIDES["right"]["wrist"]], by_name[right_middle_tip])
    scale = target_reach / source_reach

    # Authoring rotation per hand: Rz(yaw) * Ry(pitch). pxstudiomdl adds a
    # global Rz(+90) at runtime, so this yields fingers +X and palms facing
    # inward (+/-Y). The rotation is baked into vertices, normals and the
    # wrist rest rotation, never into the root (the root rest rotation is
    # dropped from the animation).
    theta = math.radians(yaw_deg)
    side_mats = {
        "right": smd_lib.mat_mul(smd_lib.rot_z(theta), smd_lib.rot_y(math.radians(pitch_right_deg))),
        "left": smd_lib.mat_mul(smd_lib.rot_z(theta), smd_lib.rot_y(math.radians(pitch_left_deg))),
    }

    # New skeleton: a shared root plus the two chains. Both wrists are placed so
    # their chosen origin lands on (0,0,0). The yaw is baked into the two wrist
    # bones rather than the root: pxstudiomdl drops the root bone's rest
    # rotation from the animation, which would apply it twice at runtime.
    new_nodes: list[smd_lib.Node] = [smd_lib.Node(0, "Bip01", -1)]
    new_frames: list[smd_lib.BoneFrame] = [
        smd_lib.BoneFrame(0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    ]

    side_index_maps: dict[str, dict[int, int]] = {}
    side_origins: dict[str, tuple[float, float, float]] = {}

    for side, cfg in SIDES.items():
        wrist_idx = by_name[cfg["wrist"]]
        palm_idx = by_name[cfg["palm"]]
        first_index_idx = by_name[cfg["fingers"]["index"][0]]

        if origin == "wrist":
            origin_pos = world[wrist_idx]
        elif origin == "palm":
            origin_pos = world[palm_idx]
        elif origin == "index":
            a, b = world[palm_idx], world[first_index_idx]
            origin_pos = tuple((a[k] + b[k]) * 0.5 for k in range(3))
        else:
            raise ValueError(f"unknown origin: {origin}")
        side_origins[side] = origin_pos

        # Rename map for this side.
        rename: dict[int, str] = {wrist_idx: f"Bip01 {cfg['prefix']} Hand"}
        rename[by_name[cfg["forearm"]]] = f"Bip01 {cfg['prefix']} Forearm"
        rename[palm_idx] = f"Bip01 {cfg['prefix']} Palm"
        for finger, chain in cfg["fingers"].items():
            for src_name, suffix in zip(chain, FINGER_SUFFIXES[finger]):
                rename[by_name[src_name]] = f"Bip01 {cfg['prefix']} Finger{suffix}"

        kept = smd_lib.descendants(smd, [wrist_idx])
        # Source nodes are listed parent-before-child; keep that order.
        ordered = [node for node in smd.nodes if node.index in kept]

        index_map: dict[int, int] = {}
        for node in ordered:
            new_idx = len(new_nodes)
            index_map[node.index] = new_idx
            if node.index == wrist_idx:
                new_parent = 0
                A = side_mats[side]
                pos = smd_lib.mat_vec(A, tuple((world[wrist_idx][k] - origin_pos[k]) * scale for k in range(3)))
                if rotate_bones:
                    # Pre-multiply the wrist rest rotation by the authoring rotation.
                    R = smd_lib.mat_mul(A, smd_lib.euler_to_matrix(*frames[wrist_idx].rot))
                    rot = smd_lib.matrix_to_euler(R)
                else:
                    rot = frames[wrist_idx].rot
            else:
                new_parent = index_map[node.parent]
                frame = frames[node.index]
                pos = tuple(v * scale for v in frame.pos)
                rot = frame.rot
            new_nodes.append(smd_lib.Node(new_idx, rename.get(node.index, node.name), new_parent))
            new_frames.append(smd_lib.BoneFrame(new_idx, pos, rot))

        side_index_maps[side] = index_map

    skeleton = smd_lib.Smd()
    skeleton.nodes = new_nodes
    skeleton.skeleton = new_frames

    # Split triangles by side and apply the same affine transform to geometry.
    meshes: dict[str, smd_lib.Smd] = {}
    for side, cfg in SIDES.items():
        index_map = side_index_maps[side]
        origin_pos = side_origins[side]
        A = side_mats[side]
        mesh = smd_lib.Smd(nodes=new_nodes, skeleton=new_frames, triangles=[])

        dropped = 0
        for tri in smd.triangles:
            if not tri.verts:
                continue
            if tri.verts[0].parent not in index_map:
                continue
            out_verts = []
            for vert in tri.verts:
                pos = smd_lib.mat_vec(A, tuple((vert.pos[k] - origin_pos[k]) * scale for k in range(3)))
                normal = smd_lib.mat_vec(A, vert.normal)
                out_verts.append(
                    smd_lib.Vertex(index_map[vert.parent], pos, normal, vert.uv)
                )
            mesh.triangles.append(smd_lib.Triangle(tri.material, out_verts))
        meshes[side] = mesh

    report = {
        "source_reach": round(source_reach, 4),
        "target_reach": target_reach,
        "scale": round(scale, 6),
        "origin": origin,
        "yaw_deg": yaw_deg,
        "pitch_right_deg": pitch_right_deg,
        "pitch_left_deg": pitch_left_deg,
        "bones": len(new_nodes),
        "right_triangles": len(meshes["right"].triangles),
        "left_triangles": len(meshes["left"].triangles),
        "materials": sorted({t.material for t in smd.triangles}),
        "bone_names": [n.name for n in sorted(new_nodes, key=lambda n: n.index)],
    }
    return meshes["right"], meshes["left"], report


QC_TEMPLATE = """// Two-hand VR first-person model.
// bodygroup 0 (rhand): studio "hand_r", blank   -> curstate.body 0
// bodygroup 1 (lhand): blank, studio "hand_l"   -> curstate.body 3
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="hev_reference.smd")
    parser.add_argument("--textures", required=True, help="directory with the source .bmp files")
    parser.add_argument("--output", required=True, help="output directory")
    parser.add_argument("--target-reach", type=float, default=DEFAULT_TARGET_REACH)
    # The tracked OpenXR aim pose sits at the controller/grip, so the palm is
    # the natural anchor: with the wrist as origin the hand appears to extend
    # forward from the controller instead of wrapping it.
    parser.add_argument("--origin", choices=["wrist", "palm", "index"], default="palm")
    parser.add_argument("--yaw", type=float, default=DEFAULT_MODEL_YAW_DEG, help="model-space yaw in degrees")
    parser.add_argument("--pitch-right", type=float, default=DEFAULT_PITCH_RIGHT_DEG, help="right hand palm roll in degrees")
    parser.add_argument("--pitch-left", type=float, default=DEFAULT_PITCH_LEFT_DEG, help="left hand palm roll in degrees")
    parser.add_argument("--no-rotate-bones", dest="rotate_bones", action="store_false", help="leave the wrist rest rotation unrotated (debug)")
    args = parser.parse_args()

    smd = smd_lib.parse_smd(args.input)
    right, left, report = build(smd, args.target_reach, args.origin, args.yaw,
                                args.pitch_right, args.pitch_left, args.rotate_bones)

    os.makedirs(args.output, exist_ok=True)
    smd_lib.write_smd(os.path.join(args.output, "hand_r.smd"), right)
    smd_lib.write_smd(os.path.join(args.output, "hand_l.smd"), left)

    with open(os.path.join(args.output, "v_hand.qc"), "w", encoding="utf-8") as handle:
        handle.write(QC_TEMPLATE)

    for material in report["materials"]:
        src = os.path.join(args.textures, material)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(args.output, material))
        else:
            print(f"warning: missing texture {src}", file=sys.stderr)

    with open(os.path.join(args.output, "build_report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
