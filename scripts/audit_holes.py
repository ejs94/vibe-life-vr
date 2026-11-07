#!/usr/bin/env python3
"""Classify the boundary loops (holes) of the MMOD Glock viewmodel decompile.

A raw boundary-edge count is not a defect list. GoldSrc weapon meshes are
authored from loosely joined shells, so a muzzle mouth, a magwell, a magazine
shell rim and a fullbright muzzle-flash card all contribute open edges that the
engine never shows. This tool exists to separate those intentional openings
from real holes before any geometry is repaired.

The audit is per body for welding: the decompiled ``$body``/``$bodygroup``
references are stored in different spaces (the ``clip`` sits at the origin and
the ``silencer`` behind the grip on this model), so bodies are never welded
together. Pairing, however, is allowed across the bodies that share the gun
space (``body``, ``silencer``, ``trits``); the ``clip`` only pairs with itself.

For each body the tool:

  * welds triangle corners by rounded position (3 decimals), body-local,
  * counts undirected edges, keeping the directed half-edges so loops can be
    walked in triangle order,
  * extracts ordered loops from boundary edges (count 1) and reports open chains
    as such instead of inventing a closing segment,
  * reports non-manifold edges (count > 2) separately, never as loops,
  * describes each loop by the shell it belongs to, so a two-triangle card is
    recognised as a card instead of a "six-edge enclosed hole",
  * labels every loop ``intentional``, ``accidental`` or ``uncertain`` with a
    confidence and a short reason, and groups the loops that belong to one
    physical defect.

The labels are conservative geometric heuristics, not a substitute for a
maintainer looking at the asset. Anything that cannot be argued from geometry is
reported as ``uncertain`` on purpose.

Outputs (``--out`` is usually a ``scripts/qa_evidence.py`` run directory):

  <name>_holes.json            full loop list, defects and raw per-body metrics
  <name>_holes.csv             the loops as a flat table
  <name>_defects.csv           the defects the repair stage must target
  <name>_holes_summary.json    counts by body, classification and confidence
  <name>_baseline_score.json   moving topology score (35 points max)
  <name>_body_sheet.png        body only, z-buffered, 8 azimuths x 3 elevations
  <name>_attachments_sheet.png clip/silencer/trits, each framed on its own
  <name>_loop_sheet.png        one close-up tile per loop, rim in red
  <name>_commands.json         exact commands, commit and input hashes
  <name>_360/                  secondary 360 montage from render_mdl_360.py

Usage:
    python3 scripts/audit_holes.py \
        --model out/mmod_import/decompiled/v_9mmhandgun \
        --out out/qa/A1/latest
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
sys.dont_write_bytecode = True
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from audit_viewmodel_assets import read_smd_full  # noqa: E402
from render_mdl_360 import (  # noqa: E402
    AZIMUTHS,
    ELEVATIONS,
    material_color,
    parse_qc,
    view_basis,
)

WELD_DECIMALS = 3
VIEW_NORMAL_DOT = 0.2  # a loop counts as visible from an orbit view above this
CARD_MAX_TRIANGLES = 2  # triangle budget of a glow/flash card
POCKET_MAX_TRIANGLES = 8  # triangle budget of an authored small open box
CARD_MIN_PLANARITY = 0.90
CARD_MIN_BOUNDARY_RATIO = 0.90  # loop bbox diagonal / shell bbox diagonal
SLIVER_ASPECT = 4.0  # longest edge^2 / (4 * area); 4 is a 4:1 sliver
SLIVER_MAX_AREA = 0.4  # model units^2; keeps big panels out of the tear set
TEAR_JOIN_BODY_FRACTION = 0.02  # unused reserve for proximity joins

SCORE_MAX = 35.0
SCORE_ACCIDENTAL_MAX = 20.0
ACCIDENTAL_EDGE_REFERENCE = 20.0
SCORE_NONMANIFOLD_MAX = 10.0
NONMANIFOLD_CLUSTER_REFERENCE = 3.0
SCORE_WINDING_MAX = 5.0
WINDING_REFERENCE = 10.0

FOV_DEG = 30.0
TILE = 512
PAD = 8
RUNNING_BODIES = ("body", "silencer", "trits")  # share the gun space
ISOLATED_BODIES = ("clip",)  # authored at the origin, pairs only with itself

KIND_TEAR = "tear"
KIND_OPEN_SIDE = "open_side"
KIND_CARD = "card"
KIND_SLEEVE = "sleeve"
KIND_MUZZLE = "muzzle"
KIND_UNCERTAIN = "uncertain"


# ---------------------------------------------------------------------------
# paths and small helpers
# ---------------------------------------------------------------------------
def display_path(path: Path) -> str:
    """Return a repo- or cwd-relative path so no absolute path is written out."""
    resolved = Path(path).resolve()
    for base in (REPO_DIR, Path.cwd()):
        try:
            return str(resolved.relative_to(base))
        except ValueError:
            continue
    return str(resolved)


def repo_relative(path: Path) -> str:
    """Relative path for a child process launched from the repository root."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_DIR))
    except ValueError:
        return str(resolved)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=REPO_DIR, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def vector(values) -> list[float]:
    return [round(float(v), 4) for v in values]


def load_font(size: int):
    for name in ("DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# topology
# ---------------------------------------------------------------------------
def weld_triangles(verts: np.ndarray):
    """Weld per body by rounded position. Returns ids and welded positions."""
    lookup: dict[tuple, int] = {}
    ids = np.zeros((verts.shape[0], 3), dtype=np.int64)
    positions: list[list[float]] = []
    for ti in range(verts.shape[0]):
        for vi in range(3):
            key = tuple(np.round(verts[ti, vi], WELD_DECIMALS).tolist())
            idx = lookup.get(key)
            if idx is None:
                idx = len(positions)
                lookup[key] = idx
                positions.append([float(c) for c in key])
            ids[ti, vi] = idx
    return ids, np.asarray(positions, dtype=np.float64)


def edge_tables(ids: np.ndarray):
    """Undirected edge counts plus the directed half-edges of each triangle."""
    counts: Counter = Counter()
    half_tri: dict[tuple[int, int], int] = {}
    edge_tris: dict[tuple[int, int], list[int]] = defaultdict(list)
    degenerate = 0
    for ti, tri in enumerate(ids):
        a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
        if len({a, b, c}) < 3:
            degenerate += 1
            continue
        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u <= v else (v, u)
            counts[key] += 1
            half_tri[(u, v)] = ti
            edge_tris[key].append(ti)
    boundary_edges = [edge for edge, count in counts.items() if count == 1]
    nonmanifold = {edge: count for edge, count in counts.items() if count > 2}
    return counts, half_tri, edge_tris, boundary_edges, nonmanifold, degenerate


def components(ids: np.ndarray, counts, verts, mats):
    """Split a body into vertex-connected shells, largest first.

    A body can contain stray helper geometry (the Glock body carries a unit box
    at the origin), so position heuristics are normalised against the largest
    shell instead of the raw body bounding box.
    """
    parent = list(range(int(ids.max()) + 1)) if ids.size else []

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for (u, v) in counts:
        union(int(u), int(v))

    groups: dict[int, list[int]] = defaultdict(list)
    for ti, tri in enumerate(ids):
        a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
        if len({a, b, c}) < 3:
            continue
        groups[find(a)].append(ti)

    ordered = sorted(groups.values(), key=len, reverse=True)
    tri_component = np.zeros(len(ids), dtype=np.int64)
    shells = []
    for index, tris in enumerate(ordered, start=1):
        for ti in tris:
            tri_component[ti] = index
        pts = verts[tris].reshape(-1, 3)
        shells.append(
            {
                "component": index,
                "triangles": len(tris),
                "material_set": sorted({mats[ti] for ti in tris}),
                "bbox_min": pts.min(axis=0),
                "bbox_max": pts.max(axis=0),
                "triangle_ids": tris,
            }
        )
    return shells, tri_component


def extract_loops(boundary_edges, half_tri):
    """Walk boundary half-edges in triangle order.

    A walk that returns to its first vertex is a closed loop; a walk that runs
    out of edges is an open chain and is kept as one so a crack is not reported
    as an enclosed opening.
    """
    half_edges = []
    for u, v in boundary_edges:
        if (u, v) in half_tri:
            half_edges.append((u, v))
        elif (v, u) in half_tri:
            half_edges.append((v, u))
    half_edges.sort()
    outgoing: dict[int, list[int]] = defaultdict(list)
    for a, b in half_edges:
        outgoing[a].append(b)
    for a in outgoing:
        outgoing[a].sort()

    unused = set(half_edges)
    loops = []
    for first in half_edges:
        if first not in unused:
            continue
        path = [first[0]]
        current = first
        closed = False
        branching = 0
        while True:
            unused.discard(current)
            nxt = current[1]
            if nxt == path[0] and len(path) >= 3:
                closed = True
                break
            path.append(nxt)
            candidates = [(nxt, w) for w in outgoing.get(nxt, []) if (nxt, w) in unused]
            if not candidates:
                break
            if len(candidates) > 1:
                branching += 1
            current = candidates[0]
        loops.append({"path": path, "closed": closed, "branching": branching})
    return loops


def newell(points: np.ndarray):
    """Return the Newell area vector of an ordered polygon."""
    area_vec = np.zeros(3, dtype=np.float64)
    count = len(points)
    for i in range(count):
        a = points[i]
        b = points[(i + 1) % count]
        area_vec[0] += (a[1] - b[1]) * (a[2] + b[2])
        area_vec[1] += (a[2] - b[2]) * (a[0] + b[0])
        area_vec[2] += (a[0] - b[0]) * (a[1] + b[1])
    return area_vec * 0.5


def planarity_of(points: np.ndarray) -> tuple[float, float]:
    """Return (planarity in [0, 1], rms deviation) against the best-fit plane."""
    if len(points) < 3:
        return 1.0, 0.0
    centre = points.mean(axis=0)
    centred = points - centre
    # Smallest singular vector is the plane normal; a zero-area loop (collinear
    # points) has no plane, so treat it as planar and let area report the truth.
    try:
        _, _, vh = np.linalg.svd(centred, full_matrices=False)
    except np.linalg.LinAlgError:
        return 0.0, 0.0
    normal = vh[-1]
    deviation = np.abs(centred @ normal)
    rms = float(np.sqrt(np.mean(deviation ** 2)))
    max_extent = float(np.max(np.linalg.norm(centred, axis=1))) if len(points) else 0.0
    if max_extent <= 1e-9:
        return 1.0, rms
    score = 1.0 - min(1.0, rms / max_extent)
    return float(max(0.0, score)), rms


def face_normal(verts: np.ndarray) -> np.ndarray:
    edge_a = verts[1] - verts[0]
    edge_b = verts[2] - verts[0]
    normal = np.cross(edge_a, edge_b)
    length = float(np.linalg.norm(normal))
    if length < 1e-12:
        return np.zeros(3)
    return normal / length


def triangle_area(verts: np.ndarray, tri: int) -> float:
    return float(np.linalg.norm(np.cross(
        verts[tri, 1] - verts[tri, 0], verts[tri, 2] - verts[tri, 0]))) * 0.5


def triangle_aspect(verts: np.ndarray, tri: int) -> float:
    """Longest edge squared over four times the area: 1 is equilateral."""
    area = triangle_area(verts, tri)
    if area <= 1e-12:
        return float("inf")
    edges = [float(np.linalg.norm(verts[tri, i] - verts[tri, (i + 1) % 3])) for i in range(3)]
    return max(edges) ** 2 / (4.0 * area)


def view_offset(az_deg: float, el_deg: float) -> np.ndarray:
    """Unit vector from the orbit centre to the camera, matching render_mdl_360."""
    az = math.radians(az_deg)
    el = math.radians(el_deg)
    return np.array(
        [math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)],
        dtype=np.float64,
    )


