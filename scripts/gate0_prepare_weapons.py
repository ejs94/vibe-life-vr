#!/usr/bin/env python3
"""Gate 0: prepare posed weapon meshes and real grip frames.

For each pilot weapon, apply idle frame 0 to the decompiled body meshes, write
an OBJ for Blender, and record the world matrix of the weapon's right-hand
grip bone. The hand meshes are aligned to this frame in Blender; the grip
geometry itself is the posed weapon mesh, not an abstract cylinder.

Outputs:
  out/evidence/gate0_hands/weapons/<weapon>_idle.obj
  out/evidence/gate0_hands/weapons/<weapon>_grip.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import smd_lib  # noqa: E402
from render_viewmodel_idle import first_frame, pose_body, world_transforms  # noqa: E402

DECOMPILED = REPO_DIR / "out" / "mmod_import" / "decompiled"
OUT = REPO_DIR / "out" / "evidence" / "gate0_hands" / "weapons"

WEAPONS = {
    "crossbow": {
        "dir": "v_crossbow",
        "bodies": ["compound_scope.smd"],
        "idle": "idle1.smd",
        "grip_bones": ["Bip01 R Hand", "grip"],
    },
    "glock": {
        "dir": "v_9mmhandgun",
        "bodies": ["glock_reference.smd"],
        "idle": "idle1.smd",
        "grip_bones": ["Bip01 R Hand"],
    },
    "mp5": {
        "dir": "v_9mmar",
        "bodies": ["mp5_reference.smd"],
        "idle": "idle1.smd",
        "grip_bones": ["Bip01 R Hand"],
    },
}


def mat4(pos, mat):
    return [
        [mat[0][0], mat[0][1], mat[0][2], pos[0]],
        [mat[1][0], mat[1][1], mat[1][2], pos[1]],
        [mat[2][0], mat[2][1], mat[2][2], pos[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def write_obj(path, triangles):
    lines = []
    offset = 1
    for verts, _norms, material in triangles:
        lines.append(f"g {material or 'default'}")
        for v in verts:
            lines.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
        lines.append(f"f {offset} {offset+1} {offset+2}")
        offset += 3
    path.write_text("\n".join(lines) + "\n", encoding="latin1")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, spec in WEAPONS.items():
        model_dir = DECOMPILED / spec["dir"]
        idle_path = model_dir / spec["idle"]
        idle = smd_lib.parse_smd(str(idle_path))
        anim_frames = first_frame(idle)

        all_tris = []
        grip_json = {"weapon": name, "idle": spec["idle"], "bones": {}}
        for body_name in spec["bodies"]:
            body_path = model_dir / body_name
            body = smd_lib.parse_smd(str(body_path))
            rest_frames = first_frame(body)
            rest_pos, rest_mat = world_transforms(body, rest_frames)
            anim_pos, anim_mat = world_transforms(body, anim_frames)
            posed = pose_body(body, rest_pos, rest_mat, anim_pos, anim_mat, [])
            if posed is None:
                continue
            verts, _norms, mats = posed
            for i in range(len(verts)):
                all_tris.append((verts[i], None, mats[i]))

            names = {n.name: n.index for n in body.nodes}
            for bone_name in spec["grip_bones"]:
                if bone_name in names:
                    idx = names[bone_name]
                    if idx in anim_pos:
                        grip_json["bones"][bone_name] = {
                            "pos": [round(float(x), 6) for x in anim_pos[idx]],
                            "mat": [[round(float(anim_mat[idx][r][c]), 6) for c in range(3)] for r in range(3)],
                            "matrix4": [
                                [round(float(x), 6) for x in row]
                                for row in mat4(anim_pos[idx], anim_mat[idx])
                            ],
                        }

        obj_path = OUT / f"{name}_idle.obj"
        write_obj(obj_path, all_tris)
        json_path = OUT / f"{name}_grip.json"
        grip_json["obj"] = str(obj_path)
        grip_json["triangles"] = len(all_tris)
        json_path.write_text(json.dumps(grip_json, indent=2) + "\n", encoding="utf-8")
        print(f"{name}: {len(all_tris)} tris -> {obj_path}")
        print(f"  grip bones: {list(grip_json['bones'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
