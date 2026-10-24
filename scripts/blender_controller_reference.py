"""
Build a Blender reference scene with a Quest-style controller proxy and the
prepared right hand.

The goal is to stop guessing grip alignment: the hand is imported at its
GoldSrc scale (converted to metres), the controller proxy is placed at the
OpenXR grip origin, and the scene can be inspected or adjusted interactively.

Run headless:
  blender --background --python scripts/blender_controller_reference.py -- \
      out/twohand/hand_r.smd out/controller_reference

Outputs:
  out/controller_reference/controller_reference.blend
  out/controller_reference/controller_reference.png
  out/controller_reference/grip_reference.json
"""

from __future__ import annotations

import bpy
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smd_lib  # noqa: E402


def import_smd_manual(path, scale):
    """Import the rest-pose SMD without relying on the ValveSource addon."""
    smd = smd_lib.parse_smd(path)
    verts = []
    faces = []
    face_materials = []
    material_names = []
    material_map = {}

    for tri in smd.triangles:
        if len(tri.verts) < 3:
            continue
        base = len(verts)
        for vert in tri.verts:
            verts.append((vert.pos[0] * scale, vert.pos[1] * scale, vert.pos[2] * scale))
        for i in range(1, len(tri.verts) - 1):
            faces.append((base, base + i, base + i + 1))
            name = tri.material
            if name not in material_map:
                material_map[name] = len(material_names)
                material_names.append(name)
            face_materials.append(material_map[name])

    mesh = bpy.data.meshes.new("HandMesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    colors = {
        "glove_texture.bmp": (0.035, 0.033, 0.032),
        "gordon_sleeve.bmp": (0.42, 0.30, 0.18),
        "glove_inner.bmp": (0.008, 0.008, 0.008),
    }
    for name in material_names:
        mesh.materials.append(make_material(name, colors.get(name, (0.5, 0.5, 0.5))))

    for poly, mat_index in zip(mesh.polygons, face_materials):
        poly.material_index = mat_index

    obj = bpy.data.objects.new("Hand_R", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_material(name, color, roughness=0.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
    return mat


def add_proxy_controller():
    """Quest-like controller proxy: handle along Y, ring and face buttons."""
    handle_mat = make_material("ControllerHandle", (0.08, 0.08, 0.09), 0.55)
    ring_mat = make_material("ControllerRing", (0.55, 0.58, 0.62), 0.35)
    button_mat = make_material("ControllerButton", (0.10, 0.10, 0.11), 0.4)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.018, depth=0.115,
                                        location=(0, 0, 0),
                                        rotation=(math.pi / 2, 0, 0))
    handle = bpy.context.object
    handle.name = "ControllerHandle"
    handle.data.materials.append(handle_mat)

    bpy.ops.mesh.primitive_torus_add(major_radius=0.036, minor_radius=0.006,
                                     location=(0, 0.012, 0.062),
                                     rotation=(math.pi / 2, 0, 0))
    ring = bpy.context.object
    ring.name = "ControllerTrackingRing"
    ring.data.materials.append(ring_mat)

    for index, (x, y, z) in enumerate((
        (0.0, 0.020, 0.070),
        (0.0, -0.020, 0.070),
        (0.020, 0.0, 0.070),
        (-0.020, 0.0, 0.070),
    )):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.0055, depth=0.004,
                                            location=(x, y, z))
        button = bpy.context.object
        button.name = f"ControllerButton{index}"
        button.data.materials.append(button_mat)

    return handle


def setup_scene():
    scene = bpy.context.scene
    available = scene.render.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in available else "BLENDER_EEVEE"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 700
    scene.world = bpy.data.worlds.new("ControllerReferenceWorld")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.16, 0.17, 0.20, 1.0)
    bg.inputs[1].default_value = 1.0

    for name, location, energy in (
        ("Key", (0.6, -0.8, 0.7), 220.0),
        ("Fill", (-0.7, -0.5, 0.3), 80.0),
        ("Rim", (0.0, 0.8, 0.5), 120.0),
    ):
        data = bpy.data.lights.new(name, type="AREA")
        data.energy = energy
        data.size = 0.8
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (-obj.location).to_track_quat("-Z", "Y").to_euler()

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 55.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0.28, -0.34, 0.18)
    cam.rotation_euler = (-cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    return scene


def main():
    argv = sys.argv
    sep = argv.index("--") if "--" in argv else len(argv)
    args = argv[sep + 1:]
    if len(args) < 2:
        print("usage: blender_controller_reference.py -- <hand.smd> <outdir> [scale]")
        raise SystemExit(2)

    smd_path = args[0]
    outdir = args[1]
    hand_scale = float(args[2]) if len(args) > 2 else 0.025
    os.makedirs(outdir, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    import_smd_manual(smd_path, hand_scale)
    bpy.context.view_layer.update()

    add_proxy_controller()
    setup_scene()

    blend_path = os.path.join(outdir, "controller_reference.blend")
    png_path = os.path.join(outdir, "controller_reference.png")
    json_path = os.path.join(outdir, "grip_reference.json")

    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(blend_path))
    bpy.ops.render.render(write_still=True)
    bpy.data.images["Render Result"].save_render(png_path)

    data = {
        "hand_smd": os.path.basename(smd_path),
        "hand_scale_m_per_unit": hand_scale,
        "grip_origin_m": [0.0, 0.0, 0.0],
        "controller_handle_axis": "Y",
        "notes": [
            "Controller proxy is a shape reference, not a licensed Quest model.",
            "Adjust the hand transform until the palm wraps the handle, then read the offset in hand-local space.",
            "Exported weapon grip offsets are in GoldSrc units; convert metres by multiplying by vr_worldscale (40 units/m).",
        ],
    }
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    print("wrote:", blend_path, png_path, json_path)


if __name__ == "__main__":
    main()