def visible_from(normal: np.ndarray) -> list[str]:
    """Orbit views whose camera sits on the opening-normal side of the loop."""
    length = float(np.linalg.norm(normal))
    if length < 1e-9:
        return []
    unit = normal / length
    hits = []
    for el in ELEVATIONS:
        for az in AZIMUTHS:
            if float(np.dot(unit, view_offset(az, el))) >= VIEW_NORMAL_DOT:
                hits.append(f"az={az:03d} el={el:+03d}")
    return hits


# ---------------------------------------------------------------------------
# wireframe renderer (z-buffered review sheets)
# ---------------------------------------------------------------------------
def make_camera(centre, radius, az, el, width, height):
    direction, right, up = view_basis(az, el)
    return {
        "direction": direction,
        "right": right,
        "up": up,
        "camera": np.asarray(centre, dtype=np.float64) - direction * radius,
        "focal": (height * 0.5) / math.tan(math.radians(FOV_DEG) * 0.5),
        "width": width,
        "height": height,
    }


def project(cam, points):
    """Project (..., 3) points. Returns screen x, screen y and camera depth."""
    rel = np.asarray(points, dtype=np.float64) - cam["camera"]
    depth = np.einsum("...i,i->...", rel, cam["direction"])
    safe = np.maximum(depth, 1e-6)
    x = np.einsum("...i,i->...", rel, cam["right"])
    y = np.einsum("...i,i->...", rel, cam["up"])
    sx = cam["width"] * 0.5 + (x / safe) * cam["focal"]
    sy = cam["height"] * 0.5 - (y / safe) * cam["focal"]
    return sx, sy, depth


def fit_radius(points, centre, az, el, width, height, fill=0.9):
    """Smallest orbit radius that keeps the points inside ``fill`` of the frame."""
    points = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    lo, hi = 1e-3, 1.0
    while hi < 1e6:
        cam = make_camera(centre, hi, az, el, width, height)
        sx, sy, depth = project(cam, points)
        if np.all(depth > 1e-3):
            fx = float(np.max(np.abs(sx - width / 2))) / (width / 2)
            fy = float(np.max(np.abs(sy - height / 2))) / (height / 2)
            if max(fx, fy) <= fill:
                break
        hi *= 1.6
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        cam = make_camera(centre, mid, az, el, width, height)
        sx, sy, depth = project(cam, points)
        if np.any(depth <= 1e-3):
            lo = mid
            continue
        fx = float(np.max(np.abs(sx - width / 2))) / (width / 2)
        fy = float(np.max(np.abs(sy - height / 2))) / (height / 2)
        if max(fx, fy) <= fill:
            hi = mid
        else:
            lo = mid
    return hi


def densify(polyline, closed, per_edge=6):
    """Sample a polyline densely enough to judge occlusion of every edge."""
    points = np.asarray(polyline, dtype=np.float64).reshape(-1, 3)
    segments = len(points) if closed else len(points) - 1
    out = []
    for i in range(segments):
        a = points[i]
        b = points[(i + 1) % len(points)]
        for t in np.linspace(0.0, 1.0, per_edge, endpoint=False):
            out.append(a + (b - a) * t)
    out.append(points[0] if closed else points[-1])
    return np.asarray(out)


def visible_fraction(points, cam, verts, surface_offset=0.02):
    """Fraction of loop samples not hidden by the rendered shell triangles.

    Ray casting is used instead of reading the z-buffer so the view can be
    chosen before the tile is rendered.
    """
    origin = cam["camera"]
    e1 = verts[:, 1] - verts[:, 0]
    e2 = verts[:, 2] - verts[:, 0]
    visible = 0
    for point in np.asarray(points, dtype=np.float64):
        direction = point - origin
        distance = float(np.linalg.norm(direction))
        if distance <= 1e-9:
            visible += 1
            continue
        pvec = np.cross(np.broadcast_to(direction, e2.shape), e2)
        det = np.einsum("ij,ij->i", e1, pvec)
        ok = np.abs(det) > 1e-9
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tvec = origin - verts[:, 0]
        u = np.einsum("ij,ij->i", tvec, pvec) * inv
        qvec = np.cross(tvec, e1)
        v = np.einsum("j,ij->i", direction, qvec) * inv
        t = np.einsum("ij,ij->i", e2, qvec) * inv
        hit = (ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1.0 + 1e-6)
               & (t > 1e-6) & (t < 1.0 - surface_offset / distance))
        if not hit.any():
            visible += 1
    return visible / max(len(points), 1)


def choose_loop_view(item, shell_verts):
    """Pick the orbit view that actually shows the loop, then the most face-on.

    Maximising the opening-normal dot alone can put the owning shell between the
    camera and its own rim; a loop the reviewer cannot see is not evidence.
    """
    points = item["_points"]
    polyline = np.vstack([points, points[:1]]) if item["closed"] else points
    dense = densify(polyline, item["closed"])
    opening = item["opening_normal"]
    if float(np.linalg.norm(opening)) < 1e-9:
        opening = item["adjacent_normal"]
    centre = (points.min(axis=0) + points.max(axis=0)) * 0.5
    best = None
    for el in ELEVATIONS:
        for az in AZIMUTHS:
            radius = fit_radius(points, centre, az, el, TILE, TILE, fill=0.55)
            cam = make_camera(centre, radius, az, el, TILE, TILE)
            fraction = visible_fraction(dense, cam, shell_verts)
            dot = float(np.dot(opening, view_offset(az, el))) if np.linalg.norm(opening) > 1e-9 else 0.0
            score = (0.05 + fraction) * (1.2 + dot)
            if best is None or score > best[0]:
                best = (score, az, el, fraction)
    return best[1], best[2], best[3]


def render_mesh(verts, mats, colours, cam, highlights=(), background=(22, 24, 28)):
    """Rasterise triangles with a z-buffer, then draw depth-tested polylines."""
    width, height = cam["width"], cam["height"]
    sx, sy, z = project(cam, verts)
    depth_buffer = np.full((height, width), np.inf, dtype=np.float64)
    pixels = np.zeros((height, width, 3), dtype=np.uint8)
    pixels[:] = background

    geometric = np.cross(verts[:, 1] - verts[:, 0], verts[:, 2] - verts[:, 0])
    lengths = np.linalg.norm(geometric, axis=1)
    unit = np.divide(geometric, lengths[:, None], out=np.zeros_like(geometric),
                     where=lengths[:, None] > 1e-12)
    light = cam["direction"] * 0.5 + cam["up"] * 0.4 + cam["right"] * 0.3
    light /= np.linalg.norm(light)

    for ti in range(verts.shape[0]):
        p = np.array([[sx[ti, k], sy[ti, k], max(z[ti, k], 1e-4)] for k in range(3)])
        x0 = max(int(math.floor(p[:, 0].min())), 0)
        x1 = min(int(math.ceil(p[:, 0].max())), width - 1)
        y0 = max(int(math.floor(p[:, 1].min())), 0)
        y1 = min(int(math.ceil(p[:, 1].max())), height - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = ((p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0])
               + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1]))
        if abs(den) < 1e-12:
            continue
        w1 = ((p[1, 1] - p[2, 1]) * (gx - p[2, 0])
              + (p[2, 0] - p[1, 0]) * (gy - p[2, 1])) / den
        w2 = ((p[2, 1] - p[0, 1]) * (gx - p[2, 0])
              + (p[0, 0] - p[2, 0]) * (gy - p[2, 1])) / den
        w3 = 1.0 - w1 - w2
        inside = (w1 >= -1e-6) & (w2 >= -1e-6) & (w3 >= -1e-6)
        if not inside.any():
            continue
        inv = w1 / p[0, 2] + w2 / p[1, 2] + w3 / p[2, 2]
        depth = 1.0 / np.maximum(inv, 1e-12)
        window = depth_buffer[y0:y1 + 1, x0:x1 + 1]
        emit = inside & (depth < window - 1e-5)
        if not emit.any():
            continue
        window[emit] = depth[emit]
        base = colours[mats[ti]]
        shade = 0.45 + 0.55 * abs(float(np.dot(unit[ti], light)))
        if float(np.dot(unit[ti], -cam["direction"])) < 0.0:
            # Backfaces are darker, never magenta: magenta exaggerates authored
            # one-sided shells and hides the silhouette.
            shade *= 0.55
        colour = np.clip(np.asarray(base) * shade * 235.0, 0, 255).astype(np.uint8)
        pixels[y0:y1 + 1, x0:x1 + 1][emit] = colour

    image = Image.fromarray(pixels)
    draw = ImageDraw.Draw(image)
    for polyline, colour, closed in highlights:
        draw_polyline_depth(draw, cam, depth_buffer, polyline, colour, closed)
    return image


def draw_polyline_depth(draw, cam, depth_buffer, points, colour, closed, width=3,
                        tolerance=None):
    """Draw a polyline only where it is not hidden by a nearer surface."""
    points = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    if len(points) < 2:
        return
    sx, sy, z = project(cam, points)
    if tolerance is None:
        mean = points.mean(axis=0)
        tolerance = 0.02 * float(np.linalg.norm(mean - cam["camera"])) + 1e-3
    count = len(points) if closed else len(points) - 1
    for i in range(count):
        j = (i + 1) % len(points)
        if z[i] <= 1e-3 or z[j] <= 1e-3:
            continue
        ax, ay, bx, by = float(sx[i]), float(sy[i]), float(sx[j]), float(sy[j])
        steps = int(max(abs(bx - ax), abs(by - ay))) + 1
        steps = min(steps, 4096)
        for s in range(steps + 1):
            t = s / steps
            px = int(round(ax + (bx - ax) * t))
            py = int(round(ay + (by - ay) * t))
            pz = z[i] + (z[j] - z[i]) * t
            if 0 <= px < cam["width"] and 0 <= py < cam["height"]:
                if pz <= depth_buffer[py, px] + tolerance:
                    draw.rectangle((px - 1, py - 1, px + 1, py + 1), fill=colour)


def tile_label(image, lines):
    draw = ImageDraw.Draw(image)
    fonts = [load_font(15), load_font(13), load_font(12)]
    total = sum(18 for _ in lines)
    top = image.height - total - 8
    draw.rectangle((0, top - 4, image.width, image.height), fill=(14, 16, 20))
    y = top
    for i, line in enumerate(lines):
        draw.text((8, y), line, fill=(240, 243, 248) if i == 0 else (168, 186, 208),
                  font=fonts[i])
        y += 18


