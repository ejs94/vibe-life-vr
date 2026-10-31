#!/usr/bin/env python3
"""Improve the Rimrook glove grip without replacing the hand mesh.

The old glove is a real low-poly hand, but its finger chains sit too far from
the palm to close around a realistic controller handle (~0.72u radius). This
script moves each finger chain toward the palm and lengthens the segments to
preserve the palm->fingertip reach, then bakes the new rest pose.

Run inside Blender through the MCP add-on. It only writes a test .blend under
out/viewmodel_work/hand_ref/; it never touches assets/.
"""

import math
import os

import bpy
from mathutils import Quaternion, Vector

REPO_DIR = "/home/ejs94/Documentos/vibe-code-vr-port/vibe-life-vr"
SMD_DIR = os.path.join(REPO_DIR, "out", "twohand")
OUT_DIR = os.path.join(REPO_DIR, "out", "viewmodel_work", "hand_ref")
BLEND_PATH = os.path.join(OUT_DIR, "hand_ref_rimrook_grip.blend")

# Authored SMD space: fingers point -Y, palm normal +X (right) / -X (left),
# thumb +Z. Moving +Y pulls a finger base toward the palm.
BASE_INWARD = 0.30
LENGTH_SCALE = 1.10

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


def move_finger_chains(arm):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for side, chains in CHAINS.items():
        for chain in chains.values():
            original = []
            for name in chain:
                eb = arm.data.edit_bones.get(name)
                if eb is None:
                    original.append(None)
                    continue
                original.append((eb.head.copy(), eb.tail.copy()))
            if any(item is None for item in original):
                continue

            # SMD bone tails are short direction indicators, not the next
            # joint. Use the next bone's head as the joint chain. Apply a
            # similarity transform from the new base to the original joints;
            # the scale keeps the fingertip (last head) at its original Y.
            joints = [item[0] for item in original]
            tails = [item[1] for item in original]
            base = joints[0]
            delta_y = joints[-1].y - base.y
            scale = 1.0 if abs(delta_y) < 1e-6 else 1.0 - BASE_INWARD / delta_y
            scale = max(0.5, min(2.0, scale))
            new_base = base + Vector((0.0, BASE_INWARD, 0.0))

            for i, name in enumerate(chain):
                eb = arm.data.edit_bones.get(name)
                new_head = new_base + (joints[i] - base) * scale
                # Preserve the authored bone direction as a short tail.
                new_tail = new_head + (tails[i] - joints[i])
                eb.head = new_head
                eb.tail = new_tail
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_mesh(mesh):
    bpy.context.view_layer.objects.active = mesh
    for mod in list(mesh.modifiers):
        if mod.type == "ARMATURE":
            bpy.ops.object.modifier_apply(modifier=mod.name)


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
    finger_groups = {
        g.index for g in mesh.vertex_groups
        if "Finger" in g.name and f" {side} " in g.name
    }
    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(deps)
    me = ev.to_mesh()
    vals = []
    for v in me.vertices:
        for ge in v.groups:
            if ge.group in finger_groups and ge.weight > 0.5:
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
    # Both meshes share one armature; use the right one for edits.
    move_finger_chains(right_arm)

    # Bake the new rest pose into the meshes, then restore an armature
    # modifier so the pose sweep below still deforms them.
    bake_mesh(right_mesh)
    bake_mesh(left_mesh)
    for mesh in (right_mesh, left_mesh):
        mod = mesh.modifiers.new("Armature", "ARMATURE")
        mod.object = right_arm

    # Keep the left hand hidden for the right-grip preview.
    left_mesh.hide_viewport = True
    left_mesh.hide_render = True

    # Report the reach and the grip radius for a small sweep while the
    # armature modifier is still active.
    result = {"blend": BLEND_PATH, "reach": {}, "min_radius": {}}
    for amount in (1.2, 1.4, 1.6, 1.7, 1.8, 2.0):
        apply_curl(right_arm, "R", amount)
        bpy.context.view_layer.update()
        result["min_radius"][str(amount)] = min_radius(right_mesh, "R")
    apply_curl(right_arm, "R", 0.0)
    bpy.context.view_layer.update()
    arm_data = right_arm.data
    palm = arm_data.bones["Bip01 R Palm"].head_local
    tip = arm_data.bones["Bip01 R Finger22"].head_local
    result["reach"]["palm_to_tip"] = (tip - palm).length

    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    return result


if __name__ == "__main__":
    print(main())
