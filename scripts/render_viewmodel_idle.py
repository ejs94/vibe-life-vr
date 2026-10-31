#!/usr/bin/env python3
"""Render a decompiled viewmodel in its assembled idle pose.

The existing 360 audit renders the SMD reference pose. That pose is not what the
player sees: detachable magazines, bolts, arrows and moving parts sit in their
rest positions instead of the idle animation. This script applies the first
frame of an animation SMD to the reference mesh, then reuses the lightweight
software rasterizer from render_mdl_360.py.

Usage:
    python3 scripts/render_viewmodel_idle.py \
        --qc out/mmod_import/decompiled/v_crossbow/v_crossbow.qc \
        --out out/qa/A4/latest --name v_crossbow_idle
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import smd_lib  # noqa: E402
from render_mdl_360 import (  # noqa: E402
    AZIMUTHS,
    ELEVATIONS,
    make_sheet,
    material_color,
    parse_qc,
    render_view,
)


def first_frame(smd: smd_lib.Smd) -> dict[int, smd_lib.BoneFrame]:
    """Return the first skeleton block (time 0) keyed by bone index."""
    frames: dict[int, smd_lib.BoneFrame] = {}
    for frame in smd.skeleton:
        if frame.index in frames:
            break
        frames[frame.index] = frame
    return frames


def world_transforms(smd: smd_lib.Smd, frames: dict[int, smd_lib.BoneFrame]):
    children: dict[int, list[int]] = {}
    for node in smd.nodes:
        children.setdefault(node.parent, []).append(node.index)

    pos: dict[int, np.ndarray] = {}
    mat: dict[int, np.ndarray] = {}

    def visit(idx: int, parent_pos: np.ndarray, parent_mat: np.ndarray) -> None:
        frame = frames.get(idx)
        if frame is None:
            return
        offset = parent_mat @ np.asarray(frame.pos, dtype=np.float64)
        pos[idx] = parent_pos + offset
        mat[idx] = parent_mat @ np.asarray(
            smd_lib.euler_to_matrix(*frame.rot), dtype=np.float64
        )
        for child in children.get(idx, []):
            visit(child, pos[idx], mat[idx])

    identity = np.eye(3, dtype=np.float64)
    zero = np.zeros(3, dtype=np.float64)
    for node in smd.nodes:
        if node.parent == -1:
            visit(node.index, zero, identity)
    return pos, mat


def pose_body(smd: smd_lib.Smd, rest_pos, rest_mat, anim_pos, anim_mat, excludes):
    verts = []
    norms = []
    mats = []
    cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for tri in smd.triangles:
        if len(tri.verts) < 3:
            continue
        material = tri.material.lower()
        if any(token in material for token in excludes):
            continue
        out_v = []
        out_n = []
        for vertex in tri.verts[:3]:
            parent = vertex.parent
            if parent not in cache:
                if parent in rest_pos and parent in anim_pos:
                    inv_rest = np.linalg.inv(rest_mat[parent])
                    cache[parent] = (inv_rest, anim_mat[parent] @ inv_rest)
                else:
                    cache[parent] = (np.eye(3), np.eye(3))
            inv_rest, delta = cache[parent]
            v = np.asarray(vertex.pos, dtype=np.float64)
            n = np.asarray(vertex.normal, dtype=np.float64)
            out_v.append(anim_pos[parent] + delta @ (v - rest_pos[parent])
                         if parent in rest_pos and parent in anim_pos else v)
            out_n.append(delta @ n)
        verts.append(out_v)
        norms.append(out_n)
        mats.append(tri.material)

    if not verts:
        return None
    return (
        np.asarray(verts, dtype=np.float64),
        np.asarray(norms, dtype=np.float64),
        mats,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qc", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--name", default=None)
    parser.add_argument("--anim", type=Path, default=None)
    parser.add_argument(
        "--exclude",
        default="camerabone,trits,glow,hev_,blank",
        help="comma-separated material substrings to omit (engine helpers/hands)",
    )
    args = parser.parse_args()
    excludes = [item.strip().lower() for item in args.exclude.split(",") if item.strip()]

    qc = args.qc.resolve()
    model_dir = qc.parent
    name = args.name or qc.stem
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    anim_path = args.anim
    if anim_path is None:
        candidates = sorted(model_dir.glob("idle*.smd"))
        if not candidates:
            candidates = sorted(model_dir.glob("draw*.smd"))
        if not candidates:
            raise SystemExit("no idle/draw animation SMD found")
        anim_path = candidates[0]

    anim = smd_lib.parse_smd(str(anim_path))
    anim_frames = first_frame(anim)

    all_v = []
    all_n = []
    all_m = []
    used = []
    for body_name, smd_name in parse_qc(qc):
        smd_path = model_dir / f"{smd_name}.smd"
        if not smd_path.is_file():
            continue
        body = smd_lib.parse_smd(str(smd_path))
        rest_frames = first_frame(body)
        rest_pos, rest_mat = world_transforms(body, rest_frames)
        anim_pos, anim_mat = world_transforms(body, anim_frames)
        posed = pose_body(body, rest_pos, rest_mat, anim_pos, anim_mat, excludes)
        if posed is None:
            continue
        v, n, m = posed
        all_v.append(v)
        all_n.append(n)
        all_m.extend(m)
        used.append((body_name, smd_name, int(len(v))))

    if not all_v:
        raise SystemExit("no posed geometry")

    verts = np.concatenate(all_v)
    norms = np.concatenate(all_n)
    mats = all_m

    lo = verts.reshape(-1, 3).min(axis=0)
    hi = verts.reshape(-1, 3).max(axis=0)
    center = (lo + hi) * 0.5
    radius = max(float(np.linalg.norm(hi - lo)) * 1.65, 1.0)

    material_names = sorted(set(mats))
    colors = {m: material_color(m) for m in material_names}

    views = []
    for el in ELEVATIONS:
        for az in AZIMUTHS:
            label = f"idle {anim_path.name} az={az:03d} el={el:+03d}"
            views.append(render_view(verts, norms, mats, colors, center, radius, az, el, label))

    montage = out_dir / f"{name}_idle_360.png"
    subtitle = (
        f"{len(verts)} tris | {len(used)} bodies | pose={anim_path.name} frame 0 | "
        "darker=backface"
    )
    make_sheet(views, f"{name} - assembled idle pose", subtitle, montage)

    report = {
        "name": name,
        "qc": str(qc),
        "anim": str(anim_path),
        "triangles": int(len(verts)),
        "bodies": used,
        "montage": str(montage),
        "materials": material_names,
    }
    (out_dir / f"{name}_idle_360.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{name}: idle pose {anim_path.name} -> {montage}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
