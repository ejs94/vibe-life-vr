#!/usr/bin/env python3
"""W1 coordinate calibration for the Glock viewmodel.

Imports the source body, places colour-coded landmark markers, renders
orthographic side/front/top views, and writes the coordinate contract used by
the native weapon pipeline. This is a human-reviewed calibration gate.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.dont_write_bytecode = True
import blender_weapon_review as review  # noqa: E402

SOURCE = REPO / "out" / "mmod_import" / "decompiled" / "v_9mmhandgun"
BODY = "glock_reference"


def marker(name, raw_position, color):
    location = review.axis_map(Vector(raw_position))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.006, location=location)
    obj = bpy.context.object
    obj.name = name
    mat = bpy.data.materials.new(name + "_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 3.0
    obj.data.materials.append(mat)
    return obj


def ortho_camera(camera, center, direction, scale, up_axis="X"):
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = scale
    camera.location = center + direction.normalized() * 1.0
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", up_axis).to_euler()


def main() -> int:
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    out_dir = Path(args[args.index("--out") + 1]) if "--out" in args else REPO / "out" / "qa" / "W1" / "latest"
    out_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene, camera = review.setup_scene(out_dir, 16)
    body = review.import_body(SOURCE, "body", BODY)
    if body is None:
        raise SystemExit("source body missing")

    landmarks = {
        # Raw SMD space. Negative Y is visually up in the decompiled viewmodel;
        # positive Y is down. Markers sit just outside the shell so they are
        # visible in the orthographic side view.
        "muzzle": ((-8.00, -1.50, 35.70), (1.0, 0.05, 0.05)),
        "trigger": ((-8.00, 2.40, 28.60), (0.05, 0.15, 1.0)),
        "top": ((-8.00, -4.90, 31.00), (0.05, 1.0, 0.20)),
    }
    objects = [body]
    marker_data = {}
    for name, (raw, color) in landmarks.items():
        objects.append(marker(name, raw, color))
        marker_data[name] = {
            "raw": list(raw),
            "blender": list(review.axis_map(Vector(raw))),
            "color": color,
        }

    minimum, maximum = review.model_bounds(objects)
    center = (minimum + maximum) * 0.5
    size = maximum - minimum
    max_dim = max(size.x, size.y, size.z)
    scale = max_dim * 1.25

    views = [
        ("side", Vector((0.0, 1.0, 0.0)), center, scale, "X"),
        ("muzzle", Vector((0.0, 0.0, 1.0)), center + Vector((0.0, 0.0, size.z * 0.45)), max(0.08, max(size.x, size.y) * 1.8), "X"),
        ("top", Vector((-1.0, 0.0, 0.0)), center, scale, "Z"),
    ]
    view_data = {}
    for name, direction, target, ortho_scale, up_axis in views:
        ortho_camera(camera, target, direction, ortho_scale, up_axis)
        path = out_dir / f"{name}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        view_data[name] = {
            "camera": list(camera.location),
            "target": list(target),
            "ortho_scale": ortho_scale,
        }

    contract = {
        "source": "out/mmod_import/decompiled/v_9mmhandgun",
        "body": BODY,
        "spaces": {
            "goldsrc_world": {"x": "forward", "y": "left", "z": "up"},
            "smd_viewmodel": {"x": "width", "y": "vertical", "z": "length"},
            "blender": {"x": "right", "y": "forward", "z": "up"},
        },
        "scale_m_per_unit": review.SCALE,
        "raw_to_blender": "blender = (-raw_y, raw_x, raw_z) * 0.025",
        "blender_to_raw": "raw = (blender_y / 0.025, -blender_x / 0.025, blender_z / 0.025)",
        "rotation_order": "Rz * Ry * Rx (SMD Euler, Blender XYZ)",
        "landmarks": marker_data,
        "views": view_data,
        "human_approved": False,
        "notes": "Colours: red=muzzle/front, blue=trigger/grip, green=top. Human must confirm FRONT/REAR before native modeling.",
    }
    (out_dir / "calibration.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    labeled = []
    for name, label in (("side", "SIDE"), ("muzzle", "MUZZLE"), ("top", "TOP")):
        src = out_dir / f"{name}.png"
        dst = out_dir / f"{name}_labeled.png"
        subprocess.run(
            ["magick", str(src), "-gravity", "northwest", "-pointsize", "22", "-fill", "white",
             "-undercolor", "#000000AA", "-annotate", "+10+10", label, str(dst)],
            check=False,
        )
        labeled.append(str(dst))
    subprocess.run(
        ["magick", "montage", *labeled, "-tile", "3x1", "-geometry", "420x420+4+4",
         "-background", "#20242b", str(out_dir / "calibration_sheet.png")],
        check=False,
    )
    print(f"wrote calibration to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