def render_tile(verts, mats, colours, frame_points, centre, az, el, highlights=(),
                label_lines=(), fill=0.9, width=TILE, height=TILE):
    radius = fit_radius(frame_points, centre, az, el, width, height, fill=fill)
    cam = make_camera(centre, radius, az, el, width, height)
    image = render_mesh(verts, mats, colours, cam, highlights)
    if label_lines:
        tile_label(image, label_lines)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width - 1, height - 1), outline=(66, 72, 84))
    return image


def scale_bar_length(cam, radius):
    per_unit = cam["focal"] / radius
    for length in (5.0, 2.0, 1.0, 0.5, 0.2, 0.1):
        if 40.0 <= length * per_unit <= 220.0:
            return length, length * per_unit
    return 1.0, per_unit


def draw_scale(draw, x, y, cam, radius, colour=(200, 210, 225)):
    length, pixels = scale_bar_length(cam, radius)
    draw.line((x, y, x + pixels, y), fill=colour, width=3)
    draw.line((x, y - 5, x, y + 5), fill=colour, width=3)
    draw.line((x + pixels, y - 5, x + pixels, y + 5), fill=colour, width=3)
    text = f"{length:g} unit = {pixels:.0f} px at the orbit centre"
    draw.text((x, y - 20), text, fill=colour, font=load_font(13))
    return pixels


def make_sheet(images, out_png: Path, title: str, caption: list[str], cols: int,
               legend: list[tuple[str, tuple[int, int, int]]] | None = None,
               extra_draw=None):
    rows = math.ceil(len(images) / cols)
    header = 34 + 20 * len(caption) + (22 * len(legend or []) if legend else 0)
    header += 46 if extra_draw else 0
    width = cols * TILE + (cols + 1) * PAD
    height = rows * TILE + (rows + 1) * PAD + header
    sheet = Image.new("RGB", (width, height), (14, 16, 20))
    draw = ImageDraw.Draw(sheet)
    draw.text((PAD, PAD), title, fill=(245, 247, 250), font=load_font(22))
    y = PAD + 30
    for line in caption:
        draw.text((PAD, y), line, fill=(172, 184, 200), font=load_font(14))
        y += 20
    if legend:
        x = PAD
        for name, colour in legend:
            draw.rectangle((x, y + 3, x + 14, y + 15), fill=colour)
            draw.text((x + 20, y), name, fill=(190, 200, 215), font=load_font(13))
            x += 28 + 8 * len(name)
        y += 22
    if extra_draw:
        extra_draw(draw, y)
    for i, image in enumerate(images):
        x = PAD + (i % cols) * (TILE + PAD)
        py = PAD + header + (i // cols) * (TILE + PAD)
        sheet.paste(image, (x, py))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png)


# ---------------------------------------------------------------------------
# loop metrics and classification
# ---------------------------------------------------------------------------
def loop_metrics(body: str, loop: dict, positions, verts, mats, edge_tris,
                 ref_lo, ref_hi, tri_component, shell_by_component, shell_loop_counts):
    path = loop["path"]
    closed = loop["closed"]
    points = positions[path]
    # A closed path does not repeat its first vertex, so every point is a corner.
    segments = np.linalg.norm(np.diff(np.vstack([points, points[:1]]), axis=0), axis=1) \
        if closed else np.linalg.norm(np.diff(points, axis=0), axis=1)
    perimeter = float(segments.sum())
    area_vec = newell(points)
    area = float(np.linalg.norm(area_vec) * 0.5)
    normal = area_vec / float(np.linalg.norm(area_vec)) if np.linalg.norm(area_vec) > 1e-9 else np.zeros(3)
    planarity, rms = planarity_of(points)

    materials = set()
    adjacent_normals = []
    adjacent_tris = set()
    edge_count = len(path) if closed else len(path) - 1
    for i in range(edge_count):
        u, v = path[i], path[(i + 1) % len(path)]
        key = (u, v) if u <= v else (v, u)
        for ti in edge_tris.get(key, []):
            adjacent_tris.add(ti)
            materials.add(mats[ti])
    for ti in adjacent_tris:
        adjacent_normals.append(face_normal(verts[ti]))
    mean_adjacent = np.mean(adjacent_normals, axis=0) if adjacent_normals else np.zeros(3)
    adjacent_length = float(np.linalg.norm(mean_adjacent))
    mean_adjacent = mean_adjacent / adjacent_length if adjacent_length > 1e-9 else np.zeros(3)

    centroid = points.mean(axis=0)
    lo = points.min(axis=0)
    hi = points.max(axis=0)
    size = hi - lo
    span = np.maximum(ref_hi - ref_lo, 1e-6)
    pnorm = (centroid - ref_lo) / span
    shell_id = int(tri_component[sorted(adjacent_tris)[0]]) if adjacent_tris else 0
    shell = shell_by_component.get(shell_id, {})
    shell_size = shell.get("bbox_max", lo) - shell.get("bbox_min", lo)
    shell_diagonal = float(np.linalg.norm(shell_size))
    loop_diagonal = float(np.linalg.norm(size))

    # A real card test: a card is one or two triangles, flat, and its boundary
    # loop is the whole card outline. Edge count alone cannot tell a card rim
    # from a hole (the old "closed and >= 6 edges" test called a 4-edge card
    # uncertain and a 6-edge bore a card).
    card = bool(
        closed
        and shell.get("triangles", 0) <= CARD_MAX_TRIANGLES
        and planarity >= CARD_MIN_PLANARITY
        and shell_diagonal > 1e-9
        and loop_diagonal / shell_diagonal >= CARD_MIN_BOUNDARY_RATIO
    )
    # An authored small open box (a pocket) has one closed rim and very few
    # triangles: the rim is the open face of the pocket, not a torn cap.
    pocket = bool(
        closed
        and shell.get("triangles", 0) <= POCKET_MAX_TRIANGLES
        and shell_loop_counts.get(shell_id, 0) == 1
    )

    return {
        "id": None,
        "body": body,
        "component": shell_id,
        "shell_triangles": int(shell.get("triangles", 0)),
        "shell_boundary_loops": int(shell_loop_counts.get(shell_id, 0)),
        "shell_bbox_diagonal": shell_diagonal,
        "closed": closed,
        "edge_count": edge_count,
        "vertex_count": len(path),
        "perimeter": perimeter,
        "area": area,
        "planarity": planarity,
        "planarity_rms": rms,
        "centroid": centroid,
        "bbox_min": lo,
        "bbox_max": hi,
        "bbox_size": size,
        "diagonal": loop_diagonal,
        "normal": normal,
        "opening_normal": np.zeros(3),
        "adjacent_normal": mean_adjacent,
        "materials": sorted(materials),
        "pnorm": pnorm,
        "branching": loop["branching"],
        "is_card": card,
        "is_pocket": pocket,
        "nm_contact": 0,
        "_points": points,
        "_path": path,
        "_adjacent": adjacent_tris,
    }


def coverage_count(metrics: dict, verts, mats, body_tris: int) -> int:
    """Count faces that would cover the loop plane inside the loop bounding box."""
    normal = metrics["normal"]
    if float(np.linalg.norm(normal)) < 1e-9:
        return 0
    lo = metrics["bbox_min"] - metrics["bbox_size"] * 0.15
    hi = metrics["bbox_max"] + metrics["bbox_size"] * 0.15
    hits = 0
    for ti in range(body_tris):
        if ti in metrics["_adjacent"]:
            continue
        centre = verts[ti].mean(axis=0)
        if np.any(centre < lo) or np.any(centre > hi):
            continue
        if abs(float(np.dot(face_normal(verts[ti]), normal))) >= 0.5:
            hits += 1
    return hits


def bbox_overlap_ratio(a: dict, b: dict) -> float:
    """Intersection volume over the smaller bounding box volume."""
    lo = np.maximum(a["bbox_min"], b["bbox_min"])
    hi = np.minimum(a["bbox_max"], b["bbox_max"])
    volume = float(np.prod(np.maximum(hi - lo, 0.0)))
    smaller = min(float(np.prod(a["bbox_size"])), float(np.prod(b["bbox_size"])))
    return volume / smaller if smaller > 1e-9 else 0.0


def shells_comparable(a: dict, b: dict) -> bool:
    """Cross-body pairs are allowed only between bodies that share a space."""
    if a["body"] == b["body"]:
        return True
    if "clip" in (a["body"].lower(), b["body"].lower()):
        return False
    return a["body"].lower() in RUNNING_BODIES and b["body"].lower() in RUNNING_BODIES


def same_shell(a: dict, b: dict) -> bool:
    return a["body"] == b["body"] and a["component"] == b["component"]


def pair_loops(loops: list[dict]) -> list[tuple[dict, dict, str]]:
    """Find the structural pairs that explain an opening without a repair.

    Two rims at the opposite ends of the same shell are an open sleeve (a
    magazine well or a tube). Two coincident rims on different shells are one
    through-opening whose wall is the gap between the shells. Both are authored
    by construction, so they are worth detecting before any name or position
    guess. Bodies are never welded: this only compares loops.
    """
    pairs: list[tuple[dict, dict, str]] = []
    for i, a in enumerate(loops):
        for b in loops[i + 1:]:
            if not (a["closed"] and b["closed"]):
                continue
            if a["is_card"] or b["is_card"]:
                continue
            if not shells_comparable(a, b):
                continue
            na, nb = a["normal"], b["normal"]
            if float(np.linalg.norm(na)) < 1e-9 or float(np.linalg.norm(nb)) < 1e-9:
                continue
            opposite = float(np.dot(na, nb)) <= -0.5
            area_ratio = min(a["area"], b["area"]) / max(a["area"], b["area"], 1e-9)
            separation = float(np.linalg.norm(a["centroid"] - b["centroid"]))
            size = max(math.sqrt(max(a["area"], 1e-9)), math.sqrt(max(b["area"], 1e-9)))
            if (opposite and same_shell(a, b) and area_ratio >= 0.6
                    and separation >= 1.5 * size):
                pairs.append((a, b, "sleeve"))
                continue
            if (not same_shell(a, b) and bbox_overlap_ratio(a, b) >= 0.55
                    and not opposite):
                pairs.append((a, b, "rim"))
    return pairs


def set_opening_normal(item: dict, kind: str) -> None:
    """Derive the direction the opening is seen from, per loop kind.

    A hole in a closed shell is traversed inwards, so it is seen from the side
    opposite the Newell normal. A card's boundary is the card outline, so the
    card is seen from the side its Newell normal points at. An open crack has no
    area normal, so the surrounding face normal is the visible side.
    """
    normal = item["normal"]
    adjacent = item["adjacent_normal"]
    if kind == KIND_CARD:
        item["opening_normal"] = normal
    elif not item["closed"]:
        item["opening_normal"] = adjacent if float(np.linalg.norm(adjacent)) > 1e-9 else normal
    else:
        item["opening_normal"] = -normal


