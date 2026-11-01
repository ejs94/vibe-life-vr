#!/usr/bin/env python3
"""W1 coordinate calibration in a PCA-derived weapon-local frame.

The raw SMD is rotated relative to Blender. This script computes the weapon's
long/up/width axes from the source mesh, transforms the calibration scene into
that local frame, and renders a straight orthographic side view plus muzzle and
top views. Human sign-off is still required.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Quaternion, Vector

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.dont_write_bytecode = True
import blender_weapon_review as review  # noqa: E402

SOURCE = REPO / "out" / "mmod_import" / "decompiled" / "v_9mmhandgun"
BODY = "glock_reference"


def make_marker(name, local_position, color):
    # local display frame is (length, width, up) -> Blender (X, Y, Z)
    location = Vector((local_position[0], local_position[1], local_position[2]))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.14, location=location)
    obj = bpy.context.object
    obj.name = name
    mat = bpy.data.materials.new(name + "_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        # Pure emission at unit strength keeps the calibration colors distinct;
        # higher strengths clip channels and turn green/blue into cyan.
        bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 1.0
    obj.data.materials.append(mat)
    return obj


def ortho_render(scene, camera, out_dir, name, target, direction, scale, track_up, roll_180=False):
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = scale
    camera.location = target + direction.normalized() * 20.0
    rotation = (target - camera.location).to_track_quat("-Z", track_up)
    if roll_180:
        rotation = rotation @ Quaternion((0.0, 0.0, 1.0), math.pi)
    camera.rotation_euler = rotation.to_euler()
    scene.render.filepath = str(out_dir / f"{name}.png")
    bpy.ops.render.render(write_still=True)


def main() -> int:
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    out_dir = Path(args[args.index("--out") + 1]) if "--out" in args else REPO / "out" / "qa" / "W1" / "latest"
    out_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene, camera = review.setup_scene(out_dir, 16)
    scene.view_settings.view_transform = "Standard"
    try:
        scene.view_settings.look = "None"
    except TypeError:
        pass
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
    up_min, up_max = local[:, 1].min(), local[:, 1].max()
    width_min, width_max = local[:, 2].min(), local[:, 2].max()
    width_center = float((width_min + width_max) * 0.5)

    # Transform the body into the local display frame: (length, width, up).
    for index, vertex in enumerate(body.data.vertices):
        l, u, w = local[index]
        vertex.co = (l, w, u)
    body.data.update()

    # The PCA long axis follows the whole body, including the grip, so the
    # slide top can still be pitched a few degrees. Measure the side silhouette
    # and rotate the local frame around width until the slide top is level.
    probe_target = Vector(
        ((length_min + length_max) * 0.5, width_center, (up_min + up_max) * 0.5)
    )
    probe_scale = max(1.0, (length_max - length_min) * 1.15)
    ortho_render(
        scene, camera, out_dir, "side_probe", probe_target,
        Vector((0.0, 1.0, 0.0)), probe_scale, "Z",
    )
    probe = bpy.data.images.load(str(out_dir / "side_probe.png"), check_existing=False)
    probe_w, probe_h = probe.size
    pixels = np.array(probe.pixels[:], dtype=np.float32).reshape(probe_h, probe_w, 4)
    lum = pixels[:, :, :3].mean(axis=2)
    silhouette = lum > 0.03
    columns = []
    top_rows = []
    for column in range(probe_w):
        rows = np.where(silhouette[:, column])[0]
        if rows.size:
            columns.append(column)
            top_rows.append(rows.max())  # Blender images are bottom-up.
    pitch_deg = 0.0
    if len(columns) > 20:
        columns = np.asarray(columns, dtype=np.float64)
        top_rows = np.asarray(top_rows, dtype=np.float64)
        span = columns.max() - columns.min()
        selected = (
            (columns > columns.min() + 0.08 * span)
            & (columns < columns.min() + 0.92 * span)
        )
        fit = np.polyfit(columns[selected], top_rows[selected], 1)
        for _ in range(10):
            residual = np.abs(top_rows - np.polyval(fit, columns))
            keep = residual < 4.0
            if keep.sum() < 20:
                break
            fit = np.polyfit(columns[keep], top_rows[keep], 1)
        slope = float(fit[0])
        if abs(slope) > 0.02:
            theta = float(np.arctan(slope))
            cos_theta, sin_theta = np.cos(theta), np.sin(theta)
            old_long, old_up = long_axis.copy(), up_axis.copy()
            local[:, 0], local[:, 1] = (
                cos_theta * local[:, 0] + sin_theta * local[:, 1],
                -sin_theta * local[:, 0] + cos_theta * local[:, 1],
            )
            long_axis = cos_theta * old_long + sin_theta * old_up
            up_axis = -sin_theta * old_long + cos_theta * old_up
            pitch_deg = float(np.degrees(theta))
            for index, vertex in enumerate(body.data.vertices):
                l, u, w = local[index]
                vertex.co = (l, w, u)
            body.data.update()
            length_min, length_max = local[:, 0].min(), local[:, 0].max()
            up_min, up_max = local[:, 1].min(), local[:, 1].max()
            width_min, width_max = local[:, 2].min(), local[:, 2].max()
            width_center = float((width_min + width_max) * 0.5)
    length_range = length_max - length_min

    def material_front_center(material_substring: str):
        """Center of the front face of a material, in local display coords."""
        material_indices = {
            index
            for index, material in enumerate(body.data.materials)
            if material and material_substring in material.name.lower()
        }
        if not material_indices:
            return None
        vertex_indices = set()
        for polygon in body.data.polygons:
            if polygon.material_index in material_indices:
                vertex_indices.update(polygon.vertices)
        if not vertex_indices:
            return None
        coords = np.array([body.data.vertices[index].co[:] for index in vertex_indices])
        front_min = coords[:, 0].min()
        front = coords[coords[:, 0] < front_min + 0.30]
        # local display is (length, width, up)
        return front.mean(axis=0)

    # The red marker belongs to the barrel cylinder, not the slide face. The
    # chrome material contains the barrel; its frontmost face is the muzzle.
    barrel_center = material_front_center("chrome")
    if barrel_center is not None:
        muzzle_l = float(barrel_center[0])
        muzzle_w = float(barrel_center[1])
        muzzle_u = float(barrel_center[2])
    else:
        muzzle_l = length_min + length_range * 0.060
        muzzle_u = up_min + 2.00
        muzzle_w = width_center

    # Trigger center from the maintainer's annotation on side_labeled.png:
    # pixel (358, 310) maps to local (0.050, 1.026) in this calibrated view.
    trigger_l = length_min + length_range * 0.5686
    trigger_u = up_min + 2.9042
    slide_l = length_max - 2.0
    slide_u = up_min - 0.12
    hammer_l = length_max - 0.65
    hammer_u = up_min + 0.80

    landmarks = {
        "muzzle": (muzzle_l, muzzle_u, muzzle_w),
        "trigger": (trigger_l, trigger_u, width_center),
        "slide": (slide_l, slide_u, width_center),
        "hammer": (hammer_l, hammer_u, width_center),
    }
    colors = {
        "muzzle": (1.0, 0.05, 0.05),
        "trigger": (0.05, 0.15, 1.0),
        "slide": (0.05, 1.0, 0.20),
        "hammer": (1.0, 0.8, 0.05),
    }
    objects = [body]
    markers = []
    landmark_data = {}
    for name, (l, u, w) in landmarks.items():
        marker = make_marker(name, (l, w, u), colors[name])
        markers.append(marker)
        objects.append(marker)
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

    # The default review lights sit near the origin, but this weapon is about
    # ten local units long and the muzzle is at x=-5. Add a front fill so the
    # muzzle face is readable instead of a black silhouette.
    front_light_data = bpy.data.lights.new("FrontFill", type="AREA")
    front_light_data.energy = 650.0
    front_light_data.size = 4.0
    front_light = bpy.data.objects.new("FrontFill", front_light_data)
    scene.collection.objects.link(front_light)
    front_light.location = Vector((length_min - 4.0, width_center, up_min + 1.5))
    front_light.rotation_euler = (
        Vector((length_min, width_center, (up_min + up_max) * 0.5)) - front_light.location
    ).to_track_quat("-Z", "Y").to_euler()

    views = {
        # Side: +Y camera, Z roll -> length horizontal, grip down.
        "side": (
            Vector(((length_min + length_max) * 0.5, width_center, (up_min + up_max) * 0.5)),
            Vector((0.0, 1.0, 0.0)), ortho_side, "Z", 0.0, False,
        ),
        # Muzzle: camera at -X, looking +X. The standard Y roll puts U up,
        # so roll 180 degrees to match the side view (top of slide at top).
        "muzzle": (
            Vector((length_min - 0.2, width_center, (up_min + up_max) * 0.5)),
            Vector((-1.0, 0.0, 0.0)), ortho_muzzle, "Y", 0.8, True,
        ),
        # Top: +Z camera, Y roll -> length horizontal.
        "top": (
            Vector(((length_min + length_max) * 0.5, width_center, up_max + 0.5)),
            Vector((0.0, 0.0, 1.0)), ortho_side, "Y", 0.0, False,
        ),
    }

    # Markers are composited over the body so a marker at the true width center
    # (for example the trigger) is still visible in the side and muzzle views.
    for name, (target, direction, scale, view_track_up, exposure, roll_180) in views.items():
        scene.view_settings.exposure = exposure
        scene.render.image_settings.color_mode = "RGB"
        scene.render.film_transparent = False
        for marker in markers:
            marker.hide_render = True
        ortho_render(scene, camera, out_dir, f"{name}_body", target, direction, scale, view_track_up, roll_180)

        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = True
        for marker in markers:
            marker.hide_render = False
        body.hide_render = True
        ortho_render(scene, camera, out_dir, f"{name}_markers", target, direction, scale, view_track_up, roll_180)
        body.hide_render = False
        scene.render.film_transparent = False

        body_path = out_dir / f"{name}_body.png"
        markers_path = out_dir / f"{name}_markers.png"
        composite_path = out_dir / f"{name}.png"
        subprocess.run(
            ["magick", str(body_path), str(markers_path), "-compose", "over", "-composite", str(composite_path)],
            check=False,
        )
    scene.view_settings.exposure = 0.0

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
        "pitch_correction_deg": pitch_deg,
        "human_trigger_mark": {
            "side_pixel": [358.0, 309.9],
            "local": [0.0495, 1.0257, width_center],
            "source": "maintainer annotation on side_labeled.png",
        },
        "landmarks": landmark_data,
        "views": {
            "side": "orthographic +Y, up Z",
            "muzzle": "orthographic -X, up Z",
            "top": "orthographic +Z, up Y",
        },
        "human_approved": False,
        "notes": "Red=barrel cylinder/bore, blue=trigger blade, green=rear sight/slide, yellow=hammer. Markers are x-ray composited so the centered trigger stays visible. Human must confirm the straight side view before W2.",
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
    legend = out_dir / "legend.png"
    subprocess.run(
        [
            "magick", "-size", "420x420", "xc:#20242b", "-gravity", "northwest",
            "-pointsize", "22", "-fill", "white", "-annotate", "+20+24", "LEGEND",
            "-pointsize", "18",
            "-fill", "#ff3333", "-annotate", "+20+86", "RED   barrel bore (cano)",
            "-fill", "#3060ff", "-annotate", "+20+126", "BLUE  trigger (gatilho)",
            "-fill", "#33ff55", "-annotate", "+20+166", "GREEN rear sight (mira)",
            "-fill", "#ffdd33", "-annotate", "+20+206", "YELLOW hammer",
            str(legend),
        ],
        check=False,
    )
    subprocess.run(
        ["magick", "montage", *labeled, str(legend), "-tile", "4x1", "-geometry", "420x420+4+4",
         "-background", "#20242b", str(out_dir / "calibration_sheet.png")],
        check=False,
    )
    bpy.ops.wm.save_as_mainfile(filepath=str(out_dir / "calibration.blend"))
    print(f"wrote local-frame calibration to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
