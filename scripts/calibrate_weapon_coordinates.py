#!/usr/bin/env python3
"""W1 coordinate calibration in a PCA-derived weapon-local frame.

The raw SMD is rotated relative to Blender. This script computes the weapon's
long/up/width axes from the source mesh, transforms the calibration scene into
that local frame, and renders a straight orthographic side view plus muzzle and
top views. Human sign-off is still required.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.dont_write_bytecode = True
import blender_weapon_review as review  # noqa: E402

SOURCE = REPO / "out" / "mmod_import" / "decompiled" / "v_9mmhandgun"
BODY = "glock_reference"


def make_marker(name, local_position, color):
    # local display frame is (length, width, up) -> Blender (X, Y, Z)
    location = Vector((local_position[0], local_position[1], local_position[2]))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.18, location=location)
    obj = bpy.context.object
    obj.name = name
    mat = bpy.data.materials.new(name + "_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 4.0
    obj.data.materials.append(mat)
    return obj


def ortho_render(scene, camera, out_dir, name, target, direction, scale, up_axis):
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = scale
    camera.location = target + direction.normalized() * 20.0
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", up_axis).to_euler()
    scene.render.filepath = str(out_dir / f"{name}.png")
    bpy.ops.render.render(write_still=True)


def main() -> int:
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    out_dir = Path(args[args.index("--out") + 1]) if "--out" in args else REPO / "out" / "qa" / "W1" / "latest"
    out_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene, camera = review.setup_scene(out_dir, 16)
    body = review.import_body(SOURCE, "body", BODY)
    if body is None:
        raise SystemExit("source body missing")

    # Convert the imported Blender mesh back to raw SMD coordinates, then fit
    # the weapon-local basis from the actual geometry.
    raw = []
    for vertex in body.data.vertices:
        bx, by, bz = vertex.co
        raw.append((by / review.SCALE, -bx / review.SCALE, bz / review.SCALE))
    raw = np.asarray(raw, dtype=np.float64)
    mean = raw.mean(axis=0)
    centered = raw - mean
    values, vectors = np.linalg.eigh(np.cov(centered.T))
    order = np.argsort(values)[::-1]
    vectors = vectors[:, order]
    long_axis = vectors[:, 0]
    up_axis = vectors[:, 1]
    width_axis = vectors[:, 2]

    # Raw Z positive points to the rear/hammer on this source; choose the long
    # axis sign so the rear/grip side is +L and the muzzle is -L.
    if long_axis[2] < 0:
        long_axis = -long_axis
    local = centered @ np.stack([long_axis, up_axis, width_axis], axis=1)
    # Up is high U. Flip if the largest upper cluster is on the wrong side.
    if local[:, 1].mean() < 0:
        up_axis = -up_axis
        local[:, 1] = -local[:, 1]
    # Keep width sign stable; it only mirrors the side view.
    length_min, length_max = local[:, 0].min(), local[:, 0].max()
    length_range = length_max - length_min
    up_min, up_max = local[:, 1].min(), local[:, 1].max()
    width_mid = float(np.median(local[:, 2]))
    width_near = float(local[:, 2].max()) + 0.25

    # Transform the body into the local display frame: (length, width, up).
    for index, vertex in enumerate(body.data.vertices):
        l, u, w = local[index]
        vertex.co = (l, w, u)
    body.data.update()

    def local_point(l, u, w=0.0):
        return (float(l), float(w), float(u))

    # Landmarks are derived from the local extents, not guessed raw axes.
    muzzle_l = length_min - 0.15
    muzzle_u = float(np.median(local[np.abs(local[:, 0] - length_min) < 0.9, 1]))
    trigger_l = length_min + length_range * 0.55
    trigger_u = up_max - 3.00
    slide_l = length_max - 2.0
    slide_u = up_min - 0.12
    hammer_l = length_max - 0.25
    hammer_u = up_min + 0.8

    landmarks = {
        "muzzle": (muzzle_l, muzzle_u, width_mid),
        "trigger": (trigger_l, trigger_u, width_near),
        "slide": (slide_l, slide_u, width_mid),
        "hammer": (hammer_l, hammer_u, width_mid),
    }
    colors = {
        "muzzle": (1.0, 0.05, 0.05),
        "trigger": (0.05, 0.15, 1.0),
        "slide": (0.05, 1.0, 0.20),
        "hammer": (1.0, 0.8, 0.05),
    }
    objects = [body]
    landmark_data = {}
    for name, (l, u, w) in landmarks.items():
        objects.append(make_marker(name, (l, w, u), colors[name]))
        landmark_data[name] = {
            "local": [float(l), float(u), float(w)],
            "display": [float(l), float(w), float(u)],
            "color": list(colors[name]),
        }

    minimum, maximum = review.model_bounds(objects)
    center = (minimum + maximum) * 0.5
    size = maximum - minimum
    ortho_side = max(1.0, length_range * 1.15)
    ortho_muzzle = max(1.0, (up_max - up_min) * 1.8)

    # Side: +Y camera, up Z -> length horizontal, up vertical.
    ortho_render(
        scene, camera, out_dir,
        "side", Vector((length_max * 0.5 + length_min * 0.5, width_mid, (up_min + up_max) * 0.5)),
        Vector((0.0, 1.0, 0.0)), ortho_side, "Z",
    )
    # Muzzle: camera at -X, looking +X, up Z.
    ortho_render(
        scene, camera, out_dir,
        "muzzle", Vector((length_min - 0.2, width_mid, (up_min + up_max) * 0.5)),
        Vector((-1.0, 0.0, 0.0)), ortho_muzzle, "Z",
    )
    # Top: +Z camera, up Y (width) -> length horizontal.
    ortho_render(
        scene, camera, out_dir,
        "top", Vector(((length_min + length_max) * 0.5, width_mid, up_max + 0.5)),
        Vector((0.0, 0.0, 1.0)), ortho_side, "Y",
    )

    contract = {
        "source": "out/mmod_import/decompiled/v_9mmhandgun",
        "body": BODY,
        "raw_mean": mean.tolist(),
        "local_basis": {
            "long": long_axis.tolist(),
            "up": up_axis.tolist(),
            "width": width_axis.tolist(),
        },
        "raw_to_local": "(raw - raw_mean) projected on [long, up, width]",
        "local_display": "(length, width, up) -> Blender (X, Y, Z)",
        "scale_m_per_unit": review.SCALE,
        "landmarks": landmark_data,
        "views": {
            "side": "orthographic +Y, up Z",
            "muzzle": "orthographic -X, up Z",
            "top": "orthographic +Z, up Y",
        },
        "human_approved": False,
        "notes": "Red=muzzle, blue=trigger, green=slide/serrations, yellow=hammer/rear. Human must confirm the straight side view before W2.",
    }
    (out_dir / "calibration.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    labeled = []
    for name in ("side", "muzzle", "top"):
        src = out_dir / f"{name}.png"
        dst = out_dir / f"{name}_labeled.png"
        subprocess.run(
            ["magick", str(src), "-gravity", "northwest", "-pointsize", "22", "-fill", "white",
             "-undercolor", "#000000AA", "-annotate", "+10+10", name.upper(), str(dst)],
            check=False,
        )
        labeled.append(str(dst))
    subprocess.run(
        ["magick", "montage", *labeled, "-tile", "3x1", "-geometry", "420x420+4+4",
         "-background", "#20242b", str(out_dir / "calibration_sheet.png")],
        check=False,
    )
    bpy.ops.wm.save_as_mainfile(filepath=str(out_dir / "calibration.blend"))
    print(f"wrote local-frame calibration to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