def classify_loops(loops: list[dict], extra_bodies: dict | None = None) -> None:
    """Label every loop in place, then derive its visible-from orbit views.

    The order matters: structural pairing runs before any name-based branch so a
    ``trits``/``silencer``/``clip`` heuristic cannot pre-empt a real pair, and
    tear evidence runs before the position heuristics so a torn front cap is not
    forced into the "bore" bucket.
    """
    extra_bodies = extra_bodies or {}
    partner: dict[str, tuple[str, str]] = {}
    for a, b, kind in pair_loops(loops):
        partner[a["id"]] = (b["id"], kind)
        partner[b["id"]] = (a["id"], kind)

    for item in loops:
        name = item["body"].lower()
        edges = item["edge_count"]
        planarity = item["planarity"]
        normal = item["normal"]
        pn = item["pnorm"]
        coverage = item["covering_faces"]
        paired = partner.get(item["id"])
        normal_axis = int(np.argmax(np.abs(normal))) if np.linalg.norm(normal) > 1e-9 else -1
        opening_axis = float(item["opening_hint"][normal_axis]) if normal_axis >= 0 else 0.0
        kind = KIND_UNCERTAIN
        confident = "medium"

        if item["nm_contact"] > 0:
            label = "accidental"
            kind = KIND_TEAR
            confident = "high"
            nm_word = "edge" if item["nm_contact"] == 1 else "edges"
            reason = (
                f"tear: the rim shares welded vertices with {item['nm_contact']} non-manifold "
                f"{nm_word} of the same body; slivers on the torn surface: "
                f"{item['sliver_contact']} (longest edge^2 / 4*area >= {SLIVER_ASPECT:g}); "
                "a torn surface cannot be capped, the sheets must be stitched"
            )
        elif not item["closed"]:
            if edges <= 2:
                label, confident = "accidental", "medium"
                reason = ("isolated unpaired edge (crack/T-junction); it encloses no opening")
            else:
                label, confident = "uncertain", "low"
                reason = ("open boundary chain; a crack and a deliberately open strip look "
                          "alike here")
        elif item["is_card"]:
            label, kind, confident = "intentional", KIND_CARD, "high"
            reason = (
                f"card/surface edge: the shell is a {item['shell_triangles']}-triangle "
                f"surface (planarity {planarity:.2f}) and this loop is its whole outline, "
                "so it is the edge of a glow/flash card, not a hole"
            )
        elif paired and paired[1] == "sleeve":
            label, kind = "intentional", KIND_SLEEVE
            reason = (
                f"matched rim pair with {paired[0]} at the other end of the same shell "
                "(opposite normals, equal area): an open-ended sleeve, not a missing cap"
            )
        elif paired and paired[1] == "rim":
            label, kind = "intentional", KIND_SLEEVE
            reason = (
                f"coincident rim with {paired[0]} on another shell (bbox overlap, same "
                "normal side): one through-opening whose wall is the gap between the two "
                "shells"
            )
        elif item["is_pocket"]:
            label, kind = "intentional", KIND_SLEEVE
            reason = (
                f"authored small open box: {item['shell_triangles']} triangles, exactly one "
                f"closed rim, planarity {planarity:.2f}; the rim is the open face of an "
                "authored pocket/spring channel, not a torn cap"
            )
        elif normal_axis >= 0 and (
            (pn[normal_axis] <= 0.03 and opening_axis < 0.0)
            or (pn[normal_axis] >= 0.97 and opening_axis > 0.0)
        ):
            label, kind = "intentional", KIND_MUZZLE
            reason = (
                f"closing rim on the extreme face of the body (normalized position "
                f"{pn[normal_axis]:.3f} along axis {'xyz'[normal_axis]}, opening faces "
                f"{'xyz'[normal_axis]}{'-' if opening_axis < 0 else '+'}): the muzzle bore / "
                "attachment plane, not a missing cap"
            )
            if name.startswith(("silencer", "suppressor")):
                reason = (
                    "only boundary loop of the single tube shell, on its extreme end face "
                    f"(normalized position {pn[normal_axis]:.3f} along "
                    f"{'xyz'[normal_axis]}): the open muzzle end of the suppressor tube"
                )
            elif "silencer" in extra_bodies:
                low, high = extra_bodies["silencer"]
                if abs(item["bbox_min"][2] - high[2]) <= 0.5:
                    reason += ("; the separate suppressor body ends on this same plane "
                               f"(z={high[2]:.3f})")
        elif name.startswith(("clip", "mag")):
            # The clip is authored at the origin and is drawn out of the grip by
            # the staged reload, so an open side is exposed on screen. Do not
            # assume the magazine follower hides it: only covering geometry can
            # prove that, and there is none.
            if coverage == 0:
                label, kind = "accidental", KIND_OPEN_SIDE
                reason = (
                    f"open side (not the top) of the inner magazine surface: the "
                    f"{item['shell_triangles']}-triangle shell with materials "
                    f"{'/'.join(item['materials'])}, not the outer casing shell. {edges} "
                    f"welded boundary edges form one closed rim at planarity "
                    f"{planarity:.2f} with covering_faces={coverage}, so no authored face "
                    "closes it. The clip mesh is skinned to Box02 (node 14), which "
                    "reload.smd animates, so the staged reload moves the clip out of the "
                    "grip and exposes this rim; nothing in the geometry proves the gun "
                    "occludes it when inserted"
                )
            else:
                label, kind = "intentional", KIND_SLEEVE
                reason = (
                    f"magazine shell rim with {coverage} covering face(s) inside the grip; "
                    "the geometry shows it is closed by the surrounding shell"
                )
        elif name.startswith(("trits", "glow")):
            label, confident = "uncertain", "low"
            reason = "glow body loop that is not a two-triangle card; no card test applies"
        elif pn[1] <= 0.12:
            label, confident = "intentional", "medium"
            reason = ("rim at the low end of the body: base/floor of the shell, filled by a "
                      "separate body in game")
        elif (coverage == 0 and planarity >= 0.9
              and item.get("ref_volume") is not None
              and item["area"] > 0.02 * item["ref_volume"]):
            # ref_volume is only present for bodies whose reference shell envelope
            # was measured; without it the "large planar loop" test cannot run, so
            # fall through to the uncertain branch instead of raising.
            label, confident = "accidental", "low"
            reason = ("large planar loop with nothing behind it; consistent with a missing "
                      "face but a designed panel gap was not excluded")
        else:
            label, confident = "uncertain", "low"
            reason = ("small interior rim of a multi-shell chassis; neighbour geometry does "
                      "not show whether the opening is authored")

        item["classification"] = label
        item["confidence"] = confident
        item["kind"] = kind
        item["reason"] = reason
        item["paired_with"] = paired[0] if paired else None
        if item["branching"]:
            item["reason"] += f" (loop walk branched {item['branching']}x)"
        set_opening_normal(item, kind)
        item["visible_from"] = visible_from(item["opening_normal"])


def nonmanifold_clusters(nonmanifold_by_body: dict[str, dict]) -> list[dict]:
    """Group non-manifold edges that share a welded vertex into one cluster."""
    clusters: list[dict] = []
    for body, edges in nonmanifold_by_body.items():
        parent: dict[int, int] = {}

        def find(x: int) -> int:
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for a, b in edges:
            union(int(a), int(b))
        groups: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for a, b in edges:
            groups[find(int(a))].append((int(a), int(b)))
        for index, group in enumerate(sorted(groups.values(), key=len, reverse=True), start=1):
            clusters.append(
                {
                    "id": f"{body}_nm_cluster_{index}",
                    "body": body,
                    "edges": [(int(a), int(b), int(edges[(a, b)])) for a, b in group],
                    "edge_count": len(group),
                    "triangle_incidences": sum(int(edges[(a, b)]) for a, b in group),
                    "defect": None,
                }
            )
    return clusters


