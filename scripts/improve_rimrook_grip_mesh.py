#!/usr/bin/env python3
"""Mesh-only Rimrook grip test: pull finger vertices toward the handle.

Keeps the proven skeleton, bone names, reach and bodygroups untouched. The
finger mesh is shifted radially inward toward the controller handle axis; the
procedural curling then rotates the closer geometry around the original bones.

Run inside Blender through the MCP add-on. Test-only; writes a .blend under
out/viewmodel_work/hand_ref/.
"""

import math
import os

import bpy
from mathutils import Quaternion

REPO_DIR = "/home/ejs94/Documentos/vibe-code-vr-port/vibe-life-vr"
SMD_DIR = os.path.join(REPO_DIR, "out", "twohand")
OUT_DIR = os.path.join(REPO_DIR, "out", "viewmodel_work", "hand_ref")
BLEND_PATH = os.path.join(OUT_DIR, "hand_ref_rimrook_mesh.blend")

INWARD = 0.40
THIN = 1.00
HANDLE_RADIUS = 0.72

CHAINS = {
    "R": {
        "thumb": ["Bip01 R Finger0", "Bip01 R Finger01"],
        "index": ["Bip01 R Finger1", "Bip01 R Finger11", "Bip01 R Finger12"],
        "middle": ["Bip01 R Finger2", "Bip01 R Finger21", "Bip01 R Finger22"],
        "ring": ["Bip01 R Finger3", "Bip01 R Finger31", "Bip01 R Finger32"],
        "pinky": ["Bip01 R Finger4", "Bip01 R Finger41", "Bip01 R Finger42"],
    },
    "L": {
        "thumb": ["Bip01 L Finger0", "Bip01 L Finger01"],
        "index": ["Bip01 L Finger1", "Bip01 L Finger11", "Bip01 L Finger12"],
        "middle": ["Bip01 L Finger2", "Bip01 L Finger21", "Bip01 L Finger22"],
        "ring": ["Bip01 L Finger3", "Bip01 L Finger31", "Bip01 L Finger32"],
        "pinky": ["Bip01 L Finger4", "Bip01 L Finger41", "Bip01 L Finger42"],
    },
}


def clear_scene():
    for obj in list(bpy.data.objects):
        if obj.name not in ("Camera", "Light"):
            bpy.data.objects.remove(obj, do_unlink=True)


def import_hand(name):
    bpy.ops.import_scene.smd(filepath=os.path.join(SMD_DIR, f"{name}.smd"))
    arm = bpy.data.objects.get(f"{name}_skeleton") or bpy.data.objects.get("hand_r_skeleton")
    mesh = bpy.data.objects.get(name)
    if arm is None or mesh is None:
        raise RuntimeError(f"import failed for {name}")
    return arm, mesh


def pull_fingers_inward(mesh, arm, side):
    group_names = {g.index: g.name for g in mesh.vertex_groups}
    groups = {
        g.index for g in mesh.vertex_groups
        if "Finger" in g.name and f" {side} " in g.name
    }
    moved = 0
    for vertex in mesh.data.vertices:
        finger_group = None
        for ge in vertex.groups:
            if ge.group in groups and ge.weight > 0.5:
                finger_group = ge.group
                break
        if finger_group is None:
            continue

        x, y, z = vertex.co
        radius = math.hypot(x, y)
        if radius > HANDLE_RADIUS:
            new_radius = max(HANDLE_RADIUS, radius - INWARD)
            scale = new_radius / radius
            vertex.co.x = x * scale
            vertex.co.y = y * scale

        # Thin the finger around its own bone axis. This brings the inner
        # surface closer to the handle without moving the skeleton or the
        # palm->tip reach.
        bone = arm.data.bones.get(group_names[finger_group])
        if bone is not None:
            head = bone.head_local
            axis = bone.tail_local - head
            axis_len2 = axis.length_squared
            if axis_len2 > 1e-9:
                rel = vertex.co - head
                t = rel.dot(axis) / axis_len2
                closest = head + axis * t
                radial = vertex.co - closest
                vertex.co = closest + radial * THIN
        moved += 1
    mesh.data.update()
    return moved


def apply_curl(arm, side, amount, index_scale=0.2, thumb_scale=0.8):
    for finger, chain in CHAINS[side].items():
        for depth, name in enumerate(chain):
            bone = arm.pose.bones.get(name)
            if bone is None:
                continue
            scale = thumb_scale if finger == "thumb" else (index_scale if finger == "index" else 1.0)
            bone.rotation_mode = "QUATERNION"
            bone.rotation_quaternion = Quaternion((0.0, 0.0, 1.0), amount * scale * (1.0 - 0.15 * depth))


def min_radius(mesh, side, z_limit=1.6):
    groups = {
        g.index for g in mesh.vertex_groups
        if "Finger" in g.name and f" {side} " in g.name
    }
    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(deps)
    me = ev.to_mesh()
    vals = []
    for v in me.vertices:
        for ge in v.groups:
            if ge.group in groups and ge.weight > 0.5:
                p = mesh.matrix_world @ v.co
                if abs(p.z) <= z_limit:
                    vals.append(math.hypot(p.x, p.y))
                break
    ev.to_mesh_clear()
    return min(vals) if vals else None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    clear_scene()
    right_arm, right_mesh = import_hand("hand_r")
    left_arm, left_mesh = import_hand("hand_l")

    moved_r = pull_fingers_inward(right_mesh, right_arm, "R")
    moved_l = pull_fingers_inward(left_mesh, left_arm, "L")
    left_mesh.hide_viewport = True
    left_mesh.hide_render = True

    result = {
        "blend": BLEND_PATH,
        "moved_vertices": {"right": moved_r, "left": moved_l},
        "min_radius": {},
    }
    for amount in (1.0, 1.2, 1.4, 1.6, 1.7, 1.8, 2.0):
        apply_curl(right_arm, "R", amount)
        bpy.context.view_layer.update()
        result["min_radius"][str(amount)] = min_radius(right_mesh, "R")
    apply_curl(right_arm, "R", 0.0)
    bpy.context.view_layer.update()
    arm_data = right_arm.data
    palm = arm_data.bones["Bip01 R Palm"].head_local
    tip = arm_data.bones["Bip01 R Finger22"].head_local
    result["reach"] = (tip - palm).length

    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    return result


if __name__ == "__main__":
    print(main())
