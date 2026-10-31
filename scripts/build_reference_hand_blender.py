#!/usr/bin/env python3
"""Build the Blender reference-hand scene for the crossbow pilot.

Run inside Blender (headless or through the MCP add-on):

    exec(open("scripts/build_reference_hand_blender.py").read())

The script starts from the existing v_hand SMD pair (the current contract:
palm at the origin, Bip01 R/L Hand + Bip01 R/L Palm + Finger0..42, two hands)
and adds the reference controller handle, a trigger proxy, and four pose
actions: open, fist, pistol and support.

Important frame note: the SMD is authored in compiler space (fingers -Y,
wrist +Y, thumb +Z). pxstudiomdl applies its built-in Rz(+90), so the runtime
frame is fingers +X, right palm inward +Y, left palm inward -Y, thumb +Z.
The reference cylinder is therefore placed on the authored +Z axis, centered
on the palm. All measurements below are in GoldSrc units (1u = 1 inch-ish).
"""

import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

REPO_DIR = "/home/ejs94/Documentos/vibe-code-vr-port/vibe-life-vr"
SMD_DIR = os.path.join(REPO_DIR, "out", "viewmodel_work", "hand_ref")
OUT_DIR = os.path.join(REPO_DIR, "out", "viewmodel_work", "hand_ref")
BLEND_PATH = os.path.join(OUT_DIR, "hand_ref.blend")

RIGHT_FINGERS = {
    "thumb": ["Bip01 R Finger0", "Bip01 R Finger01"],
    "index": ["Bip01 R Finger1", "Bip01 R Finger11", "Bip01 R Finger12"],
    "middle": ["Bip01 R Finger2", "Bip01 R Finger21", "Bip01 R Finger22"],
    "ring": ["Bip01 R Finger3", "Bip01 R Finger31", "Bip01 R Finger32"],
    "pinky": ["Bip01 R Finger4", "Bip01 R Finger41", "Bip01 R Finger42"],
}
LEFT_FINGERS = {
    "thumb": ["Bip01 L Finger0", "Bip01 L Finger01"],
    "index": ["Bip01 L Finger1", "Bip01 L Finger11", "Bip01 L Finger12"],
    "middle": ["Bip01 L Finger2", "Bip01 L Finger21", "Bip01 L Finger22"],
    "ring": ["Bip01 L Finger3", "Bip01 L Finger31", "Bip01 L Finger32"],
    "pinky": ["Bip01 L Finger4", "Bip01 L Finger41", "Bip01 L Finger42"],
}


def clear_scene():
    for obj in list(bpy.data.objects):
        if obj.name not in ("Camera", "Light"):
            bpy.data.objects.remove(obj, do_unlink=True)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def import_hand(name):
    path = os.path.join(SMD_DIR, f"{name}.smd")
    bpy.ops.import_scene.smd(filepath=path)
    # ValveSource reuses the existing armature when the bone list matches, so
    # the second hand may not create a *_skeleton object of its own.
    arm = bpy.data.objects.get(f"{name}_skeleton") or bpy.data.objects.get("hand_r_skeleton")
    mesh = bpy.data.objects.get(name)
    if arm is None or mesh is None:
        raise RuntimeError(f"import failed for {path}")
    return arm, mesh


def add_cylinder(name, location, radius=0.94, depth=3.2):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=24,
        radius=radius,
        depth=depth,
        location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.display_type = "WIRE"
    return obj


def add_trigger(name, location):
    bpy.ops.mesh.primitive_cube_add(size=0.45, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.display_type = "WIRE"
    return obj


def apply_curl(arm, fingers, amount, index_scale=1.0, thumb_scale=1.0):
    for finger, chain in fingers.items():
        for depth, bone_name in enumerate(chain):
            bone = arm.pose.bones.get(bone_name)
            if bone is None:
                continue
            scale = thumb_scale if finger == "thumb" else (index_scale if finger == "index" else 1.0)
            angle = amount * scale * (1.0 - 0.15 * depth)
            bone.rotation_mode = "QUATERNION"
            bone.rotation_quaternion = Quaternion((0.0, 0.0, 1.0), angle)


def key_both(arm, name, right_amount, left_amount,
             right_index=1.0, left_index=1.0,
             right_thumb=1.0, left_thumb=1.0):
    action = bpy.data.actions.new(name)
    arm.animation_data_create()
    arm.animation_data.action = action
    apply_curl(arm, RIGHT_FINGERS, right_amount, right_index, right_thumb)
    apply_curl(arm, LEFT_FINGERS, left_amount, left_index, left_thumb)
    for chain in (RIGHT_FINGERS, LEFT_FINGERS):
        for bone_name in [b for c in chain.values() for b in c]:
            bone = arm.pose.bones.get(bone_name)
            if bone:
                bone.keyframe_insert("rotation_quaternion", frame=1)
    action.use_fake_user = True
    return action


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    clear_scene()

    right_arm, right_mesh = import_hand("hand_r")
    left_arm, left_mesh = import_hand("hand_l")

    # Both meshes share one armature, which is exactly the two-bodygroup
    # contract of the runtime hand model. Keep both at the palm origin and hide
    # the left mesh in this reference view so the right grip is readable.
    right_mesh.location = (0.0, 0.0, 0.0)
    left_mesh.location = (0.0, 0.0, 0.0)
    left_mesh.hide_viewport = True
    left_mesh.hide_render = True

    # Reference controller handle and trigger, in authored SMD space.
    add_cylinder("REF_ControllerHandle_R", (0.0, 0.0, 0.0))
    add_trigger("REF_Trigger_R", (0.7, -1.6, 0.55))
    left_handle = add_cylinder("REF_ControllerHandle_L", (0.0, 0.0, 0.0))
    left_trigger = add_trigger("REF_Trigger_L", (0.7, -1.6, 0.55))
    left_handle.hide_viewport = True
    left_trigger.hide_viewport = True

    # Pose actions. The engine currently drives the fingers procedurally; these
    # actions are reference/calibration poses for the pilot and future runtime
    # sequence support.
    actions = {}
    actions["ref_open"] = key_both(right_arm, "ref_open", 0.0, 0.0)
    actions["ref_fist"] = key_both(right_arm, "ref_fist", 1.40, 1.40)
    actions["ref_pistol"] = key_both(
        right_arm, "ref_pistol", 1.20, 1.20,
        right_index=0.20, left_index=0.70,
        right_thumb=0.55, left_thumb=0.50,
    )
    actions["ref_support"] = key_both(
        right_arm, "ref_support", 0.0, 1.20,
        right_index=1.0, left_index=0.70,
        right_thumb=1.0, left_thumb=0.50,
    )

    # Leave the right hand in the pistol pose and the left hand in support.
    right_arm.animation_data.action = actions["ref_pistol"]
    bpy.context.scene.frame_set(1)

    # Save the reproducible scene.
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    result = {
        "blend": BLEND_PATH,
        "right_arm": right_arm.name,
        "left_arm": left_arm.name,
        "actions": sorted(actions),
        "objects": [o.name for o in bpy.context.scene.objects],
    }
    return result


if __name__ == "__main__":
    print(main())
