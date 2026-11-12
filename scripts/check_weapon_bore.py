#!/usr/bin/env python3
"""Measure the authored muzzle pair against the weapon body's long axis.

This is an asset diagnostic only; the renderer uses the runtime grip->muzzle
bone vector (D-027). ``muzzle_pos -> muzzle_pos2`` is a lateral muzzle-flash
quad, so a large angle against the body's long hitbox axis is expected for most
native weapons and does not describe the bore the VR laser and the firing line
follow.

A row is ``ALIGNED`` when the pair is within five degrees of the body's long
hitbox axis, ``OFF-AXIS`` otherwise, and ``NOT-APPLICABLE`` when the weapon has
no barrel. The angle does not take ``abs(dot)``: a fully reversed pair is
OFF-AXIS, not ALIGNED.

This script is read-only. It does not change the firing line and it does not
rewrite an asset. A mismatch is a finding for the maintainer, not an automatic
failure; ``--fail-on-off-axis`` turns the finding into exit code 1 when a CI job
wants to record it.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
NATIVE_DIR = REPO_ROOT / "assets" / "valve_vr" / "models" / "native"
PROFILE = REPO_ROOT / "assets" / "valve_vr" / "models" / "vr_weapons.json"
MDLDEC = SCRIPT_DIR / "mdldec.sh"

# A pair within five degrees of the body's long axis is treated as aligned.
# The current models are expected to be far outside this tolerance.
ALIGNED_DEG = 5.0


def parse_hboxes(qc_path: Path) -> list[dict]:
    """Return the ``$hbox`` entries with their extents and longest axis."""
    boxes = []
    for line in qc_path.read_text(encoding="latin-1", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("$hbox"):
            continue
        parts = line.split('"')
        if len(parts) < 3:
            continue
        head = parts[0].split()
        numbers = parts[2].split()
        if len(numbers) < 6:
            continue
        bone = parts[1]
        lo = [float(v) for v in numbers[:3]]
        hi = [float(v) for v in numbers[3:6]]
        extents = [abs(hi[k] - lo[k]) for k in range(3)]
        axis = max(range(3), key=lambda k: extents[k])
        boxes.append({
            "group": head[1] if len(head) > 1 else "",
            "bone": bone,
            "extents": extents,
            "axis": axis,
            "length": extents[axis],
        })
    return boxes


def parse_nodes_and_skeleton(smd_path: Path):
    """Return (nodes, parent, local transforms) from an SMD."""
    lines = smd_path.read_text(encoding="utf-8", errors="replace").splitlines()
    nodes: dict[int, str] = {}
    parent: dict[int, int] = {}
    local: dict[int, tuple[float, ...]] = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line == "nodes":
            i += 1
            while i < len(lines) and lines[i].strip() != "end":
                parts = lines[i].split('"')
                if len(parts) >= 3:
                    idx = int(parts[0].strip())
                    nodes[idx] = parts[1]
                    parent[idx] = int(parts[2].strip())
                i += 1
        elif line == "skeleton":
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("time"):
                i += 1
            i += 1
            while i < len(lines) and lines[i].strip() != "end":
                parts = lines[i].split()
                if len(parts) >= 7:
                    local[int(parts[0])] = tuple(float(v) for v in parts[1:7])
                i += 1
        i += 1
    return nodes, parent, local


def rotation_x(deg: float):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def rotation_y(deg: float):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rotation_z(deg: float):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def mat_mul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)] for r in range(3)]


def mat_vec(m, v):
    return [sum(m[r][k] * v[k] for k in range(3)) for r in range(3)]


def bone_frames(nodes, parent, local):
    """Return world rotations and positions for every bone in the skeleton."""
    rotations: dict[int, list[list[float]]] = {}
    positions: dict[int, list[float]] = {}
    for idx in sorted(local):
        px, py, pz, rx, ry, rz = local[idx]
        rot = mat_mul(mat_mul(rotation_x(rx), rotation_y(ry)), rotation_z(rz))
        if parent[idx] in rotations:
            parent_rot = rotations[parent[idx]]
            parent_pos = positions[parent[idx]]
            rotations[idx] = mat_mul(parent_rot, rot)
            positions[idx] = [
                parent_pos[k] + mat_vec(parent_rot, [px, py, pz])[k] for k in range(3)
            ]
        else:
            rotations[idx] = rot
            positions[idx] = [px, py, pz]
    return rotations, positions


def find_bone(nodes, name: str) -> int:
    for idx, bone in nodes.items():
        if bone == name:
            return idx
    return -1


def unit(v):
    length = math.sqrt(sum(x * x for x in v))
    if length < 1e-6:
        return None
    return [x / length for x in v]


def angle_between(a, b) -> float:
    ua, ub = unit(a), unit(b)
    if ua is None or ub is None:
        return float("nan")
    # Do NOT take abs(dot): a 180-degree reversed pair is OFF-AXIS, not
    # ALIGNED. abs() would mask a fully reversed pair as 0 degrees.
    dot = max(-1.0, min(1.0, sum(ua[k] * ub[k] for k in range(3))))
    return math.degrees(math.acos(dot))


def profile_muzzles() -> dict[str, int]:
    if not PROFILE.is_file():
        return {}
    data = json.loads(PROFILE.read_text(encoding="utf-8"))
    weapons = data.get("weapons", data)
    result = {}
    for name, entry in weapons.items():
        if isinstance(entry, dict) and "muzzle_attachment" in entry:
            result[name] = int(entry["muzzle_attachment"])
    return result


def diagnose_model(mdl_path: Path, muzzle_attachment: int | None) -> dict:
    if muzzle_attachment is not None and muzzle_attachment < 0:
        return {"model": mdl_path.name, "state": "NOT-APPLICABLE", "note": "no barrel"}

    with tempfile.TemporaryDirectory(prefix="borecheck_") as tmp:
        out_dir = Path(tmp)
        try:
            subprocess.run(
                [str(MDLDEC), str(mdl_path), str(out_dir)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            return {"model": mdl_path.name, "state": "SKIP", "note": "mdldec failed"}

        qc_path = out_dir / (mdl_path.stem + ".qc")
        if not qc_path.is_file():
            return {"model": mdl_path.name, "state": "SKIP", "note": "no QC"}

        boxes = parse_hboxes(qc_path)
        if not boxes:
            return {"model": mdl_path.name, "state": "SKIP", "note": "no hitbox"}
        body = max(boxes, key=lambda box: box["length"])

        best = None
        for smd_path in sorted(out_dir.glob("*.smd")):
            nodes, parent, local = parse_nodes_and_skeleton(smd_path)
            muzzle = find_bone(nodes, "muzzle_pos")
            muzzle2 = find_bone(nodes, "muzzle_pos2")
            body_bone = find_bone(nodes, body["bone"])
            if muzzle < 0 or muzzle2 < 0 or body_bone < 0:
                continue
            rotations, positions = bone_frames(nodes, parent, local)
            pair = [positions[muzzle2][k] - positions[muzzle][k] for k in range(3)]
            if sum(x * x for x in pair) < 1e-6:
                continue
            axis = mat_vec(rotations[body_bone], [1.0 if k == body["axis"] else 0.0 for k in range(3)])
            best = (smd_path.name, body, pair, axis)
            break

        if best is None:
            return {
                "model": mdl_path.name,
                "state": "SKIP",
                "note": f"bones not found ({body['bone']}, muzzle_pos, muzzle_pos2)",
            }

        smd_name, box, pair, axis = best
        angle = angle_between(pair, axis)
        dot = sum(unit(pair)[k] * unit(axis)[k] for k in range(3))
        state = "ALIGNED" if angle <= ALIGNED_DEG else "OFF-AXIS"
        return {
            "model": mdl_path.name,
            "state": state,
            "angle": angle,
            "pair_len": math.sqrt(sum(x * x for x in pair)),
            "pair": pair,
            "barrel": axis,
            "hbox_bone": box["bone"],
            "hbox_axis": "XYZ"[box["axis"]],
            "hbox_len": box["length"],
            "dot_sign": dot,
            "smd": smd_name,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true",
                        help="return 1 when a barrel weapon is off-axis")
    parser.add_argument("--fail-on-off-axis", action="store_true",
                        help="exit 1 when any row state is OFF-AXIS")
    parser.add_argument("--model", action="append", default=[],
                        help="diagnose only this model (repeatable)")
    parser.add_argument("--json", nargs="?", const="-", default=None, metavar="PATH",
                        help="dump a JSON map {model: {state, pair, angle, "
                             "hbox_bone, dot_sign}} to PATH (or stdout if no PATH)")
    args = parser.parse_args()

    muzzles = profile_muzzles()
    models = [NATIVE_DIR / name for name in sorted(args.model)] if args.model else sorted(NATIVE_DIR.glob("*.mdl"))
    if not models:
        print("[FAIL] no native models found")
        return 1

    rows = []
    for mdl_path in models:
        if not mdl_path.is_file():
            print(f"[FAIL] missing model: {mdl_path}")
            return 1
        rows.append(diagnose_model(mdl_path, muzzles.get(mdl_path.name)))

    print(f"{'model':22s} {'state':14s} {'angle':>7s} {'pair':>7s} {'hbox':>6s} {'axis':>4s}  detail")
    print("-" * 100)
    off_axis = 0
    for row in rows:
        if "angle" not in row:
            print(f"{row['model']:22s} {row['state']:14s} {'-':>7s} {'-':>7s} {'-':>6s} {'-':>4s}  {row['note']}")
            continue
        if row["state"] == "OFF-AXIS":
            off_axis += 1
        detail = f"hbox={row['hbox_bone']} dot={row['dot_sign']:+.2f} smd={row['smd']}"
        print(
            f"{row['model']:22s} {row['state']:14s} {row['angle']:6.1f}° "
            f"{row['pair_len']:7.2f} {row['hbox_len']:6.1f} {row['hbox_axis']:>4s}  {detail}"
        )

    print("-" * 100)
    failing = [row for row in rows if row["state"] == "OFF-AXIS"]
    print(f"{off_axis} barrel weapon(s) off the body's long axis by more than {ALIGNED_DEG:.0f}°")
    print("Asset diagnostic: the pair is not the runtime bore (D-027); an OFF-AXIS row is a finding.")
    if failing:
        names = ", ".join(row["model"] for row in failing)
        print(f"[FINDING] {len(failing)} barrel weapon(s) not aligned: {names}")
    else:
        print("[PASS] every barrel weapon is aligned or not applicable")

    if args.json is not None:
        payload = {}
        for row in rows:
            if "barrel" in row:
                payload[row["model"]] = {
                    "state": row["state"],
                    "pair": row["pair"],
                    "angle": row["angle"],
                    "hbox_bone": row["hbox_bone"],
                    "dot_sign": row["dot_sign"],
                }
            else:
                payload[row["model"]] = {
                    "state": row.get("state"),
                    "note": row.get("note"),
                }
        text = json.dumps(payload, indent=2)
        if args.json == "-" or not args.json:
            print(text)
        else:
            Path(args.json).write_text(text, encoding="utf-8")

    if args.fail_on_off_axis and failing:
        return 1
    return 1 if args.strict and failing else 0


if __name__ == "__main__":
    sys.exit(main())