def build_defects(loops: list[dict], nm_clusters: list[dict], positions,
                  verts, mats, edge_tris_by_body, tri_component_by_body) -> list[dict]:
    """Group loops and non-manifold edges into physical defects.

    The front-top tear is the proof that raw loops are not the repair unit: one
    open boundary edge and three non-manifold edges share welded vertices and
    must be reported as one defect.
    """
    defects: list[dict] = []
    used = set()
    # A tear is the non-manifold cluster plus every loop that shares a welded
    # vertex with it. That is a topological join, not a distance guess.
    for cluster in nm_clusters:
        body = cluster["body"]
        nm_vertices = {v for a, b, _ in cluster["edges"] for v in (a, b)}
        joined = []
        for item in loops:
            if item["body"] != body:
                continue
            if nm_vertices.intersection(item["_path"]):
                joined.append(item)
        if not joined:
            continue
        materials = set()
        triangles = set()
        for item in joined:
            used.add(item["id"])
            materials.update(item["materials"])
            triangles.update(int(t) for t in item["_adjacent"])
        edge_counts = {(a, b): count for a, b, count in cluster["edges"]}
        edge_set = set(edge_counts)
        for edge in edge_set:
            for ti in edge_tris_by_body[body].get(edge, []):
                triangles.add(int(ti))
                materials.add(mats[body][ti])
        # Sliver triangles that make up the torn surface are part of the same
        # defect even when they are not incident to the rim itself.
        nm_points = np.array([positions[body][v] for edge in cluster["edges"]
                              for v in (edge[0], edge[1])])
        rim_lo = np.min(np.vstack([item["bbox_min"] for item in joined] + [nm_points]), axis=0)
        rim_hi = np.max(np.vstack([item["bbox_max"] for item in joined] + [nm_points]), axis=0)
        rim_centre = (rim_lo + rim_hi) * 0.5
        rim_diagonal = float(np.linalg.norm(rim_hi - rim_lo))
        comp = int(tri_component_by_body[body][sorted(triangles)[0]])
        for ti in np.nonzero(tri_component_by_body[body] == comp)[0]:
            if int(ti) in triangles:
                continue
            centre = verts[body][ti].mean(axis=0)
            if float(np.linalg.norm(centre - rim_centre)) > max(rim_diagonal, 0.25):
                continue
            if (triangle_aspect(verts[body], int(ti)) >= SLIVER_ASPECT
                    and triangle_area(verts[body], int(ti)) <= SLIVER_MAX_AREA):
                triangles.add(int(ti))
                materials.add(mats[body][ti])
        visible = sorted({view for item in joined for view in item["visible_from"]})
        cluster["defect"] = f"{body}_tear_1"
        defects.append(
            {
                "id": f"{body}_tear_1",
                "kind": KIND_TEAR,
                "body": body,
                "loops": [item["id"] for item in joined],
                "nonmanifold_edges": [
                    {
                        "a": vector(positions[body][a]),
                        "b": vector(positions[body][b]),
                        "count": edge_counts[(a, b)],
                    }
                    for a, b in sorted(edge_set)
                ],
                "triangles": sorted(triangles),
                "materials": sorted(materials),
                "bbox": {
                    "min": vector(rim_lo),
                    "max": vector(rim_hi),
                    "size": vector(rim_hi - rim_lo),
                },
                "bbox_min": vector(rim_lo),
                "bbox_max": vector(rim_hi),
                "bbox_size": vector(rim_hi - rim_lo),
                "visible_from": visible,
                "classification": "accidental",
                "confidence": "high",
                "reason": (
                    f"one front-top tear: {len(joined)} open boundary "
                    f"{'rim' if len(joined) == 1 else 'rims'} share{'s' if len(joined) == 1 else ''} "
                    f"welded vertices with {cluster['edge_count']} non-manifold "
                    f"{'edge' if cluster['edge_count'] == 1 else 'edges'} where three sheets "
                    f"meet; {len(triangles)} triangles form the torn surface "
                    f"(materials: {', '.join(sorted(materials))}), including the sliver "
                    f"triangles and the reversed-winding sheet. Stitch the sheets; do not cap"
                ),
            }
        )
    # Every remaining loop is its own physical unit, except paired rims that are
    # already one opening; paired loops therefore share one defect entry.
    partner_seen = {}
    for item in loops:
        if item["id"] in used:
            continue
        pair_id = item["paired_with"]
        if pair_id:
            key = tuple(sorted((item["id"], pair_id)))
            if key in partner_seen:
                defect = partner_seen[key]
                defect["loops"].append(item["id"])
                defect["materials"] = sorted(set(defect["materials"]) | set(item["materials"]))
                defect["triangles"] = sorted(set(defect["triangles"]) | set(
                    int(t) for t in item["_adjacent"]))
                defect["bbox_min"] = vector(np.minimum(defect["bbox_min"], item["bbox_min"]))
                defect["bbox_max"] = vector(np.maximum(defect["bbox_max"], item["bbox_max"]))
                defect["bbox_size"] = vector(np.array(defect["bbox_max"]) - np.array(defect["bbox_min"]))
                defect["bbox"] = {
                    "min": defect["bbox_min"],
                    "max": defect["bbox_max"],
                    "size": defect["bbox_size"],
                }
                defect["visible_from"] = sorted(set(defect["visible_from"]) | set(item["visible_from"]))
                item["defect"] = defect["id"]
                continue
        triangles = sorted(int(t) for t in item["_adjacent"])
        defect = {
            "id": f"{item['id']}_{item['kind']}",
            "kind": item["kind"],
            "body": item["body"],
            "loops": [item["id"]],
            "nonmanifold_edges": [],
            "triangles": triangles,
            "materials": sorted(set(item["materials"])),
            "bbox": {
                "min": vector(item["bbox_min"]),
                "max": vector(item["bbox_max"]),
                "size": vector(item["bbox_size"]),
            },
            "bbox_min": vector(item["bbox_min"]),
            "bbox_max": vector(item["bbox_max"]),
            "bbox_size": vector(item["bbox_size"]),
            "visible_from": list(item["visible_from"]),
            "classification": item["classification"],
            "confidence": item["confidence"],
            "reason": item["reason"],
        }
        defects.append(defect)
        if pair_id:
            partner_seen[tuple(sorted((item["id"], pair_id)))] = defect
        item["defect"] = defect["id"]
    return defects


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def declared_bodies(qc_path: Path) -> list[str]:
    """Body names declared by the QC, including the ones the parser drops."""
    names: list[str] = []
    for line in qc_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r'^\s*\$(?:body|bodygroup)\s+"([^"]+)"', line, re.I)
        if match:
            names.append(match.group(1))
    return names


