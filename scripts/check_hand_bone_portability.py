#!/usr/bin/env python3
"""Static portability check for hand bone semantics across game directories.

Scans viewmodel MDLs in valve, gearbox and bshift, reads the bone table, and
reports which hand/finger slots the semantic resolver can identify. No runtime
and no file writes outside out/qa/A3/latest.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "out/qa/A3/latest/gate2/hand_bone_portability.json"

# Slot order mirrors ref/gl_vr/gl_studio.c.
SLOTS = [
    "hand", "palm", "thumb0", "thumb1", "thumb2",
    "index0", "index1", "index2", "middle0", "middle1", "middle2",
    "ring0", "ring1", "ring2", "pinky0", "pinky1", "pinky2",
]


def ends_with(text: str, suffix: str) -> bool:
    return text.endswith(suffix)


def semantic(name: str):
    side = -1
    slot = -1
    if " R " in name:
        side = 0
    elif " L " in name:
        side = 1

    legacy = {
        "Bone09": (0, "hand"), "Bone24": (1, "hand"),
        "Bone27": (0, "thumb0"), "Bone28": (0, "thumb1"), "Bone29": (0, "thumb2"),
        "Bone31": (0, "index0"), "Bone32": (0, "index1"), "Bone33": (0, "index2"),
        "Bone35": (0, "middle0"), "Bone36": (0, "middle1"), "Bone37": (0, "middle2"),
        "Bone39": (0, "ring0"), "Bone40": (0, "ring1"), "Bone41": (0, "ring2"),
        "Bone43": (0, "pinky0"), "Bone44": (0, "pinky1"), "Bone45": (0, "pinky2"),
    }
    if name in legacy:
        side, slot_name = legacy[name]
        slot = SLOTS.index(slot_name)
    elif "Palm" in name:
        slot = SLOTS.index("palm")
    elif "Hand" in name:
        slot = SLOTS.index("hand")
    else:
        for finger, base in (("Finger0", "thumb"), ("Finger1", "index"),
                             ("Finger2", "middle"), ("Finger3", "ring"),
                             ("Finger4", "pinky")):
            if finger in name:
                if ends_with(name, "02"):
                    slot = SLOTS.index(base + "2")
                elif ends_with(name, "01"):
                    slot = SLOTS.index(base + "1")
                else:
                    slot = SLOTS.index(base + "0")
                break

    if side < 0 or slot < 0:
        return None
    return side, slot


def read_bones(path: Path):
    data = path.read_bytes()
    if len(data) < 160 or data[:4] != b"IDST":
        return []
    numbones = struct.unpack_from("<i", data, 140)[0]
    boneindex = struct.unpack_from("<i", data, 144)[0]
    if not (0 < numbones < 256 and 0 < boneindex < len(data)):
        return []
    bones = []
    for i in range(numbones):
        off = boneindex + i * 112
        if off + 112 > len(data):
            break
        raw = data[off:off + 32].split(b"\0")[0]
        bones.append(raw.decode("latin1", errors="replace"))
    return bones


def scan_model(path: Path):
    bones = read_bones(path)
    found = {}
    for name in bones:
        mapped = semantic(name)
        if mapped is None:
            continue
        side, slot = mapped
        found.setdefault(side, set()).add(SLOTS[slot])

    try:
        model_name = str(path.relative_to(REPO))
    except ValueError:
        model_name = path.name
    result = {
        "model": model_name,
        "bones": len(bones),
        "right": sorted(found.get(0, set())),
        "left": sorted(found.get(1, set())),
    }
    result["right_hand"] = "hand" in result["right"]
    result["left_hand"] = "hand" in result["left"]
    result["right_fingers"] = all(s in result["right"] for s in ("index0", "middle0", "ring0", "pinky0"))
    result["left_fingers"] = all(s in result["left"] for s in ("index0", "middle0", "ring0", "pinky0"))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-root", help="Half-Life install root (default: sibling of valve symlink)")
    args = parser.parse_args()

    if args.game_root:
        root = Path(args.game_root)
    else:
        valve = (REPO / "valve").resolve()
        root = valve.parent

    results = []
    for game in ("valve", "gearbox", "bshift"):
        models = root / game / "models"
        if not models.is_dir():
            continue
        for path in sorted(models.glob("v_*.mdl")):
            results.append(scan_model(path))

    overlay = REPO / "assets/valve_vr/models"
    if overlay.is_dir():
        for path in sorted(overlay.glob("v_*.mdl")):
            results.append(scan_model(path))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    print(f"{'game/model':58} bones  R-hand  L-hand  R-fingers  L-fingers")
    for row in results:
        if not (row["right_hand"] or row["left_hand"]):
            continue
        print(f"{row['model'][:58]:58} {row['bones']:5}  "
              f"{str(row['right_hand']):6}  {str(row['left_hand']):6}  "
              f"{str(row['right_fingers']):9}  {str(row['left_fingers']):9}")
    print(f"\nWrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
