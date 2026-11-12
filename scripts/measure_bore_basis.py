#!/usr/bin/env python3
"""Measure the authored two-point barrel basis of a viewmodel from bone positions.

The ``authored_bore`` vector is ``muzzle_pos - hud_pos``: the only skeleton bone
pair authored on the barrel axis of these GoldSrc viewmodels. It is the ground
truth the V3 acceptance gate compares the renderer against, not a runtime
integrator, and it never feeds the firing line.

WHY MESH VERTICES ARE EXCLUDED: ``scripts/mdldec.sh`` writes SMD triangle
vertices in a different coordinate space from the ``skeleton`` block (measured
on the SD MP5: mesh bbox X [-0.9, 19.6] while the ``muzzle_pos`` bone sits at
X = -37.8). Vertices, and therefore any PCA of them, cannot be combined with
bone positions; only the ``skeleton`` block is internally consistent, so this
script reads bone world positions exclusively.

Read-only: it decompiles into a temporary directory, never calls the engine,
never rewrites an MDL, and writes nothing except the optional ``--json`` file.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

from check_weapon_bore import (  # noqa: E402  (import after bytecode opt-out)
    MDLDEC, bone_frames, find_bone, mat_vec, parse_hboxes,
    parse_nodes_and_skeleton, unit,
)

MUZZLE, MUZZLE2 = ("muzzle_pos",), ("muzzle_pos2",)
REAR, HAND = ("hud_pos", "HUD_pos"), ("Bip01 R Hand", "grip", "Bip01 L Hand")
HIGH_LEN, HIGH_ANGLE, MEDIUM_LEN = 8.0, 20.0, 4.0


def pick_bone(nodes, candidates):
    """Return (index, name) for the first candidate, exact then case-insensitive."""
    for name in candidates:
        idx = find_bone(nodes, name)
        if idx >= 0:
            return idx, nodes[idx]
    lowered = {bone.lower(): idx for idx, bone in nodes.items()}
    for name in candidates:
        if name.lower() in lowered:
            idx = lowered[name.lower()]
            return idx, nodes[idx]
    return -1, None


def pick_smd(out_dir: Path):
    """Return (path, nodes, parent, local) for the first SMD with a muzzle bone."""
    for candidate in sorted(out_dir.glob("*.smd")):
        nodes, parent, local = parse_nodes_and_skeleton(candidate)
        if pick_bone(nodes, MUZZLE)[0] >= 0:
            return candidate, nodes, parent, local
    return None


def sub(a, b):
    return [a[k] - b[k] for k in range(3)]


def norm(v):
    return math.sqrt(sum(x * x for x in v))


def angle_deg(a, b):
    """Undirected angle: a fully reversed pair still reads 0 degrees."""
    ua, ub = unit(a), unit(b)
    if ua is None or ub is None:
        return None
    dot = max(-1.0, min(1.0, abs(sum(ua[k] * ub[k] for k in range(3)))))
    return math.degrees(math.acos(dot))


def field(vec):
    u = unit(vec)
    return {"length": norm(vec), "unit": [round(x, 6) for x in u] if u else None}


def measure_model(mdl_path: Path) -> dict:
    row = {"model": mdl_path.name, "status": "OK", "confidence": "LOW", "reason": None,
           "smd": None, "authored_bore": None, "flash_pair": None,
           "wrist_to_muzzle": None, "hitbox_axis": None, "angles": {}, "positions": {}}
    with tempfile.TemporaryDirectory(prefix="borebasis_") as tmp:
        out_dir = Path(tmp)
        try:
            subprocess.run([str(MDLDEC), str(mdl_path), str(out_dir)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.CalledProcessError):
            row.update(status="SKIP", reason="mdldec failed")
            return row

        qc_path = out_dir / (mdl_path.stem + ".qc")
        boxes = parse_hboxes(qc_path) if qc_path.is_file() else []
        smd = pick_smd(out_dir)
        if smd is None:
            row.update(status="SKIP", reason="no SMD with a muzzle_pos bone")
            return row
        smd_path, nodes, parent, local = smd
        muzzle, rear = pick_bone(nodes, MUZZLE), pick_bone(nodes, REAR)
        if rear[0] < 0:
            # Never invent a bore without the authored rear anchor.
            row.update(status="NO_REAR_ANCHOR",
                       reason=f"{smd_path.name} has muzzle_pos but no hud_pos")
            return row

        rotations, positions = bone_frames(nodes, parent, local)
        muzzle2, hand = pick_bone(nodes, MUZZLE2), pick_bone(nodes, HAND)
        row["smd"] = smd_path.name
        row["positions"] = {nodes[idx]: [round(x, 3) for x in positions[idx]]
                            for idx, _ in (muzzle, rear, muzzle2, hand) if idx >= 0}
        bore = sub(positions[muzzle[0]], positions[rear[0]])
        row["authored_bore"] = field(bore)

        if muzzle2[0] >= 0:
            flash = sub(positions[muzzle2[0]], positions[muzzle[0]])
            row["flash_pair"] = field(flash)
            row["angles"]["authored_bore_vs_flash"] = angle_deg(bore, flash)
        if hand[0] >= 0:
            wrist = sub(positions[muzzle[0]], positions[hand[0]])
            row["wrist_to_muzzle"] = field(wrist)
            row["angles"]["authored_bore_vs_wrist"] = angle_deg(bore, wrist)

        # The body's long hitbox axis, rotated into the same model space as the
        # bones, is the independent cross-check for the authored bore.
        for box in sorted(boxes, key=lambda b: -b["length"]):
            bone = find_bone(nodes, box["bone"])
            if bone >= 0:
                axis = mat_vec(rotations[bone], [1.0 if k == box["axis"] else 0.0
                                                 for k in range(3)])
                row["hitbox_axis"] = {"bone": box["bone"], "axis": "XYZ"[box["axis"]],
                                      **field(axis)}
                row["angles"]["authored_bore_vs_hitbox"] = angle_deg(bore, axis)
                break

        vs_hitbox = row["angles"].get("authored_bore_vs_hitbox")
        if norm(bore) >= HIGH_LEN and vs_hitbox is not None and vs_hitbox <= HIGH_ANGLE:
            row["confidence"] = "HIGH"
        elif norm(bore) >= MEDIUM_LEN:
            row["confidence"] = "MEDIUM"
    return row


def cell(value, width=8):
    return f"{value:{width}.1f}" if value is not None else f"{'-':>{width}s}"


def print_table(rows) -> None:
    print(f"{'model':20s} {'authored_bore':32s} {'len':>6s} {'vs_flash':>8s} "
          f"{'vs_hitbox':>9s} {'vs_wrist':>8s}  confidence")
    print("-" * 104)
    for row in rows:
        if row["status"] != "OK":
            print(f"{row['model']:20s} {row['status']:32s}  {row['reason']}")
            continue
        bore, angles = row["authored_bore"], row["angles"]
        text = "(" + ",".join(f"{x:+.2f}" for x in bore["unit"]) + ")"
        print(f"{row['model']:20s} {text:32s} {bore['length']:6.2f} "
              f"{cell(angles.get('authored_bore_vs_flash'))} "
              f"{cell(angles.get('authored_bore_vs_hitbox'), 9)} "
              f"{cell(angles.get('authored_bore_vs_wrist'))}  {row['confidence']}")
    print("-" * 104)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", default=[], metavar="PATH",
                        help="measure this .mdl (repeatable)")
    parser.add_argument("--dir", metavar="DIR", help="measure every *.mdl in DIR")
    parser.add_argument("--json", metavar="PATH", help="write the full report as JSON")
    args = parser.parse_args()

    models = [Path(p) for p in args.model]
    if args.dir:
        models.extend(sorted(Path(args.dir).glob("*.mdl")))
    if not models:
        parser.error("one of --model or --dir with *.mdl files is required")
    for model in models:
        if not model.is_file():
            print(f"[FAIL] missing model: {model}")
            return 1

    rows = [measure_model(model) for model in models]
    print_table(rows)
    measured = [row for row in rows if row["status"] == "OK"]
    counts = {label: sum(1 for row in measured if row["confidence"] == label)
              for label in ("HIGH", "MEDIUM", "LOW")}
    rear_missing = sum(1 for row in rows if row["status"] == "NO_REAR_ANCHOR")
    skipped = sum(1 for row in rows if row["status"] == "SKIP")
    print(f"measured {len(measured)}/{len(rows)}  HIGH={counts['HIGH']} "
          f"MEDIUM={counts['MEDIUM']} LOW={counts['LOW']} "
          f"NO_REAR_ANCHOR={rear_missing} SKIP={skipped}")

    if args.json:
        payload = {
            "method": "bone_positions_only_no_mesh_pca",
            "space": "skeleton_model_space",
            "models": {row["model"]: row for row in rows},
            "summary": {"total": len(rows), "measured": len(measured),
                        "confidence": counts, "no_rear_anchor": rear_missing,
                        "skipped": skipped}}
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"[json] {out}")

    return 0 if measured else 1


if __name__ == "__main__":
    sys.exit(main())
