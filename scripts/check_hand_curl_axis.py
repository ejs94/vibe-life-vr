#!/usr/bin/env python3
"""Measure the finger curl axis of the standalone hand MDL's rest bones.

This is an asset diagnostic: it decompiles the MDL and inspects the bone
rest frames. It never calls the engine and does not grep logs.
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

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from check_weapon_bore import (  # noqa: E402
    MDLDEC,
    bone_frames,
    find_bone,
    parse_nodes_and_skeleton,
    unit,
)

def _cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]

def _dot(a, b):
    return sum(a[k] * b[k] for k in range(3))

def _resolve(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p

def measure(mdl_path: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="handcurl_") as tmp:
        out_dir = Path(tmp)
        try:
            subprocess.run(
                [str(MDLDEC), str(mdl_path), str(out_dir)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("mdldec failed")
        smd_path = None
        for candidate in sorted(out_dir.glob("*.smd")):
            nodes, _, _ = parse_nodes_and_skeleton(candidate)
            if nodes:
                smd_path = candidate
                break
        if smd_path is None:
            raise RuntimeError("no SMD with nodes block")
        nodes, parent, local = parse_nodes_and_skeleton(smd_path)
        rotations, positions = bone_frames(nodes, parent, local)
        def idx(name):
            i = find_bone(nodes, name)
            if i < 0:
                raise RuntimeError(f"missing bone: {name}")
            return i
        finger = unit([positions[idx("Bip01 R Finger12")][k] - positions[idx("Bip01 R Finger1")][k] for k in range(3)])
        thumb = unit([positions[idx("Bip01 R Finger01")][k] - positions[idx("Bip01 R Finger0")][k] for k in range(3)])
        if finger is None or thumb is None:
            raise RuntimeError("degenerate finger/thumb vector")
        palm_normal = unit(_cross(finger, thumb))
        if palm_normal is None:
            raise RuntimeError("degenerate palm normal")
        curl_world = unit(_cross(finger, palm_normal))
        if curl_world is None:
            raise RuntimeError("degenerate curl axis")
        bones = ["Bip01 R Finger1", "Bip01 R Finger11"]
        result = {}
        for bone in bones:
            r = rotations[idx(bone)]
            # local axes are the columns of R
            axes = [[r[row][k] for row in range(3)] for k in range(3)]
            vals = [abs(_dot(ax, curl_world)) for ax in axes]
            result[bone] = {
                "aX": vals[0],
                "aY": vals[1],
                "aZ": vals[2],
            }
    return {
        "bones": result,
        "curl_world": curl_world,
        "finger": finger,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="assets/valve_vr/models/v_hand.mdl",
                        help="path to v_hand.mdl (relative to repo root)")
    parser.add_argument("--legacy-y", action="store_true",
                        help="invert expectation: require local Y (negative control)")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="dump JSON result to PATH")
    args = parser.parse_args()
    mdl_path = _resolve(args.model)
    if not mdl_path.is_file():
        print(f"[FAIL] missing model: {mdl_path}")
        return 1
    try:
        data = measure(mdl_path)
    except RuntimeError as exc:
        print(f"[FAIL] {exc}")
        return 1
    bones = data["bones"]
    curl_world = data["curl_world"]
    finger = data["finger"]
    print(f"{'bone':24s} {'aX':>8s} {'aY':>8s} {'aZ':>8s}")
    print("-" * 48)
    ok = True
    for bone in ("Bip01 R Finger1", "Bip01 R Finger11"):
        v = bones[bone]
        print(f"{bone:24s} {v['aX']:8.4f} {v['aY']:8.4f} {v['aZ']:8.4f}")
        if args.legacy_y:
            if not (v["aY"] >= 0.9):
                ok = False
        else:
            if not (v["aZ"] >= 0.9 and v["aY"] <= 0.2 and v["aX"] <= 0.2):
                ok = False
    print("-" * 48)
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] curl axis is {'local Y (legacy)' if args.legacy_y else 'local Z'}")
    if args.json is not None:
        payload = {}
        for bone, v in bones.items():
            payload[bone] = {"aX": v["aX"], "aY": v["aY"], "aZ": v["aZ"]}
        payload["curl_world"] = curl_world
        payload["finger"] = finger
        payload["status"] = status
        out_path = _resolve(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
PY