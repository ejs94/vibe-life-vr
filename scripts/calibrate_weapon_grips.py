#!/usr/bin/env python3
"""Procedurally calibrate weapon grip sockets from vr_grip_probe telemetry.

The probe emits the animated grip bone in weapon-local coordinates and a signed
``err=(x y z)`` vector. For the Valve/M MOD viewmodels the palm anchor sits ten
units forward of the wrist, so the socket is:

    grip_offset = [10 - local_x, local_y, -local_z]

This script reads one or more engine logs, picks an idle sample per model, and
optionally writes the values into ``vr_weapons.json`` without touching the other
profile fields. It also derives the crossbow foregrip from the ``grip`` landmark
when ``vr_grip_probe 2`` telemetry is present.

Usage:
    python3 scripts/calibrate_weapon_grips.py engine.log [--write]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

GRIP_RE = re.compile(
    r"\[VR_GRIP_BONE\] model=(\S+) bone=(.+?) seq=(\d+) label=(\S*)"
)
MODEL_RE = re.compile(r"\smodel=\(([-\d.]+) ([-\d.]+) ([-\d.]+)\)")
LANDMARK_RE = re.compile(
    r"\[VR_GRIP_BONES\] model=(\S+) bone=(.+?) seq=(\d+) label=(\S*)"
)
DEFAULT_JSON = Path("assets/valve_vr/models/vr_weapons.json")


def parse_log(path: Path):
    grips: dict[str, tuple[str, tuple[float, float, float]]] = {}
    landmarks: dict[tuple[str, str], tuple[str, tuple[float, float, float]]] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        grip = GRIP_RE.search(raw)
        if grip:
            model, bone, seq, label = grip.groups()
            loc = MODEL_RE.search(raw)
            if not loc:
                continue
            value = tuple(float(loc.group(i)) for i in (1, 2, 3))
            previous = grips.get(model)
            # Prefer an idle/rest sample; otherwise keep the last sample.
            if previous is None or ("idle" in label.lower() and "idle" not in previous[0].lower()):
                grips[model] = (label, value)
            continue
        landmark = LANDMARK_RE.search(raw)
        if landmark:
            model, bone, seq, label = landmark.groups()
            loc = MODEL_RE.search(raw)
            if not loc:
                continue
            value = tuple(float(loc.group(i)) for i in (1, 2, 3))
            key = (model, bone)
            previous = landmarks.get(key)
            if previous is None or ("idle" in label.lower() and "idle" not in previous[0].lower()):
                landmarks[key] = (label, value)
    return grips, landmarks


def model_key(model: str, weapons: dict):
    base = model.rsplit("/", 1)[-1].lower()
    for key in weapons:
        if key.lower() == base:
            return key
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+", type=Path)
    ap.add_argument("--json", type=Path, default=DEFAULT_JSON)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    grips = {}
    landmarks = {}
    for path in args.logs:
        g, l = parse_log(path)
        for model, value in g.items():
            if model not in grips or "idle" in value[0].lower():
                grips[model] = value
        for key, value in l.items():
            if key not in landmarks or "idle" in value[0].lower():
                landmarks[key] = value

    if not grips:
        print("error: no [VR_GRIP_BONE] samples found", file=sys.stderr)
        return 1

    data = json.loads(args.json.read_text(encoding="utf-8"))
    weapons = data.get("weapons", {})
    changes = []
    missing = []
    for model, (label, (x, y, z)) in sorted(grips.items()):
        key = model_key(model, weapons)
        if not key:
            missing.append(model)
            continue
        offset = [round(10.0 - x, 3), round(y, 3), round(-z, 3)]
        weapons[key]["grip_offset"] = offset
        changes.append((key, label, offset))

    for (model, bone), (label, (x, y, z)) in landmarks.items():
        if bone.lower() != "grip" or "crossbow" not in model.lower():
            continue
        key = model_key(model, weapons)
        if key:
            weapons[key]["foregrip_offset"] = [round(x, 3), round(-y, 3), round(z, 3)]
            changes.append((key + " foregrip", label, weapons[key]["foregrip_offset"]))

    for name, label, offset in changes:
        print(f"{name:28s} {label:10s} -> [{offset[0]:.3f}, {offset[1]:.3f}, {offset[2]:.3f}]")
    if missing:
        print("warning: no profile for: " + ", ".join(missing), file=sys.stderr)

    if args.write:
        # Keep numeric arrays compact so the manifest stays reviewable.
        def fmt(value, indent=0):
            space = "  " * indent
            if isinstance(value, dict):
                body = ",\n".join(
                    "  " * (indent + 1) + json.dumps(k) + ": " + fmt(v, indent + 1)
                    for k, v in value.items()
                )
                return "{\n" + body + "\n" + space + "}"
            if isinstance(value, list):
                if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
                    return "[" + ", ".join(json.dumps(v) for v in value) + "]"
                if all(isinstance(v, str) for v in value):
                    return "[" + ", ".join(json.dumps(v) for v in value) + "]"
                body = ",\n".join("  " * (indent + 1) + fmt(v, indent + 1) for v in value)
                return "[\n" + body + "\n" + space + "]"
            return json.dumps(value, ensure_ascii=False)

        args.json.write_text(fmt(data) + "\n", encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