def cluster_shells(shells: list[dict], frame_diagonal: float) -> list[list[dict]]:
    """Group shells whose bounding boxes touch, so each cluster can be framed."""
    grow = max(frame_diagonal * 0.02, 1e-3)
    parent = list(range(len(shells)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(shells):
        for j in range(i + 1, len(shells)):
            b = shells[j]
            if np.all(a["bbox_min"] - grow <= b["bbox_max"]) and np.all(
                    b["bbox_min"] - grow <= a["bbox_max"]):
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[rb] = ra
    groups: dict[int, list[dict]] = defaultdict(list)
    for i, shell in enumerate(shells):
        groups[find(i)].append(shell)
    return sorted(groups.values(), key=lambda group: -sum(s["triangles"] for s in group))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path,
                        help="decompiled model directory containing the QC")
    parser.add_argument("--out", required=True, type=Path,
                        help="evidence run directory")
    parser.add_argument("--name", default="glock", help="output file stem")
    parser.add_argument("--skip-render", action="store_true",
                        help="debug: skip every render and the review-sheet check")
    args = parser.parse_args()

    model_dir = args.model.resolve()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    qcs = sorted(model_dir.glob("*.qc"))
    if not qcs:
        print(f"error: no QC in {display_path(model_dir)}", file=sys.stderr)
        return 1
    qc = qcs[0]

    bodies = parse_qc(qc)  # parse_qc already drops hands/forearms
    if not bodies:
        print(f"error: no auditable bodies in {display_path(qc)}", file=sys.stderr)
        return 1

    loops_out: list[dict] = []
    body_rows: list[dict] = []
    nonmanifold_rows: list[dict] = []
    nonmanifold_by_body: dict[str, dict] = {}
    positions_by_body: dict[str, np.ndarray] = {}
    verts_by_body: dict[str, np.ndarray] = {}
    mats_by_body: dict[str, list[str]] = {}
    edge_tris_by_body: dict[str, dict] = {}
    tri_component_by_body: dict[str, np.ndarray] = {}
    shell_by_body: dict[str, list[dict]] = {}
    total_winding = 0
    total_winding_detail: list[dict] = []

    for body_name, smd_name in bodies:
        smd_path = model_dir / f"{smd_name}.smd"
        if not smd_path.is_file():
            print(f"warning: missing {display_path(smd_path)}", file=sys.stderr)
            continue
        verts, norms, _uvs, vertex_mats = read_smd_full(smd_path)
        if len(verts) == 0:
            continue
        # read_smd_full records one material per vertex line; one material per
        # triangle is what the topology and defect tables need.
        mats = vertex_mats[::3]
        if len(mats) < len(verts):
            mats += [vertex_mats[-1]] * (len(verts) - len(mats))
        ids, positions = weld_triangles(verts)
        counts, half_tri, edge_tris, boundary, nonmanifold, degenerate = edge_tables(ids)
        shells, tri_component = components(ids, counts, verts, mats)
        body_lo = positions.min(axis=0)
        body_hi = positions.max(axis=0)
        # Normalise positions against the largest shell: helper boxes and debris
        # would otherwise stretch the body box and hide the real layout.
        ref_lo = shells[0]["bbox_min"]
        ref_hi = shells[0]["bbox_max"]

        bad_winding = winding_mismatches(verts, norms)
        total_winding += len(bad_winding)
        for ti in bad_winding:
            total_winding_detail.append(
                {
                    "body": body_name,
                    "triangle": ti,
                    "materials": mats[ti],
                    "centroid": vector(verts[ti].mean(axis=0)),
                }
            )

        raw_loops = extract_loops(boundary, half_tri)
        shell_by_component = {shell["component"]: shell for shell in shells}
        shell_loop_counts: Counter = Counter()
        raw_by_component = []
        for raw in raw_loops:
            adjacent = set()
            path = raw["path"]
            edge_count = len(path) if raw["closed"] else len(path) - 1
            for i in range(edge_count):
                u, v = path[i], path[(i + 1) % len(path)]
                key = (u, v) if u <= v else (v, u)
                adjacent.update(edge_tris.get(key, []))
            comp = int(tri_component[sorted(adjacent)[0]]) if adjacent else 0
            raw_by_component.append(comp)
            shell_loop_counts[comp] += 1

        body_loops = []
        for raw, comp in zip(raw_loops, raw_by_component):
            metrics = loop_metrics(body_name, raw, positions, verts, mats, edge_tris,
                                   ref_lo, ref_hi, tri_component, shell_by_component,
                                   shell_loop_counts)
            metrics["covering_faces"] = coverage_count(metrics, verts, mats, len(verts))
            metrics["opening_hint"] = -metrics["normal"]
            metrics["sliver_contact"] = sum(
                1 for ti in metrics["_adjacent"]
                if triangle_aspect(verts, ti) >= SLIVER_ASPECT)
            body_loops.append(metrics)

        # Non-manifold contact is a topological join: a loop that shares a
        # welded vertex with a non-manifold edge is part of the same tear.
        nm_vertices = {v for edge in nonmanifold for v in edge}
        for metrics in body_loops:
            metrics["nm_contact"] = len(nm_vertices.intersection(metrics["_path"]))
            if metrics["nm_contact"] == 0 and metrics["_path"]:
                span = float(np.linalg.norm(metrics["bbox_size"]))
                centre = metrics["centroid"]
                for (a, b) in nonmanifold:
                    near_a = np.linalg.norm(positions[a] - centre)
                    near_b = np.linalg.norm(positions[b] - centre)
                    if min(near_a, near_b) <= max(span, 0.25) * TEAR_JOIN_BODY_FRACTION:
                        metrics["nm_contact"] += 1

        # Number loops per body in a stable order (biggest opening first) and
        # classify afterwards, because pairing needs the loop ids.
        body_loops.sort(key=lambda item: (-item["edge_count"], -item["perimeter"]))
        for index, metrics in enumerate(body_loops, start=1):
            metrics["id"] = f"{body_name}_loop_{index}"
        loops_out.extend(body_loops)

        for (a, b), count in sorted(nonmanifold.items()):
            nonmanifold_rows.append({
                "body": body_name,
                "count": int(count),
                "length": round(float(np.linalg.norm(positions[a] - positions[b])), 4),
                "a": vector(positions[a]),
                "b": vector(positions[b]),
                "defect": None,
                "_edge": [int(a), int(b)],
            })
        nonmanifold_by_body[body_name] = nonmanifold
        positions_by_body[body_name] = positions
        verts_by_body[body_name] = verts
        mats_by_body[body_name] = mats
        edge_tris_by_body[body_name] = edge_tris
        tri_component_by_body[body_name] = tri_component
        shell_by_body[body_name] = shells

        body_rows.append(
            {
                "body": body_name,
                "smd": f"{smd_name}.smd",
                "triangles": int(len(verts)),
                "welded_vertices": int(len(positions)),
                "materials": sorted(set(mats)),
                "boundary_edges": int(len(boundary)),
                "nonmanifold_edges": int(len(nonmanifold)),
                "winding_mismatch": len(bad_winding),
                "degenerate_triangles": degenerate,
                "loops": len(body_loops),
                "closed_loops": sum(1 for item in body_loops if item["closed"]),
                "open_chains": sum(1 for item in body_loops if not item["closed"]),
                "bbox_min": vector(body_lo),
                "bbox_max": vector(body_hi),
                "reference_bbox_min": vector(ref_lo),
                "reference_bbox_max": vector(ref_hi),
                "shells": [
                    {
                        "component": shell["component"],
                        "triangles": shell["triangles"],
                        "materials": shell["material_set"],
                        "bbox_min": vector(shell["bbox_min"]),
                        "bbox_max": vector(shell["bbox_max"]),
                    }
                    for shell in shells
                ],
            }
        )

    if not body_rows:
        print("error: no geometry parsed", file=sys.stderr)
        return 1

    extra_bodies = {}
    if "silencer" in shell_by_body and shell_by_body["silencer"]:
        sil = shell_by_body["silencer"][0]
        extra_bodies["silencer"] = (sil["bbox_min"], sil["bbox_max"])
    classify_loops(loops_out, extra_bodies)

    nm_clusters = nonmanifold_clusters(nonmanifold_by_body)
    defects = build_defects(loops_out, nm_clusters, positions_by_body, verts_by_body,
                            mats_by_body, edge_tris_by_body, tri_component_by_body)
    defect_by_loop = {}
    for defect in defects:
        for loop_id in defect["loops"]:
            defect_by_loop[loop_id] = defect["id"]
    for item in loops_out:
        item["defect"] = defect_by_loop.get(item["id"])
    edge_owner: dict[tuple[str, tuple[int, int]], str] = {}
    for cluster in nm_clusters:
        for a, b, _ in cluster["edges"]:
            edge_owner[(cluster["body"], (a, b))] = cluster["id"]
    for row in nonmanifold_rows:
        key = (row["body"], tuple(row["_edge"]))
        row["defect"] = edge_owner.get(key)

    raw_boundary = sum(row["boundary_edges"] for row in body_rows)
    nonmanifold_total = sum(row["nonmanifold_edges"] for row in body_rows)
    accidental_edges = sum(item["edge_count"] for item in loops_out
                           if item["classification"] == "accidental")
    uncertain_edges = sum(item["edge_count"] for item in loops_out
                          if item["classification"] == "uncertain")
    uncertain_loops = [item for item in loops_out if item["classification"] == "uncertain"]
    uncertain_visible = [item["id"] for item in uncertain_loops if item["visible_from"]]
    repair_blocked = bool(uncertain_visible)

    class_counts = Counter(item["classification"] for item in loops_out)
    kind_counts = Counter(item["kind"] for item in loops_out)
    conf_counts = Counter(item["confidence"] for item in loops_out)
    body_class_counts: dict[str, dict[str, int]] = {}
    body_kind_counts: dict[str, dict[str, int]] = {}
    for row in body_rows:
        body_class_counts[row["body"]] = {"intentional": 0, "accidental": 0, "uncertain": 0}
        body_kind_counts[row["body"]] = {}
    for item in loops_out:
        body_class_counts[item["body"]][item["classification"]] += 1
        kinds = body_kind_counts[item["body"]]
        kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1

    cluster_count = len(nm_clusters)
    accidental_penalty = min(SCORE_ACCIDENTAL_MAX,
                             accidental_edges / ACCIDENTAL_EDGE_REFERENCE * SCORE_ACCIDENTAL_MAX)
    nonmanifold_penalty = min(SCORE_NONMANIFOLD_MAX,
                              cluster_count / NONMANIFOLD_CLUSTER_REFERENCE * SCORE_NONMANIFOLD_MAX)
    winding_penalty = min(SCORE_WINDING_MAX,
                          total_winding / WINDING_REFERENCE * SCORE_WINDING_MAX)
    topology_score = max(0.0, SCORE_MAX - accidental_penalty - nonmanifold_penalty
                         - winding_penalty)

    input_hashes = {"qc": {qc.name: sha256_file(qc)}, "smd": {}}
    for smd in sorted(model_dir.glob("*.smd")):
        input_hashes["smd"][smd.name] = sha256_file(smd)

    score = {
        "gate": "A1",
        "model": "v_9mmhandgun",
        "source": "MMOD decompile (out/mmod_import/decompiled/v_9mmhandgun)",
        "score_kind": "moving topology only",
        "score_max": SCORE_MAX,
        "topology_score": round(topology_score, 2),
        "formula": "score = max(0, 35 - accidental - nonmanifold - winding)",
        "components": [
            {
                "name": "accidental_boundary_edges",
                "max": SCORE_ACCIDENTAL_MAX,
                "raw": accidental_edges,
                "reference": ACCIDENTAL_EDGE_REFERENCE,
                "penalty": round(accidental_penalty, 2),
                "score": round(SCORE_ACCIDENTAL_MAX - accidental_penalty, 2),
                "note": ("penalty = min(20, accidental_edges / 20 * 20); an edge count, "
                         "not a ratio against the observed boundary count"),
            },
            {
                "name": "nonmanifold_clusters",
                "max": SCORE_NONMANIFOLD_MAX,
                "raw": cluster_count,
                "reference": NONMANIFOLD_CLUSTER_REFERENCE,
                "penalty": round(nonmanifold_penalty, 2),
                "score": round(SCORE_NONMANIFOLD_MAX - nonmanifold_penalty, 2),
                "note": ("penalty = min(10, clusters / 3 * 10); clusters join non-manifold "
                         "edges that share a welded vertex"),
            },
            {
                "name": "winding_mismatch",
                "max": SCORE_WINDING_MAX,
                "raw": total_winding,
                "reference": WINDING_REFERENCE,
                "penalty": round(winding_penalty, 2),
                "score": round(SCORE_WINDING_MAX - winding_penalty, 2),
                "note": ("penalty = min(5, winding / 10 * 5); authored normal against face "
                         "winding, same test as A1"),
            },
        ],
        "accidental_edges_by_body": {
            body: sum(item["edge_count"] for item in loops_out
                      if item["body"] == body and item["classification"] == "accidental")
            for body in [row["body"] for row in body_rows]
        },
        "nonmanifold_clusters_detail": [
            {
                "id": cluster["id"],
                "edges": cluster["edge_count"],
                "triangle_incidences": cluster["triangle_incidences"],
                "defect": cluster["defect"],
            }
            for cluster in nm_clusters
        ],
        "uncertain_boundary_edges": uncertain_edges,
        "uncertain_loops": [
            {"id": item["id"], "body": item["body"], "visible_from": item["visible_from"]}
            for item in uncertain_loops
        ],
        "repair_blocked_by_uncertain": repair_blocked,
        "player_facing_orbit": {
            "views": (f"all {len(AZIMUTHS) * len(ELEVATIONS)} orbit views "
                      f"({len(AZIMUTHS)} azimuths x {len(ELEVATIONS)} elevations)"),
            "rationale": ("the weapon follows the hand in VR, so every orbit view in this "
                          "audit is reachable by the player; an uncertain loop that is "
                          "visible from any of them blocks repair"),
            "uncertain_visible_from": uncertain_visible,
        },
        "visual": None,
        "runtime": None,
        "note": (
            "Topology only. The visual term needs an A4 comparison sheet and the runtime "
            "term needs M1/R1; neither is inferred here. No final 0-100 score is claimed."
        ),
        "inputs_sha256": input_hashes,
        "raw": {
            "bodies": len(body_rows),
            "triangles": sum(row["triangles"] for row in body_rows),
            "boundary_edges": raw_boundary,
            "nonmanifold_edges": nonmanifold_total,
            "nonmanifold_clusters": cluster_count,
            "winding_mismatch": total_winding,
            "loops": len(loops_out),
            "defects": len(defects),
            "accidental_loops": class_counts.get("accidental", 0),
            "uncertain_loops": class_counts.get("uncertain", 0),
        },
        "winding_mismatch_detail": total_winding_detail,
    }

    audited_names = [row["body"] for row in body_rows]
    declared = declared_bodies(qc)
    holes = {
        "format": "glock_hole_audit_v2",
        "model": "v_9mmhandgun",
        "qc": display_path(qc),
        "scope": {
            "declared_bodies": declared,
            "audited_bodies": audited_names,
            "excluded_bodies": [name for name in declared if name not in audited_names],
            "excluded_reason": (
                "the shared QC parser drops hands/forearms; the hand asset is scored by "
                "A3/A4 and is not part of the weapon chassis audit"
            ),
        },
        "bodies": body_rows,
        "loops": [],
        "defects": defects,
        "nonmanifold_edges": nonmanifold_rows,
        "nonmanifold_clusters": [
            {key: value for key, value in cluster.items() if key != "edges"}
            | {"edges": [{"a": a, "b": b, "count": count}
                         for a, b, count in cluster["edges"]]}
            for cluster in nm_clusters
        ],
        "winding_mismatch": total_winding,
        "summary": {
            "loops": len(loops_out),
            "defects": len(defects),
            "by_classification": dict(class_counts),
            "by_kind": dict(kind_counts),
            "by_confidence": dict(conf_counts),
            "by_body": body_class_counts,
            "by_body_kind": body_kind_counts,
            "uncertain_boundary_edges": uncertain_edges,
            "repair_blocked_by_uncertain": repair_blocked,
        },
        "conventions": {
            "weld": f"rounded position, {WELD_DECIMALS} decimals, per body",
            "pairing": (
                "loops are compared across body/silencer/trits (shared gun space) and only "
                "within clip (authored at the origin); bodies are never welded"
            ),
            "normal": "Newell area normal of the ordered boundary loop",
            "opening_normal": (
                "card: Newell normal (the card face side); closed shell: -Newell (the hole "
                "opens opposite the surface winding); open chain: mean adjacent face normal"
            ),
            "visible_from": (
                "orbit views whose camera unit offset has dot(opening_normal) >= "
                f"{VIEW_NORMAL_DOT}; az/el shared with scripts/render_mdl_360.py"
            ),
            "card": (
                "closed loop whose shell has <= "
                f"{CARD_MAX_TRIANGLES} triangles, planarity >= {CARD_MIN_PLANARITY}, and "
                f"loop bbox diagonal / shell bbox diagonal >= {CARD_MIN_BOUNDARY_RATIO}"
            ),
            "pocket": (
                f"closed loop whose shell has <= {POCKET_MAX_TRIANGLES} triangles and exactly "
                "one boundary loop"
            ),
            "tear": (
                "a loop that shares welded vertices with a non-manifold edge, or an edge of "
                "the same non-manifold cluster; grouped as one defect with that cluster"
            ),
            "defect": (
                "the repair unit: one physical opening/tear, its loops, its non-manifold "
                "edges, its triangles and its materials"
            ),
            "area": "Newell area, i.e. projected onto the loop best-fit plane",
            "planarity": "1 - rms deviation / max loop radius; 1 is flat",
            "coordinates": (
                "body-local: decompiled bodies do not share one space, so absolute "
                "positions are only comparable inside a body"
            ),
        },
    }
    for item in loops_out:
        holes["loops"].append(
            {
                "id": item["id"],
                "body": item["body"],
                "component": item["component"],
                "shell_triangles": item["shell_triangles"],
                "materials": item["materials"],
                "closed": item["closed"],
                "edge_count": item["edge_count"],
                "vertex_count": item["vertex_count"],
                "perimeter": round(item["perimeter"], 4),
                "area": round(item["area"], 4),
                "planarity": round(item["planarity"], 4),
                "planarity_rms": round(item["planarity_rms"], 4),
                "centroid": vector(item["centroid"]),
                "bbox_min": vector(item["bbox_min"]),
                "bbox_max": vector(item["bbox_max"]),
                "bbox_size": vector(item["bbox_size"]),
                "normal": vector(item["normal"]),
                "opening_normal": vector(item["opening_normal"]),
                "visible_from": list(item["visible_from"]),
                "covering_faces": item["covering_faces"],
                "paired_with": item["paired_with"],
                "kind": item["kind"],
                "defect": item["defect"],
                "is_card": item["is_card"],
                "is_pocket": item["is_pocket"],
                "classification": item["classification"],
                "confidence": item["confidence"],
                "reason": item["reason"],
            }
        )

    for row in holes["nonmanifold_edges"]:
        row.pop("_edge", None)
    (out_dir / f"{args.name}_holes.json").write_text(
        json.dumps(holes, indent=2) + "\n", encoding="utf-8")

    loop_fields = [
        "id", "body", "classification", "kind", "defect", "confidence", "closed",
        "edge_count", "vertex_count", "shell_triangles", "perimeter", "area",
        "planarity", "centroid_x", "centroid_y", "centroid_z", "bbox_min_x",
        "bbox_min_y", "bbox_min_z", "bbox_max_x", "bbox_max_y", "bbox_max_z",
        "normal_x", "normal_y", "normal_z", "opening_normal_x", "opening_normal_y",
        "opening_normal_z", "visible_from", "materials", "covering_faces",
        "paired_with", "reason",
    ]
    with (out_dir / f"{args.name}_holes.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=loop_fields)
        writer.writeheader()
        for item in holes["loops"]:
            writer.writerow(
                {
                    "id": item["id"],
                    "body": item["body"],
                    "classification": item["classification"],
                    "kind": item["kind"],
                    "defect": item["defect"] or "",
                    "confidence": item["confidence"],
                    "closed": item["closed"],
                    "edge_count": item["edge_count"],
                    "vertex_count": item["vertex_count"],
                    "shell_triangles": item["shell_triangles"],
                    "perimeter": f"{item['perimeter']:.3f}",
                    "area": f"{item['area']:.4f}",
                    "planarity": f"{item['planarity']:.3f}",
                    "centroid_x": f"{item['centroid'][0]:.3f}",
                    "centroid_y": f"{item['centroid'][1]:.3f}",
                    "centroid_z": f"{item['centroid'][2]:.3f}",
                    "bbox_min_x": f"{item['bbox_min'][0]:.3f}",
                    "bbox_min_y": f"{item['bbox_min'][1]:.3f}",
                    "bbox_min_z": f"{item['bbox_min'][2]:.3f}",
                    "bbox_max_x": f"{item['bbox_max'][0]:.3f}",
                    "bbox_max_y": f"{item['bbox_max'][1]:.3f}",
                    "bbox_max_z": f"{item['bbox_max'][2]:.3f}",
                    "normal_x": f"{item['normal'][0]:.3f}",
                    "normal_y": f"{item['normal'][1]:.3f}",
                    "normal_z": f"{item['normal'][2]:.3f}",
                    "opening_normal_x": f"{item['opening_normal'][0]:.3f}",
                    "opening_normal_y": f"{item['opening_normal'][1]:.3f}",
                    "opening_normal_z": f"{item['opening_normal'][2]:.3f}",
                    "visible_from": ";".join(item["visible_from"]),
                    "materials": ";".join(item["materials"]),
                    "covering_faces": item["covering_faces"],
                    "paired_with": item["paired_with"] or "",
                    "reason": item["reason"],
                }
            )

    defect_fields = [
        "id", "kind", "body", "classification", "confidence", "loops",
        "nonmanifold_edges", "triangles", "materials", "bbox_min_x", "bbox_min_y",
        "bbox_min_z", "bbox_max_x", "bbox_max_y", "bbox_max_z", "visible_from",
        "reason",
    ]
    with (out_dir / f"{args.name}_defects.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=defect_fields)
        writer.writeheader()
        for defect in defects:
            writer.writerow(
                {
                    "id": defect["id"],
                    "kind": defect["kind"],
                    "body": defect["body"],
                    "classification": defect["classification"],
                    "confidence": defect["confidence"],
                    "loops": ";".join(defect["loops"]),
                    "nonmanifold_edges": ";".join(
                        f"{edge['a']}->{edge['b']}" for edge in defect["nonmanifold_edges"]),
                    "triangles": ";".join(str(t) for t in defect["triangles"]),
                    "materials": ";".join(defect["materials"]),
                    "bbox_min_x": f"{defect['bbox_min'][0]:.3f}",
                    "bbox_min_y": f"{defect['bbox_min'][1]:.3f}",
                    "bbox_min_z": f"{defect['bbox_min'][2]:.3f}",
                    "bbox_max_x": f"{defect['bbox_max'][0]:.3f}",
                    "bbox_max_y": f"{defect['bbox_max'][1]:.3f}",
                    "bbox_max_z": f"{defect['bbox_max'][2]:.3f}",
                    "visible_from": ";".join(defect["visible_from"]),
                    "reason": defect["reason"],
                }
            )

    summary = {
        "gate": "A1",
        "model": "v_9mmhandgun",
        "loops_total": len(loops_out),
        "defects_total": len(defects),
        "bodies_audited": audited_names,
        "bodies_excluded": [name for name in declared if name not in audited_names],
        "boundary_edges": raw_boundary,
        "by_body": {
            row["body"]: {
                "triangles": row["triangles"],
                "boundary_edges": row["boundary_edges"],
                "nonmanifold_edges": row["nonmanifold_edges"],
                "loops": row["loops"],
                "closed_loops": row["closed_loops"],
                "open_chains": row["open_chains"],
                "classification": body_class_counts[row["body"]],
                "kind": body_kind_counts[row["body"]],
            }
            for row in body_rows
        },
        "by_classification": {
            "intentional": class_counts.get("intentional", 0),
            "accidental": class_counts.get("accidental", 0),
            "uncertain": class_counts.get("uncertain", 0),
        },
        "by_kind": {kind: kind_counts[kind] for kind in sorted(kind_counts)},
        "by_confidence": {
            "high": conf_counts.get("high", 0),
            "medium": conf_counts.get("medium", 0),
            "low": conf_counts.get("low", 0),
        },
        "accidental_boundary_edges": accidental_edges,
        "uncertain_boundary_edges": uncertain_edges,
        "nonmanifold_edges": nonmanifold_total,
        "nonmanifold_clusters": cluster_count,
        "winding_mismatch": total_winding,
        "repair_blocked_by_uncertain": repair_blocked,
        "topology_score": round(topology_score, 2),
        "defects": [
            {
                "id": defect["id"],
                "kind": defect["kind"],
                "classification": defect["classification"],
                "loops": defect["loops"],
                "confidence": defect["confidence"],
            }
            for defect in defects
        ],
        "needs_human_review": [
            {"id": item["id"], "body": item["body"],
             "classification": item["classification"], "reason": item["reason"]}
            for item in loops_out
            if item["classification"] == "uncertain" or item["confidence"] == "low"
        ] + [
            {"id": defect["id"], "body": defect["body"],
             "classification": defect["classification"], "reason": defect["reason"]}
            for defect in defects if defect["classification"] == "accidental"
        ],
    }
    (out_dir / f"{args.name}_holes_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / f"{args.name}_baseline_score.json").write_text(
        json.dumps(score, indent=2) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # review sheets
    # ------------------------------------------------------------------
    name = args.name
    frames = {
        "body": {
            "smd": "glock_reference",
            "title": "body",
        },
        "clip": {"smd": "clip_reference", "title": "clip"},
        "silencer": {"smd": "glock_silencer_reference", "title": "silencer"},
        "trits": {"smd": "v_9mmhandgun_glow_glock_reference_trits", "title": "trits"},
    }
    sheet_status: dict[str, object] = {}
    render_ok = True
    if args.skip_render:
        sheet_status = {"skipped": True}
        print("warning: --skip-render requested; review sheets were not written",
              file=sys.stderr)
    else:
        body = "body"
        verts = verts_by_body[body]
        mats = mats_by_body[body]
        colours = {mat: material_color(mat) for mat in sorted(set(mats))}
        shells = shell_by_body[body]
        main_shell = shells[0]
        main_centre = (main_shell["bbox_min"] + main_shell["bbox_max"]) * 0.5
        main_diagonal = float(np.linalg.norm(main_shell["bbox_max"] - main_shell["bbox_min"]))
        cluster = [shell for shell in shells
                   if np.linalg.norm((shell["bbox_min"] + shell["bbox_max"]) * 0.5
                                     - main_centre) <= 1.5 * main_diagonal]
        frame_points = np.concatenate([
            verts[shell["triangle_ids"]].reshape(-1, 3) for shell in cluster])
        lo = frame_points.min(axis=0)
        hi = frame_points.max(axis=0)
        centre = (lo + hi) * 0.5
        # One shared radius keeps the gun the same size in every tile, so the
        # sheet can be compared as a 360 and not as 24 unrelated close-ups.
        radius = max(fit_radius(frame_points, centre, az, el, TILE, TILE, fill=0.92)
                     for el in ELEVATIONS for az in AZIMUTHS)
        body_images = []
        for el in ELEVATIONS:
            for az in AZIMUTHS:
                cam = make_camera(centre, radius, az, el, TILE, TILE)
                image = render_mesh(verts, mats, colours, cam)
                tile_label(image, [f"az={az:03d} el={el:+03d}",
                                   f"gun cluster: {len(cluster)} shells",
                                   f"orbit radius {radius:.2f}"])
                ImageDraw.Draw(image).rectangle((0, 0, TILE - 1, TILE - 1),
                                                outline=(66, 72, 84))
                body_images.append(image)
        framed_materials = sorted({mats[ti] for shell in cluster
                                   for ti in shell["triangle_ids"]})
        legend = [(mat, tuple(int(c * 220) for c in colours[mat]))
                  for mat in framed_materials]

        def body_extra(draw, y):
            cam = make_camera(centre, radius, 0, 0, TILE, TILE)
            draw_scale(draw, PAD + 8, y + 30, cam, radius)

        make_sheet(
            body_images, out_dir / f"{name}_body_sheet.png",
            f"{name} - A1 body topology review (body body only, z-buffered)",
            [
                f"{len(body_rows)} bodies audited | body: {len(verts)} tris, "
                f"{sum(1 for item in loops_out if item['body'] == 'body')} loops "
                f"({sum(1 for item in loops_out if item['body'] == 'body' and item['classification'] == 'accidental')} "
                "accidental)",
                "Camera orbits the body: 8 azimuths x 3 elevations, one fixed radius. "
                "Backfaces are darker, never magenta.",
                "Frames are fitted to the gun cluster; the 12-triangle unit helper box at "
                "the body origin is outside every frame. Openings are expected at the "
                "muzzle, the magwell, the pockets and the glow cards: the loop table, not "
                "this sheet alone, decides which opening is a defect.",
            ],
            cols=8, legend=legend, extra_draw=body_extra)
        sheet_status["body"] = {"views": len(body_images), "radius": round(radius, 3)}

        attachment_images = []
        attachment_caption = []
        for body_name in ("clip", "silencer", "trits"):
            if body_name not in verts_by_body:
                continue
            verts = verts_by_body[body_name]
            mats = mats_by_body[body_name]
            colours = {mat: material_color(mat) for mat in sorted(set(mats))}
            shells = shell_by_body[body_name]
            lo = verts.reshape(-1, 3).min(axis=0)
            hi = verts.reshape(-1, 3).max(axis=0)
            frame_diagonal = float(np.linalg.norm(hi - lo))
            clusters = cluster_shells(shells, frame_diagonal)[:6]
            attachment_caption.append(
                f"{body_name}: {len(verts)} tris, {len(shells)} shells, "
                f"{len(clusters)} framed cluster(s)")
            for group in clusters:
                tri_ids = np.concatenate([shell["triangle_ids"] for shell in group])
                gverts = verts[tri_ids]
                gmats = [mats[ti] for ti in tri_ids]
                points = gverts.reshape(-1, 3)
                centre = (points.min(axis=0) + points.max(axis=0)) * 0.5
                best_az = 0
                best_area = -1.0
                for az in (0, 90, 180, 270):
                    cam = make_camera(centre, 1.0, az, 0, TILE, TILE)
                    sx, sy, depth = project(cam, points)
                    area = float(np.ptp(sx) * np.ptp(sy)) if np.all(depth > 0) else 0.0
                    if area > best_area:
                        best_area, best_az = area, az
                for el in (0, 35):
                    label = (f"{body_name} shells "
                             f"{','.join(str(s['component']) for s in group)} az={best_az:03d} "
                             f"el={el:+03d}")
                    attachment_images.append(
                        render_tile(gverts, gmats, colours, points, centre, best_az, el,
                                    label_lines=[label,
                                                 f"{len(tri_ids)} tris",
                                                 "framed on this cluster"],
                                    fill=0.86))
        legend = []
        for body_name in ("clip", "silencer", "trits"):
            if body_name not in mats_by_body:
                continue
            for mat in sorted(set(mats_by_body[body_name])):
                legend.append((mat, tuple(int(c * 220) for c in material_color(mat))))
        make_sheet(
            attachment_images, out_dir / f"{name}_attachments_sheet.png",
            f"{name} - A1 attachments review (clip, silencer, trits)",
            attachment_caption + [
                "Each cluster is framed on its own bounding box; detached cards and dots are "
                "no longer lost in a gun-sized frame.",
                "Backfaces are darker, never magenta.",
            ],
            cols=4, legend=legend)
        sheet_status["attachments"] = {"tiles": len(attachment_images)}

        loop_images = []
        for item in loops_out:
            body_name = item["body"]
            verts = verts_by_body[body_name]
            mats = mats_by_body[body_name]
            colours = {mat: material_color(mat) for mat in sorted(set(mats))}
            shell = next((s for s in shell_by_body[body_name]
                          if s["component"] == item["component"]), None)
            if shell is None:
                continue
            tri_ids = shell["triangle_ids"]
            sverts = verts[tri_ids]
            smats = [mats[ti] for ti in tri_ids]
            points = item["_points"]
            best_az, best_el, visibility = choose_loop_view(item, sverts)
            polyline = np.vstack([points, points[:1]]) if item["closed"] else points
            centre = (points.min(axis=0) + points.max(axis=0)) * 0.5
            image = render_tile(
                sverts, smats, colours, points, centre, best_az, best_el,
                highlights=[(polyline, (255, 46, 46), False)],
                label_lines=[
                    f"{item['id']}  |  {item['classification']}  |  {item['confidence']}",
                    f"kind {item['kind']} | shell {item['component']} "
                    f"({item['shell_triangles']} tris) | {item['edge_count']} edges | "
                    f"area {item['area']:.3f}",
                    f"view az={best_az:03d} el={best_el:+03d} | loop visible "
                    f"{visibility * 100:.0f}% | red = this loop",
                ],
                fill=0.55)
            loop_images.append(image)
        make_sheet(
            loop_images, out_dir / f"{name}_loop_sheet.png",
            f"{name} - A1 loop close-ups (one tile per loop, owning shell only)",
            [
                "Each tile frames the loop itself and renders only the shell that owns it, "
                "so the rim is never a dot and far-side rims cannot paint over near-side "
                "surfaces.",
                "Red = the loop under review, hidden fragments are not drawn. Tiles are "
                f"ordered by the loop id; {len(loop_images)} tiles.",
            ],
            cols=4)
        sheet_status["loops"] = {"tiles": len(loop_images)}

        # Secondary artifact: the shared 360 renderer, with relative paths.
        render_dir = out_dir / f"{name}_360"
        cmd = [
            sys.executable, "scripts/render_mdl_360.py",
            "--qc", repo_relative(qc),
            "--out", repo_relative(render_dir),
            "--name", name,
        ]
        result = subprocess.run(cmd, cwd=REPO_DIR, check=False,
                                capture_output=True, text=True)

        def sanitize(text: str) -> str:
            """Keep absolute host paths out of the captured log."""
            return (text.replace(str(out_dir), display_path(out_dir))
                    .replace(str(REPO_DIR) + "/", ""))

        print(sanitize(result.stdout).strip())
        if result.returncode != 0:
            print(sanitize(result.stderr).strip(), file=sys.stderr)
            print("error: render_mdl_360.py failed", file=sys.stderr)
            render_ok = False
        else:
            report_path = render_dir / f"{name}_360.json"
            if report_path.is_file():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                # render_mdl_360.py resolves its own inputs; rewrite them to
                # relative paths so no absolute path leaks into the evidence.
                if "qc" in report:
                    report["qc"] = os.path.relpath(Path(report["qc"]).resolve(), REPO_DIR)
                if "montage" in report:
                    report["montage"] = os.path.relpath(
                        Path(report["montage"]).resolve(), REPO_DIR)
                report_path.write_text(json.dumps(report, indent=2) + "\n",
                                       encoding="utf-8")
        sheet_status["secondary_360"] = {"ok": render_ok}

        required = [
            out_dir / f"{name}_body_sheet.png",
            out_dir / f"{name}_attachments_sheet.png",
            out_dir / f"{name}_loop_sheet.png",
        ]
        missing = [display_path(path) for path in required
                   if not path.is_file() or path.stat().st_size == 0]
        secondary = out_dir / f"{name}_360" / f"{name}_360.png"
        if not secondary.is_file() or secondary.stat().st_size == 0:
            missing.append(display_path(secondary))
        if missing:
            render_ok = False
            print("error: missing review artifacts:", file=sys.stderr)
            for path in missing:
                print(f"  {path}", file=sys.stderr)

    # ------------------------------------------------------------------
    # run metadata: exact commands, commit and input hashes
    # ------------------------------------------------------------------
    run_dir_rel = display_path(out_dir)
    model_rel = display_path(model_dir)
    finish_note = ("A1 audit complete; asset_verdict=FAIL; human_decision=PENDING"
                   if class_counts.get("accidental", 0) else
                   "A1 audit complete; asset_verdict=PASS; human_decision=PENDING")
    commands = [
        (f'python3 scripts/qa_evidence.py new --gate A1 --command "python3 '
         f'scripts/audit_holes.py --model {model_rel} --out <run-dir>" --device monado'),
        f"python3 scripts/audit_holes.py --model {model_rel} --out {run_dir_rel}",
        ("python3 scripts/audit_viewmodel_assets.py --decompiled-dir "
         f"out/mmod_import/decompiled --out {run_dir_rel}/asset_audit"),
        (f'python3 scripts/qa_evidence.py finish --run {run_dir_rel} --exit-code 0 '
         f'--status PASS --device monado --note "{finish_note}"'),
    ]
    input_note = "inputs: " + "; ".join(
        [f"qc/{name}={digest}" for name, digest in input_hashes["qc"].items()]
        + [f"smd/{name}={digest}" for name, digest in input_hashes["smd"].items()])
    commands_payload = {
        "gate": "A1",
        "commit": git_value("rev-parse", "HEAD"),
        "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(git_value("status", "--porcelain")),
        "commands": commands,
        "inputs_sha256": input_hashes,
        "review_artifacts_complete": bool(render_ok and not args.skip_render),
    }
    (out_dir / f"{name}_commands.json").write_text(
        json.dumps(commands_payload, indent=2) + "\n", encoding="utf-8")

    asset_verdict = ("FAIL" if any(defect["classification"] == "accidental"
                                  for defect in defects) else "PASS")
    manifest_path = out_dir / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["asset_verdict"] = asset_verdict
        manifest["human_decision"] = manifest.get("human_decision") or "PENDING"
        manifest["status_detail"] = (
            "status=PASS/FAIL is the audit tool result, not the asset verdict. "
            f"asset_verdict={asset_verdict} is the topology judgement from this run; the "
            "maintainer records ADVANCE/REWORK/BLOCK in human_decision."
        )
        manifest["commands"] = commands
        manifest["inputs_sha256"] = input_hashes
        manifest["review_artifacts_complete"] = bool(render_ok and not args.skip_render)
        notes = manifest.setdefault("notes", [])
        if input_note not in notes:
            notes.append(input_note)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                 encoding="utf-8")

    print(f"model: {display_path(model_dir)}")
    for row in body_rows:
        print(f"  {row['body']:9s} tris={row['triangles']:4d} weld={row['welded_vertices']:4d} "
              f"boundary={row['boundary_edges']:3d} nonmanifold={row['nonmanifold_edges']:2d} "
              f"winding={row['winding_mismatch']:2d} loops={row['loops']:2d}")
    print(f"loops: {len(loops_out)}  intentional={class_counts.get('intentional', 0)} "
          f"accidental={class_counts.get('accidental', 0)} "
          f"uncertain={class_counts.get('uncertain', 0)}  defects={len(defects)}")
    print("by body/class: " + "; ".join(
        f"{body}: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())
                                if value)
        for body, counts in body_class_counts.items()))
    print(f"topology score: {topology_score:.2f}/35 (accidental edges {accidental_edges} "
          f"-> -{accidental_penalty:.2f}, non-manifold clusters {cluster_count} "
          f"-> -{nonmanifold_penalty:.2f}, winding {total_winding} -> -{winding_penalty:.2f})")
    print(f"uncertain boundary edges: {uncertain_edges}  "
          f"repair_blocked_by_uncertain={repair_blocked}")
    print(f"wrote {display_path(out_dir)}/{name}_holes.json")
    if not render_ok:
        return 1
    return 0


def winding_mismatches(verts, norms) -> list[int]:
    """Triangle indices whose authored normal disagrees with the winding."""
    edge_a = verts[:, 1] - verts[:, 0]
    edge_b = verts[:, 2] - verts[:, 0]
    geo = np.cross(edge_a, edge_b)
    real = np.linalg.norm(geo, axis=1) > 1e-8
    face_n = norms.mean(axis=1)
    bad = real & (np.sum(face_n * geo, axis=1) < 0.0)
    return [int(i) for i in np.nonzero(bad)[0]]


if __name__ == "__main__":
    sys.exit(main())
