#!/usr/bin/env python3
"""Headless Blender review renderer for a decompiled GoldSrc weapon.

The renderer imports the static ``$body`` meshes in bind pose, applies the SMD
bone matrices so detached magazine/suppressor bodies assemble correctly, loads
the textures, and renders fixed front/right/left/top/bottom/rear/quarter views
plus a turntable. It is evidence tooling, not a model editor.

Run:
  blender --background --factory-startup --python scripts/blender_weapon_review.py -- \
      --qc out/ab/entry_a/patched/v_9mmhandgun.qc \
      --out out/qa/AB/neutral/entry_a_patched \
      --label entry_a_patched
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import bpy
from mathutils import Euler, Matrix, Vector

BODY_RE = re.compile(r'^\s*\$body\s+"([^"]+)"\s+"([^"]+)"', re.I)
BODYGROUP_RE = re.compile(r'^\s*\$bodygroup\s+"([^"]+)"', re.I)
SKIP_RE = re.compile(r"(^|[_\s])(hands?|forearms?|sleeves?|cuffs?|player_arm|trits|silencer)([_\s]|$)", re.I)
SCALE = 0.025  # GoldSrc units to metres (vr_worldscale 40 units/m)


def parse_qc(qc: Path) -> list[tuple[str, str]]:
    bodies = []
    lines = qc.read_text(encoding="latin1", errors="replace").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        match = BODY_RE.match(line)
        if match:
            name, smd = match.group(1), match.group(2)
            if not SKIP_RE.search(name) and not SKIP_RE.search(smd):
                bodies.append((name, smd))
            index += 1
            continue
        group = BODYGROUP_RE.match(line)
        if group:
            # Skip bodygroups entirely; their first option is usually blank.
            depth = 0
            while index < len(lines):
                if "{" in lines[index]:
                    depth += 1
                if "}" in lines[index]:
                    depth -= 1
                    if depth == 0:
                        break
                index += 1
        index += 1
    return bodies


def parse_smd(path: Path):
    nodes: dict[int, tuple[str, int]] = {}
    frames: dict[int, tuple[tuple[float, float, float], tuple[float, float, float]]] = {}
    triangles = []
    material = "default"
    section = None
    current = None
    for raw in path.read_text(encoding="latin1", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line in ("nodes", "skeleton", "triangles"):
            section = line
            continue
        if line == "end":
            if section == "triangles" and current is not None:
                triangles.append((material, current))
                current = None
            section = None
            continue
        if section == "nodes":
            match = re.match(r'^\s*(\d+)\s+"([^"]*)"\s+(-?\d+)\s*$', line)
            if match:
                nodes[int(match.group(1))] = (match.group(2), int(match.group(3)))
        elif section == "skeleton":
            parts = line.split()
            if len(parts) == 7 and parts[0] != "time":
                idx = int(parts[0])
                if idx not in frames:
                    frames[idx] = (
                        (float(parts[1]), float(parts[2]), float(parts[3])),
                        (float(parts[4]), float(parts[5]), float(parts[6])),
                    )
        elif section == "triangles":
            parts = line.split()
            if len(parts) == 1:
                if current is not None:
                    triangles.append((material, current))
                material = parts[0]
                current = []
            elif current is not None and len(parts) >= 9:
                current.append(
                    {
                        "bone": int(parts[0]),
                        "pos": (float(parts[1]), float(parts[2]), float(parts[3])),
                        "normal": (float(parts[4]), float(parts[5]), float(parts[6])),
                        "uv": (float(parts[7]), float(parts[8])),
                    }
                )
    if current is not None and len(current) >= 3:
        triangles.append((material, current))
    return nodes, frames, triangles


def bone_world(nodes, frames):
    world: dict[int, Matrix] = {}
    visiting: set[int] = set()

    def build(index: int) -> Matrix:
        if index in world:
            return world[index]
        parent = nodes.get(index, ("", -1))[1]
        local = Matrix.Identity(4)
        if index in frames:
            pos, rot = frames[index]
            local = Matrix.Translation(Vector(pos)) @ Euler(rot, "XYZ").to_matrix().to_4x4()
        if parent >= 0 and parent not in visiting:
            visiting.add(index)
            parent_world = build(parent)
            visiting.discard(index)
            world[index] = parent_world @ local
        else:
            world[index] = local
        return world[index]

    for index in nodes:
        build(index)
    return world


def axis_map(position: Vector) -> Vector:
    # GoldSrc: X forward, Y left, Z up. Blender: X right, Y forward, Z up.
    return Vector((-position.y, position.x, position.z)) * SCALE


def texture_candidates(model_dir: Path, name: str):
    stem = Path(name).stem
    for candidate in (
        model_dir / name,
        model_dir / f"{stem}.bmp",
        model_dir / f"{stem}.BMP",
        model_dir / f"{stem}.tga",
        model_dir / f"{stem}.png",
    ):
        if candidate.is_file():
            return candidate
    return None


def material_for(name: str, model_dir: Path):
    material = bpy.data.materials.get(name)
    if material:
        return material
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf is None:
        return material
    texture = texture_candidates(model_dir, name)
    if texture:
        image = bpy.data.images.load(str(texture), check_existing=True)
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = "Closest"
        material.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        hash_value = sum(ord(ch) for ch in name.lower())
        bsdf.inputs["Base Color"].default_value = (
            0.18 + (hash_value % 40) / 100.0,
            0.18 + (hash_value % 31) / 100.0,
            0.18 + (hash_value % 23) / 100.0,
            1.0,
        )
    lower = name.lower()
    if "chrome" in lower or "steel" in lower:
        bsdf.inputs["Metallic"].default_value = 0.85
        bsdf.inputs["Roughness"].default_value = 0.22
    else:
        bsdf.inputs["Roughness"].default_value = 0.58
    return material



def filter_components(triangles):
    """Drop tiny helper boxes at the model origin; keep real detached parts visible."""
    if not triangles:
        return triangles
    lookup = {}
    parent = []

    def vertex_id(position):
        key = tuple(round(float(value), 3) for value in position)
        index = lookup.get(key)
        if index is None:
            index = len(parent)
            lookup[key] = index
            parent.append(index)
        return index

    tri_ids = []
    for _, tri in triangles:
        if len(tri) < 3:
            continue
        tri_ids.append([vertex_id(vertex["pos"]) for vertex in tri])

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a, b):
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    for ids in tri_ids:
        for a, b in ((ids[0], ids[1]), (ids[1], ids[2]), (ids[2], ids[0])):
            union(a, b)

    groups = {}
    for index, ids in enumerate(tri_ids):
        groups.setdefault(find(ids[0]), []).append(index)

    keep = []
    for indices in groups.values():
        points = [
            triangles[index][1][vertex_index]["pos"]
            for index in indices
            for vertex_index in range(len(triangles[index][1]))
        ]
        minimum = [min(point[axis] for point in points) for axis in range(3)]
        maximum = [max(point[axis] for point in points) for axis in range(3)]
        center = [(minimum[axis] + maximum[axis]) * 0.5 for axis in range(3)]
        size = max(maximum[axis] - minimum[axis] for axis in range(3))
        near_origin = all(abs(center[axis]) < 1.5 for axis in range(3))
        if near_origin and size < 2.5:
            continue  # authored unit helper box
        keep.extend(indices)
    keep.sort()
    return [triangles[index] for index in keep]

def import_body(model_dir: Path, body_name: str, smd_name: str, apply_bones: bool = False):
    smd_path = model_dir / f"{smd_name}.smd"
    if not smd_path.is_file():
        print(f"warning: missing {smd_path}", file=sys.stderr)
        return None
    nodes, frames, triangles = parse_smd(smd_path)
    world = bone_world(nodes, frames)
    triangles = filter_components(triangles)

    vertices = []
    faces = []
    face_uvs = []
    face_materials = []
    materials = []
    material_index: dict[str, int] = {}

    for material_name, tri in triangles:
        if len(tri) < 3:
            continue
        if material_name not in material_index:
            material_index[material_name] = len(materials)
            materials.append(material_for(material_name, model_dir))
        base = len(vertices)
        for vertex in tri:
            if apply_bones:
                bone = world.get(vertex["bone"], Matrix.Identity(4))
                position = axis_map(bone @ Vector(vertex["pos"]))
            else:
                position = axis_map(Vector(vertex["pos"]))
            vertices.append(tuple(position))
        for offset in range(1, len(tri) - 1):
            faces.append((base, base + offset, base + offset + 1))
            face_uvs.append(
                (
                    tri[0]["uv"],
                    tri[offset]["uv"],
                    tri[offset + 1]["uv"],
                )
            )
            face_materials.append(material_index[material_name])

    mesh = bpy.data.meshes.new(f"{body_name}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon, uvs in zip(mesh.polygons, face_uvs):
        for loop_offset in range(polygon.loop_total):
            uv_layer.data[polygon.loop_start + loop_offset].uv = uvs[loop_offset]
    for material in materials:
        mesh.materials.append(material)
    for polygon, material_index_value in zip(mesh.polygons, face_materials):
        polygon.material_index = material_index_value
    obj = bpy.data.objects.new(body_name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def setup_scene(out_dir: Path, samples: int):
    scene = bpy.context.scene
    available = scene.render.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in available else "BLENDER_EEVEE"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    try:
        scene.eevee.taa_render_samples = samples
    except AttributeError:
        pass
    scene.world = bpy.data.worlds.new("ReviewWorld")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes["Background"]
    background.inputs[0].default_value = (0.028, 0.032, 0.040, 1.0)
    background.inputs[1].default_value = 0.35

    for name, location, energy, size in (
        ("Key", (1.4, 1.8, 2.0), 240.0, 1.5),
        ("Fill", (-1.8, 1.2, 0.8), 110.0, 1.8),
        ("Rim", (0.4, -1.8, 1.4), 170.0, 1.2),
    ):
        light_data = bpy.data.lights.new(name, type="AREA")
        light_data.energy = energy
        light_data.size = size
        light = bpy.data.objects.new(name, light_data)
        scene.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (-light.location).to_track_quat("-Z", "Y").to_euler()

    camera_data = bpy.data.cameras.new("ReviewCamera")
    camera_data.lens = 50
    camera = bpy.data.objects.new("ReviewCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    return scene, camera


def model_bounds(objects):
    points = []
    for obj in objects:
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    minimum = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maximum = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return minimum, maximum


def look_at(camera, target: Vector):
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def render_view(scene, camera, out_dir: Path, name: str, center: Vector, radius: float, direction: Vector):
    direction = direction.normalized()
    camera.location = center + direction * radius
    look_at(camera, center)
    path = out_dir / f"{name}.png"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


def main() -> int:
    argv = sys.argv
    separator = argv.index("--") if "--" in argv else len(argv)
    args = argv[separator + 1 :]
    parser = argparse.ArgumentParser()
    parser.add_argument("--qc", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--label", default="weapon")
    parser.add_argument("--samples", type=int, default=12)
    parser.add_argument("--turntable-frames", type=int, default=24)
    parser.add_argument("--body", default="", help="body name or SMD stem to render; default first body")
    parser.add_argument("--all-bodies", action="store_true", help="render every imported body")
    parsed = parser.parse_args(args)

    qc = Path(parsed.qc).resolve()
    out_dir = Path(parsed.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    model_dir = qc.parent

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene, camera = setup_scene(out_dir, parsed.samples)

    bodies = parse_qc(qc)
    if parsed.body:
        bodies = [item for item in bodies if parsed.body in item]
    elif not parsed.all_bodies:
        bodies = bodies[:1]
    print("selected bodies:", bodies)
    objects = []
    for body_name, smd_name in bodies:
        obj = import_body(model_dir, body_name, smd_name)
        if obj:
            objects.append(obj)
    if not objects:
        print("error: no bodies imported", file=sys.stderr)
        return 1

    minimum, maximum = model_bounds(objects)
    center = (minimum + maximum) * 0.5
    size = maximum - minimum
    max_dim = max(size.x, size.y, size.z)
    radius = max(0.18, max_dim * 2.4)

    # The raw viewmodel axes are X = left/right, Y = up/down, Z = forward/back.
    # The harness maps raw X to Blender Y, raw Y to Blender -X and raw Z to
    # Blender Z, so the semantic views are chosen in that mapped space.
    muzzle_target = center + Vector((0.0, 0.0, size.z * 0.45))
    muzzle_radius = max(0.06, max(size.x, size.y) * 0.55)
    rear_target = center - Vector((0.0, 0.0, size.z * 0.45))
    rear_radius = max(0.06, max(size.x, size.y) * 0.55)
    views = [
        ("muzzle", Vector((0.0, 0.0, 1.0)), muzzle_target, muzzle_radius),
        ("rear", Vector((0.0, 0.0, -1.0)), rear_target, rear_radius),
        ("right", Vector((0.0, 1.0, 0.12)), center, radius),
        ("left", Vector((0.0, -1.0, 0.12)), center, radius),
        ("top", Vector((-1.0, 0.0, 0.12)), center, radius),
        ("bottom", Vector((1.0, 0.0, 0.12)), center, radius),
        ("quarter", Vector((0.8, 0.9, 0.45)), center, radius),
    ]
    manifest = {
        "label": parsed.label,
        "qc": str(qc.relative_to(Path.cwd())) if qc.is_relative_to(Path.cwd()) else str(qc),
        "bodies": [name for name, _ in bodies],
        "bounds_min": list(minimum),
        "bounds_max": list(maximum),
        "views": {},
    }
    for name, direction, target, view_radius in views:
        render_view(scene, camera, out_dir, name, target, view_radius, direction)
        manifest["views"][name] = {
            "camera": list(camera.location),
            "target": list(target),
            "radius": view_radius,
        }

    frame_dir = out_dir / "turntable_frames"
    frame_dir.mkdir(exist_ok=True)
    for frame in range(parsed.turntable_frames):
        azimuth = 2.0 * math.pi * frame / parsed.turntable_frames
        elevation = math.radians(15.0)
        direction = Vector(
            (
                math.cos(elevation) * math.cos(azimuth),
                math.cos(elevation) * math.sin(azimuth),
                math.sin(elevation),
            )
        )
        render_view(scene, camera, frame_dir, f"turntable_{frame:03d}", center, radius, direction)

    manifest["turntable_frames"] = parsed.turntable_frames
    (out_dir / "render_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"rendered {len(views)} views and {parsed.turntable_frames} turntable frames to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
