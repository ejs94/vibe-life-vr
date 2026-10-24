"""
Render the prepared Rimrook hand model for visual review.

Imports the decompiled SMD (or a reference SMD), assigns the extracted BMP
textures as materials, and renders the open hand, a half curl and a closed fist
from two viewpoints. The curl composes a local-Z rotation onto each rest pose,
matching R_StudioApplyFingerCurling in ref/gl_vr/gl_studio.c.

Run headless:
  blender --background --python scripts/blender_render_hand.py -- <smd> <texdir> <outdir>
"""

import math
import os
import sys

import addon_utils
import bpy
from mathutils import Quaternion, Vector


def enable_valvesource():
    for module in addon_utils.modules():
        if "valvesource" in module.__name__:
            addon_utils.enable(module.__name__, default_set=True, persistent=True)
            return module.__name__
    return None


# Finger chains named as the engine expects, paired with curl axis signs so the
# render matches R_StudioApplyFingerCurling (rotation around the bone's local Z).
FINGER_CHAINS = {
    "thumb": ["Bone27", "Bone28"],
    "index": ["Bone31", "Bone32", "Bone33"],
    "middle": ["Bone35", "Bone36", "Bone37"],
    "ring": ["Bone39", "Bone40", "Bone41"],
    "pinky": ["Bone43", "Bone44", "Bone45"],
}


def assign_textures(mesh_obj, texdir):
    """Map the decompiled SMD's material slots to the extracted BMP files.

    Uses an emission-style unlit shader so the authored texture colours show
    exactly as authored (the glove is near-black by design and would otherwise
    be lost under lighting).
    """
    assigned = []
    for slot in mesh_obj.material_slots:
        mat = slot.material
        if mat is None:
            continue
        stem = mat.name.lower()
        if stem.endswith((".bmp", ".png", ".tga")):
            stem = os.path.splitext(stem)[0]
        candidate = None
        for ext in (".bmp", ".png", ".tga"):
            path = os.path.join(texdir, stem + ext)
            if os.path.exists(path):
                candidate = path
                break
        if candidate is None:
            print("no texture for material", mat.name)
            continue
        img = bpy.data.images.load(candidate)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        out = nodes.new("ShaderNodeOutputMaterial")
        emit = nodes.new("ShaderNodeEmission")
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.interpolation = "Closest"
        links.new(tex.outputs["Color"], emit.inputs["Color"])
        links.new(emit.outputs["Emission"], out.inputs["Surface"])
        assigned.append((mat.name, os.path.basename(candidate)))
    print("texture assignment:", assigned)


def curl_fingers(armature_obj, amount):
    """Bend the finger bones about local Z, exactly as the engine does.

    R_StudioApplyFingerCurling composes a rotation about each finger bone's
    local Z on top of its rest orientation. In Blender that is a pose transform
    equal to a pure rotation about the bone's local Z axis (matrix_basis), which
    preserves the rest pose instead of overwriting it.
    """
    for chain in FINGER_CHAINS.values():
        for depth, bone_name in enumerate(chain):
            bone = armature_obj.pose.bones.get(bone_name)
            if bone is None:
                continue
            bone.rotation_mode = "QUATERNION"
            angle = amount * (1.0 - 0.15 * depth)
            bone.rotation_quaternion = Quaternion((0.0, 0.0, 1.0), angle)



def setup_scene(outdir):
    scene = bpy.context.scene
    available = scene.render.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in available else "BLENDER_EEVEE"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 700
    scene.render.film_transparent = False
    scene.world = bpy.data.worlds.new("HandWorld")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.18, 0.19, 0.22, 1.0)
    bg.inputs[1].default_value = 1.0

    # Three-point-ish lighting.
    for name, loc, energy in (
        ("Key", (8.0, -10.0, 9.0), 1200.0),
        ("Fill", (-9.0, -6.0, 4.0), 500.0),
        ("Rim", (0.0, 10.0, 7.0), 700.0),
    ):
        light_data = bpy.data.lights.new(name, type="AREA")
        light_data.energy = energy
        light_data.size = 8.0
        light_obj = bpy.data.objects.new(name, light_data)
        scene.collection.objects.link(light_obj)
        light_obj.location = loc
        direction = -light_obj.location
        light_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    return scene


def add_camera(scene, target, angle_deg, distance=11.0):
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 55.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    rad = math.radians(angle_deg)
    cam.location = (
        target.x + distance * math.sin(rad),
        target.y - distance * math.cos(rad),
        target.z + 4.0,
    )
    look = target - cam.location
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    return cam


def main():
    argv = sys.argv
    sep = argv.index("--") if "--" in argv else len(argv)
    args = argv[sep + 1:]
    smd_path = args[0]
    texdir = args[1]
    outdir = args[2]

    os.makedirs(outdir, exist_ok=True)
    print("enabled addon:", enable_valvesource())

    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.import_scene.smd(filepath=smd_path)

    armature = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    mesh = next(o for o in bpy.data.objects if o.type == "MESH" and o.parent == armature)

    assign_textures(mesh, texdir)
    scene = setup_scene(outdir)
    scene.render.filepath = os.path.join(outdir, "hand_open.png")

    # Estimate the model centre for camera framing.
    coords = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    centre = sum(coords, Vector()) / len(coords)
    print("mesh centre:", tuple(round(c, 2) for c in centre),
          "verts:", len(mesh.data.vertices))

    add_camera(scene, centre, angle_deg=25.0)

    # Render open, half-curl and closed fist from the palm side and the back.
    stages = [("open", 0.0), ("half", 0.9), ("fist", 1.8)]
    for view_name, angle in (("palm", 25.0), ("back", 205.0)):
        add_camera(scene, centre, angle_deg=angle)
        for stage_name, amount in stages:
            curl_fingers(armature, amount)
            # Report the middle fingertip so the pose can be checked numerically
            # against the Python curl model, not only by eye.
            bpy.context.view_layer.update()
            tip = armature.pose.bones["Bone37"]
            world = armature.matrix_world @ tip.tail
            print(f"  {stage_name:5s} {view_name:4s} middle tip = "
                  f"({world.x:+.2f}, {world.y:+.2f}, {world.z:+.2f})")
            scene.render.filepath = os.path.join(
                outdir, f"hand_{stage_name}_{view_name}.png"
            )
            bpy.ops.render.render(write_still=True)

    print("rendered to", outdir)


if __name__ == "__main__":
    main()
