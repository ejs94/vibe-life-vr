#!/usr/bin/env python3
"""Static asset audit for decompiled GoldSrc viewmodels.

The audit is intentionally cheap: it reads the QC and the body SMDs produced by
mdldec, then reports the defects that can be detected without a renderer:

  * faces whose material has no matching texture file
  * UVs outside [0, 1] or degenerate UV triangles
  * zero normals or winding/normal disagreement (backface culling risk)
  * open boundary edges and non-manifold edges

It does not replace the textured 360-degree render; it is the automated table
that tells you which weapon is worth opening in Blender.

Usage:
    python3 scripts/audit_viewmodel_assets.py \
        --decompiled-dir out/mmod_import/decompiled \
        --out out/evidence/viewmodel_asset_audit
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from render_mdl_360 import parse_qc  # noqa: E402

BODY_RE = re.compile(r'^\s*\$body\s+"([^"]+)"\s+"([^"]+)"', re.I)
BODYGROUP_RE = re.compile(r'^\s*\$bodygroup\s+"([^"]+)"', re.I)


def read_smd_full(path: Path):
    """Return (vertices, normals, uvs, materials) for every triangle vertex."""
    verts: list[tuple[float, float, float]] = []
    norms: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    mats: list[str] = []
    material = "default"
    section = None

    with path.open("r", encoding="latin1", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if line in ("nodes", "skeleton", "triangles"):
                section = line
                continue
            if line == "end":
                section = None
                continue
            if section != "triangles" or not line:
                continue
            parts = line.split()
            if len(parts) == 1:
                material = parts[0]
                continue
            if len(parts) < 9:
                continue
            try:
                verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
                norms.append((float(parts[4]), float(parts[5]), float(parts[6])))
                uvs.append((float(parts[7]), float(parts[8])))
                mats.append(material)
            except ValueError:
                continue

    if len(verts) % 3:
        verts = verts[: len(verts) - (len(verts) % 3)]
        norms = norms[: len(norms) - (len(norms) % 3)]
        uvs = uvs[: len(uvs) - (len(uvs) % 3)]
        mats = mats[: len(mats) - (len(mats) % 3)]

    return (
        np.asarray(verts, dtype=np.float64).reshape((-1, 3, 3)),
        np.asarray(norms, dtype=np.float64).reshape((-1, 3, 3)),
        np.asarray(uvs, dtype=np.float64).reshape((-1, 3, 2)),
        mats,
    )


def texture_exists(model_dir: Path, material: str) -> bool:
    if not material or material == "default":
        return False
    stem = Path(material).stem
    for name in (material, stem + ".bmp", stem + ".png", stem + ".tga"):
        candidate = model_dir / name
        if candidate.is_file():
            return True
    lowered = {p.name.lower(): p for p in model_dir.iterdir() if p.is_file()}
    return any(key in lowered for key in (material.lower(), (stem + ".bmp").lower()))


def boundary_report(verts: np.ndarray):
    weld: dict[tuple[float, float, float], int] = {}
    ids = np.zeros((verts.shape[0], 3), dtype=np.int64)
    for ti in range(verts.shape[0]):
        for vi in range(3):
            key = tuple(np.round(verts[ti, vi], 3).tolist())
            idx = weld.get(key)
            if idx is None:
                idx = len(weld)
                weld[key] = idx
            ids[ti, vi] = idx

    edges: Counter[tuple[int, int]] = Counter()
    for tri in ids:
        if len(set(tri.tolist())) < 3:
            continue
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edges[tuple(sorted((int(a), int(b))))] += 1

    boundary = sum(1 for count in edges.values() if count == 1)
    nonmanifold = sum(1 for count in edges.values() if count > 2)
    return boundary, nonmanifold


def audit_model(model_dir: Path):
    qcs = sorted(model_dir.glob("*.qc"))
    if not qcs:
        return None
    qc = qcs[0]
    bodies = parse_qc(qc)
    if not bodies:
        bodies = []
        for line in qc.read_text(encoding="latin1", errors="replace").splitlines():
            match = BODY_RE.match(line)
            if match:
                bodies.append((match.group(1), match.group(2)))

    all_verts = []
    all_norms = []
    all_uvs = []
    all_mats: list[str] = []
    used = []

    for body_name, smd_name in bodies:
        smd_path = model_dir / f"{smd_name}.smd"
        if not smd_path.is_file():
            continue
        verts, norms, uvs, mats = read_smd_full(smd_path)
        if len(verts) == 0:
            continue
        all_verts.append(verts)
        all_norms.append(norms)
        all_uvs.append(uvs)
        all_mats.extend(mats)
        used.append((body_name, smd_name, int(len(verts))))

    if not all_verts:
        return None

    verts = np.concatenate(all_verts)
    norms = np.concatenate(all_norms)
    uvs = np.concatenate(all_uvs)

    tri_count = int(len(verts))
    missing_material = sum(1 for name in all_mats if not name or name == "default")
    missing_texture = sum(
        1 for name in all_mats if not texture_exists(model_dir, name)
    )

    # SMD triangle strips contain zero-area transition triangles. They are
    # never visible, so exclude them from the UV/normal/winding checks.
    edge_a = verts[:, 1] - verts[:, 0]
    edge_b = verts[:, 2] - verts[:, 0]
    geo_n = np.cross(edge_a, edge_b)
    geo_len = np.linalg.norm(geo_n, axis=1)
    real = geo_len > 1e-8

    uv_eps = 0.05  # the compiler clamps small wrap excursions
    uv_out = int(np.count_nonzero(
        real[:, None, None] & ((uvs < -uv_eps) | (uvs > 1.0 + uv_eps))
    ))
    tri_uv = uvs.reshape((-1, 3, 2))
    uv_area = np.abs(
        (tri_uv[:, 1, 0] - tri_uv[:, 0, 0]) * (tri_uv[:, 2, 1] - tri_uv[:, 0, 1])
        - (tri_uv[:, 2, 0] - tri_uv[:, 0, 0]) * (tri_uv[:, 1, 1] - tri_uv[:, 0, 1])
    )
    degenerate_uv = int(np.count_nonzero(real & (uv_area < 1e-8)))

    norm_len = np.linalg.norm(norms, axis=2)
    zero_normals = int(np.count_nonzero(real[:, None] & (norm_len < 1e-8)))

    face_n = norms.mean(axis=1)
    winding_bad = int(np.count_nonzero(
        real & (np.sum(face_n * geo_n, axis=1) < 0.0)
    ))
    degenerate_geometry = int(np.count_nonzero(~real))

    boundary, nonmanifold = boundary_report(verts)
    hard = missing_material + missing_texture + uv_out + zero_normals + winding_bad
    warn = degenerate_uv + degenerate_geometry + nonmanifold
    verdict = "FAIL" if hard else ("WARN" if warn else "PASS")

    return {
        "model": model_dir.name,
        "verdict": verdict,
        "qc": qc.name,
        "bodies": len(used),
        "triangles": tri_count,
        "materials": len(set(all_mats)),
        "missing_material": missing_material,
        "missing_texture": missing_texture,
        "uv_out_of_range": uv_out,
        "degenerate_uv": degenerate_uv,
        "zero_normals": zero_normals,
        "winding_mismatch": winding_bad,
        "degenerate_geometry": degenerate_geometry,
        "boundary_edges": boundary,
        "nonmanifold_edges": nonmanifold,
        "used_bodies": used,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decompiled-dir",
        type=Path,
        default=REPO_DIR / "out" / "mmod_import" / "decompiled",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_DIR / "out" / "evidence" / "viewmodel_asset_audit",
    )
    args = parser.parse_args()

    if not args.decompiled_dir.is_dir():
        print(f"error: not a directory: {args.decompiled_dir}", file=sys.stderr)
        return 1

    rows = []
    for model_dir in sorted(args.decompiled_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        row = audit_model(model_dir)
        if row:
            rows.append(row)

    if not rows:
        print("error: no auditable models found", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "audit.json"
    csv_path = args.out / "audit.csv"
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    fields = [
        "model", "verdict", "bodies", "triangles", "materials",
        "missing_material", "missing_texture",
        "uv_out_of_range", "degenerate_uv",
        "zero_normals", "winding_mismatch", "degenerate_geometry",
        "boundary_edges", "nonmanifold_edges",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    header = (
        f"{'model':22s} {'verdict':7s} {'tris':>6s} {'mat':>4s} {'missMat':>7s} "
        f"{'missTex':>7s} {'uvOut':>6s} {'degUV':>6s} {'zeroN':>6s} "
        f"{'wind':>5s} {'degGeo':>6s} {'bound':>6s} {'nonman':>6s}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['model']:22s} {row['verdict']:7s} {row['triangles']:6d} {row['materials']:4d} "
            f"{row['missing_material']:7d} {row['missing_texture']:7d} "
            f"{row['uv_out_of_range']:6d} {row['degenerate_uv']:6d} "
            f"{row['zero_normals']:6d} {row['winding_mismatch']:5d} "
            f"{row['degenerate_geometry']:6d} "
            f"{row['boundary_edges']:6d} {row['nonmanifold_edges']:6d}"
        )

    print(f"\nwrote {json_path}")
    print(f"wrote {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
