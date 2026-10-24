#!/usr/bin/env python3
"""Render a 360-degree geometry audit sheet for a decompiled GoldSrc model.

The input is a QC file produced by mdldec (or the original mod QC). The script
collects the static body meshes referenced by ``$body``, excludes embedded
hands/arms, and renders 16 orbit views with a small software rasterizer. It also
reports welded boundary/non-manifold edge counts as a cheap topology warning.

This is a geometry audit, not a replacement for the in-engine 360 capture: open
barrel mouths and magwells are expected, while missing receiver/stock faces show
up as large magenta backfaces or holes.

Usage:
    python3 scripts/render_mdl_360.py --qc path/to/model.qc --out out/audit
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HAND_RE = re.compile(
    r"(^|[_\s])(hands?|forearms?|sleeves?|cuffs?|player_arm)([_\s]|$)|hev_hands",
    re.I,
)
BODY_RE = re.compile(r'^\s*\$body\s+"([^"]+)"\s+"([^"]+)"', re.I)

AZIMUTHS = [0, 45, 90, 135, 180, 225, 270, 315]
ELEVATIONS = [0, 35, -35]
VIEW_W = 512
VIEW_H = 512
SS = 2
FOV_DEG = 34.0


def read_smd(path: Path):
    """Return triangles as (verts[3,3], normals[3,3], material)."""
    material = "default"
    in_triangles = False
    tris = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if line == "triangles":
                in_triangles = True
                material = "default"
                continue
            if not in_triangles:
                continue
            if line == "end":
                in_triangles = False
                continue
            if not line:
                continue
            parts = line.split()
            if len(parts) == 1:
                material = parts[0]
                continue
            if len(parts) < 9 or not parts[0].lstrip("-").isdigit():
                continue
            try:
                vert = np.array([float(parts[1]), float(parts[2]), float(parts[3])], dtype=np.float64)
                norm = np.array([float(parts[4]), float(parts[5]), float(parts[6])], dtype=np.float64)
            except ValueError:
                continue
            tris.append((vert, norm, material))
    if not tris:
        return np.zeros((0, 3, 3)), np.zeros((0, 3, 3)), []
    # Input SMD has one vertex per line and triangles are every three lines.
    if len(tris) % 3 == 0:
        grouped = [tris[i:i + 3] for i in range(0, len(tris), 3)]
    else:
        grouped = [tris[i:i + 3] for i in range(0, len(tris) - 2, 3)]
    verts = np.array([[p[0] for p in g] for g in grouped], dtype=np.float64)
    norms = np.array([[p[1] for p in g] for g in grouped], dtype=np.float64)
    mats = [g[0][2] for g in grouped]
    return verts, norms, mats


def parse_qc(qc_path: Path):
    lines = qc_path.read_text(encoding="utf-8", errors="replace").splitlines()
    bodies = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = BODY_RE.match(line)
        if m:
            body_name, smd_name = m.group(1), m.group(2)
            if not HAND_RE.search(body_name) and not HAND_RE.search(smd_name):
                bodies.append((body_name, smd_name))
            i += 1
            continue
        group = re.match(r'^\s*\$bodygroup\s+"([^"]+)"', line, re.I)
        if group:
            group_name = group.group(1)
            i += 1
            while i < len(lines) and "{" not in lines[i]:
                i += 1
            options = []
            i += 1
            while i < len(lines) and "}" not in lines[i]:
                option = re.match(r'^\s*studio\s+"([^"]+)"', lines[i], re.I)
                if option:
                    options.append(option.group(1))
                i += 1
            # Bodygroup 0 is the default used by the engine. Pick its first
            # non-hand option; a "blank" first option means the group is hidden.
            for smd_name in options:
                if smd_name.lower() == "blank" or HAND_RE.search(smd_name):
                    continue
                if not HAND_RE.search(group_name):
                    bodies.append((group_name, smd_name))
                break
            i += 1
            continue
        i += 1
    return bodies


def load_bodies(qc_path: Path):
    bodies = parse_qc(qc_path)
    if not bodies:
        raise SystemExit(f"no $body entries in {qc_path}")
    all_v, all_n, all_m, used = [], [], [], []
    base = qc_path.parent
    for body_name, smd_name in bodies:
        smd = base / f"{smd_name}.smd"
        if not smd.is_file():
            print(f"warning: missing {smd}", file=sys.stderr)
            continue
        v, n, m = read_smd(smd)
        if len(v) == 0:
            continue
        all_v.append(v)
        all_n.append(n)
        all_m.extend(m)
        used.append((body_name, smd.name, int(len(v))))
    if not all_v:
        raise SystemExit(f"no geometry for {qc_path}")
    return np.concatenate(all_v), np.concatenate(all_n), all_m, used


def edge_report(verts: np.ndarray):
    """Weld by rounded position and count boundary/non-manifold edges."""
    weld = {}
    ids = np.zeros((verts.shape[0], verts.shape[1]), dtype=np.int64)
    for ti in range(verts.shape[0]):
        for vi in range(3):
            key = tuple(np.round(verts[ti, vi], 3).tolist())
            idx = weld.get(key)
            if idx is None:
                idx = len(weld)
                weld[key] = idx
            ids[ti, vi] = idx
    edges = Counter()
    for tri in ids:
        if len(set(tri.tolist())) < 3:
            continue
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edges[tuple(sorted((int(a), int(b))))] += 1
    boundary = sum(1 for n in edges.values() if n == 1)
    nonmanifold = sum(1 for n in edges.values() if n > 2)
    return boundary, nonmanifold


def material_color(name: str):
    h = 0
    for ch in name.lower():
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    # Keep hues in a readable range and value high enough for small parts.
    hue = (h % 360) / 360.0
    sat = 0.28 + ((h >> 8) % 22) / 100.0
    val = 0.62 + ((h >> 16) % 24) / 100.0
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
    return np.array([r, g, b], dtype=np.float64)


def view_basis(az_deg: float, el_deg: float):
    az = math.radians(az_deg)
    el = math.radians(el_deg)
    offset = np.array([math.cos(el) * math.cos(az),
                       math.cos(el) * math.sin(az),
                       math.sin(el)], dtype=np.float64)
    world_up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    forward = -offset
    if abs(float(np.dot(forward, world_up))) > 0.995:
        world_up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    right = np.cross(forward, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return forward, right, up


def render_view(verts, norms, mats, colors, center, radius, az, el, label):
    direction, right, up = view_basis(az, el)
    camera = center - direction * radius
    focal = (VIEW_H * SS * 0.5) / math.tan(math.radians(FOV_DEG) * 0.5)
    cx = VIEW_W * SS * 0.5
    cy = VIEW_H * SS * 0.5

    rel = verts - camera
    x = np.einsum("tvi,i->tv", rel, right)
    y = np.einsum("tvi,i->tv", rel, up)
    z = np.einsum("tvi,i->tv", rel, direction)
    z = np.maximum(z, 1e-4)
    sx = cx + (x / z) * focal
    sy = cy - (y / z) * focal

    face_n = norms.mean(axis=1)
    face_n /= np.maximum(np.linalg.norm(face_n, axis=1, keepdims=True), 1e-8)

    # Use projected winding rather than the authored normal: the decompiled
    # SMD normal frame is not reliable enough to certify face orientation.
    area = ((sx[:, 1] - sx[:, 0]) * (sy[:, 2] - sy[:, 0])
            - (sx[:, 2] - sx[:, 0]) * (sy[:, 1] - sy[:, 0]))
    facing = -area

    light = direction * 0.55 + up * 0.35 + right * 0.25
    light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.maximum(np.einsum("ti,i->t", face_n, light), 0.0)

    order = np.argsort(-z.mean(axis=1))
    img = Image.new("RGB", (VIEW_W * SS, VIEW_H * SS), (24, 27, 32))
    draw = ImageDraw.Draw(img)
    for ti in order:
        pts = [(float(sx[ti, k]), float(sy[ti, k])) for k in range(3)]
        if max(p[0] for p in pts) < 0 or min(p[0] for p in pts) > VIEW_W * SS:
            continue
        if max(p[1] for p in pts) < 0 or min(p[1] for p in pts) > VIEW_H * SS:
            continue
        if facing[ti] >= 0:
            base = colors[mats[ti]]
            color = tuple(int(max(0, min(255, c * shade[ti] * 255))) for c in base)
        else:
            # Backfaces are darker, not magenta: many GoldSrc parts are
            # intentionally one-sided, and a loud color hides the silhouette.
            base = colors[mats[ti]]
            color = tuple(int(max(0, min(255, c * shade[ti] * 0.45 * 255))) for c in base)
        draw.polygon(pts, fill=color)
    img = img.resize((VIEW_W, VIEW_H), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, VIEW_W - 1, VIEW_H - 1), outline=(70, 76, 86))
    draw.text((10, 8), label, fill=(235, 238, 245))
    return img


def make_sheet(images, title, subtitle, out_png: Path):
    cols = 4
    rows = math.ceil(len(images) / cols)
    pad = 8
    sheet = Image.new("RGB", (cols * VIEW_W + (cols + 1) * pad,
                              rows * VIEW_H + (rows + 1) * pad + 48), (16, 18, 22))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, pad), title, fill=(245, 247, 250))
    draw.text((pad, pad + 20), subtitle, fill=(170, 180, 195))
    for i, img in enumerate(images):
        x = pad + (i % cols) * (VIEW_W + pad)
        y = pad + 48 + (i // cols) * (VIEW_H + pad)
        sheet.paste(img, (x, y))
    sheet.save(out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qc", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    qc = args.qc.resolve()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    name = args.name or qc.stem
    verts, norms, mats, used = load_bodies(qc)
    if len(verts) == 0:
        raise SystemExit("no triangles")

    lo = verts.reshape(-1, 3).min(axis=0)
    hi = verts.reshape(-1, 3).max(axis=0)
    center = (lo + hi) * 0.5
    extent = hi - lo
    radius = max(float(np.linalg.norm(extent)) * 1.65, 1.0)
    boundary, nonmanifold = edge_report(verts)

    material_names = sorted(set(mats))
    colors = {m: material_color(m) for m in material_names}

    views = []
    for el in ELEVATIONS:
        for az in AZIMUTHS:
            label = f"az={az:03d}  el={el:+03d}"
            views.append(render_view(verts, norms, mats, colors, center, radius, az, el, label))

    subtitle = (f"{len(verts)} tris | {len(used)} bodies | "
                f"welded boundary={boundary} nonmanifold={nonmanifold} | darker=backface")
    montage = out_dir / f"{name}_360.png"
    make_sheet(views, f"{name} - 360 geometry audit", subtitle, montage)

    report = {
        "name": name,
        "qc": str(qc),
        "triangles": int(len(verts)),
        "bodies": used,
        "boundary_edges": int(boundary),
        "nonmanifold_edges": int(nonmanifold),
        "montage": str(montage),
        "materials": material_names,
    }
    (out_dir / f"{name}_360.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{name}: tris={len(verts)} boundary={boundary} nonmanifold={nonmanifold} -> {montage}")

    index = out_dir / "index.html"
    rows = []
    for json_path in sorted(out_dir.glob("*_360.json")):
        r = json.loads(json_path.read_text(encoding="utf-8"))
        rel = Path(r["montage"]).name
        rows.append(
            f"<tr><td>{html.escape(r['name'])}</td><td>{r['triangles']}</td>"
            f"<td>{r['boundary_edges']}</td><td>{r['nonmanifold_edges']}</td>"
            f"<td><a href='{html.escape(rel)}'>{html.escape(rel)}</a></td></tr>"
        )
    index.write_text(
        "<!doctype html><meta charset='utf-8'><title>MMOD 360 audit</title>"
        "<style>body{font:14px sans-serif;background:#16181c;color:#e8eaf0}"
        "table{border-collapse:collapse}td,th{padding:6px 10px;border-bottom:1px solid #333}"
        "a{color:#8cc8ff}</style><h1>MMOD 360 geometry audit</h1>"
        "<p>Darker faces are backfaces. Open barrel/magwell surfaces are expected; "
        "large see-through gaps or absent receiver/stock faces are not.</p>"
        "<table><tr><th>Model</th><th>Tris</th><th>Boundary</th><th>Non-manifold</th><th>Sheet</th></tr>"
        + "".join(rows) + "</table>",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
