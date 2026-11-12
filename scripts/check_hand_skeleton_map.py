#!/usr/bin/env python3
"""Map a hand-skeleton joint standard onto the shipped ``v_hand.mdl`` rig.

The PRIMARY reference is the OpenXR ``XR_EXT_hand_tracking`` default joint set,
``XrHandJointEXT`` (26 joints), because the target device is a Meta Quest 3 and
its hand input is OpenXR-only. The OpenVR 31-bone enum is kept as a SECONDARY
semantic guide for bone names and indices only: ``v_hand.mdl`` carries its own
``Bip01 ...`` naming and this project has no OpenVR runtime dependency.

Neither standard is consumed by the engine yet: the shipped hands are baked
viewmodel geometry plus procedural curl, so this script performs no runtime
integration. It never calls the engine, reads a log, links a library or adds a
dependency. It only reports which rig bone answers each joint slot so a later
stage can align names and indices without a re-skin.

The rig has one shared ``Bip01`` root plus 17 bones per hand. The thumb has two
phalanges (``Finger0``, ``Finger01``) and the other four fingers have three
(``Finger1``, ``Finger11``, ``Finger12``, ...). ``Palm`` is the palm socket and
``Hand`` is the wrist joint, so the OpenXR 26-joint set leaves the metacarpal,
tip and second thumb-distal slots unmapped rather than inventing bones."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from check_weapon_bore import MDLDEC, find_bone, parse_nodes_and_skeleton  # noqa: E402

HAND_LETTER = {"right": "R", "left": "L"}

# OpenVR semantic guide: guide name -> MDL digit slot.
FINGERS = (("IndexFinger", "1"), ("MiddleFinger", "2"),
           ("RingFinger", "3"), ("PinkyFinger", "4"))
AUX_BONES = ("Aux_Thumb", "Aux_IndexFinger", "Aux_MiddleFinger",
             "Aux_RingFinger", "Aux_PinkyFinger")

XR_JOINT_COUNT = 26
OPENVR_JOINT_COUNT = 31

# OpenXR XrHandJointEXT suffixes after the joint prefix, with the MDL phalanx
# slot each one answers. A negative slot means the rig cannot answer the joint:
# there is no metacarpal bone, no tip bone, and the thumb stops after two bones.
FINGER_SUFFIXES = (("METACARPAL", -1), ("PROXIMAL", 0),
                   ("INTERMEDIATE", 1), ("DISTAL", 2), ("TIP", -1))
# The thumb has no INTERMEDIATE joint; its two MDL bones answer METACARPAL
# (Finger0) and PROXIMAL (Finger01).
THUMB_SUFFIXES = (("METACARPAL", 0), ("PROXIMAL", 1),
                  ("DISTAL", -1), ("TIP", -1))

# OpenXR XrHandJointEXT: joint-name prefix -> (MDL digit slot, suffix table).
XR_FINGERS = (("THUMB", "0", THUMB_SUFFIXES),
              ("INDEX", "1", FINGER_SUFFIXES),
              ("MIDDLE", "2", FINGER_SUFFIXES),
              ("RING", "3", FINGER_SUFFIXES),
              ("LITTLE", "4", FINGER_SUFFIXES))


def openvr_entries(hand: str) -> list[tuple[str, str | None]]:
    """Return ``(guide name, MDL bone name or None)`` in OpenVR enum order."""
    letter = HAND_LETTER[hand]
    entries: list[tuple[str, str | None]] = [
        ("Root", "Bip01"),
        ("Wrist", f"Bip01 {letter} Hand"),
        ("Thumb0", f"Bip01 {letter} Finger0"),
        ("Thumb1", f"Bip01 {letter} Finger01"),
        # The MDL thumb stops after two phalanges.
        ("Thumb2", None),
        ("Thumb3", None),
    ]
    for guide, digit in FINGERS:
        for slot in range(5):
            suffix = "" if slot == 0 else f"{slot}"
            bone = f"Bip01 {letter} Finger{digit}{suffix}" if slot < 3 else None
            entries.append((f"{guide}{slot}", bone))
    entries.extend((name, None) for name in AUX_BONES)
    return entries


def openxr_entries(hand: str) -> list[tuple[str, str | None]]:
    """Return ``(joint name, MDL bone name or None)`` in XrHandJointEXT order."""
    letter = HAND_LETTER[hand]
    entries: list[tuple[str, str | None]] = [
        ("PALM", f"Bip01 {letter} Palm"),
        ("WRIST", f"Bip01 {letter} Hand"),
    ]
    for prefix, digit, suffixes in XR_FINGERS:
        for suffix, slot in suffixes:
            bone = None
            if slot >= 0:
                bone = f"Bip01 {letter} Finger{digit}{'' if slot == 0 else slot}"
            entries.append((f"{prefix}_{suffix}", bone))
    return entries


def guide_entries(hand: str, standard: str = "openxr") -> list[tuple[str, str | None]]:
    """Return ``(guide name, MDL bone name or None)`` for ``standard``."""
    if standard == "openvr":
        return openvr_entries(hand)
    return openxr_entries(hand)


def build_map(nodes: dict[int, str], hand: str, standard: str = "openxr") -> dict[str, dict]:
    """Return ``{guide name: {"bone": str|None, "index": int|None}}``."""
    mapping = {}
    for guide, bone in guide_entries(hand, standard):
        index = find_bone(nodes, bone) if bone is not None else -1
        mapping[guide] = {"bone": bone, "index": index if index >= 0 else None}
    return mapping


def summarise(nodes: dict[int, str], hand: str, mapping: dict[str, dict],
              standard: str = "openxr") -> dict:
    """Return counts for one hand plus the per-finger mapped-joint tally."""
    letter = HAND_LETTER[hand]
    indices = [v["index"] for v in mapping.values() if v["index"] is not None]
    phalanges = {}
    if standard == "openvr":
        phalanges["Thumb"] = sum(1 for g in mapping if g.startswith("Thumb")
                                 and mapping[g]["index"] is not None)
        for guide, _digit in FINGERS:
            phalanges[guide] = sum(1 for slot in range(5)
                                   if mapping[f"{guide}{slot}"]["index"] is not None)
    else:
        for prefix, _digit, suffixes in XR_FINGERS:
            names = [f"{prefix}_{suffix}" for suffix, _slot in suffixes]
            phalanges[prefix.title()] = sum(1 for name in names
                                            if mapping[name]["index"] is not None)
    return {
        "hand": hand,
        "standard": standard,
        "joint_count": OPENVR_JOINT_COUNT if standard == "openvr" else XR_JOINT_COUNT,
        "total_entries": len(mapping),
        "mapped": len(indices),
        "unmapped": len(mapping) - len(indices),
        "duplicate_indices": len(indices) - len(set(indices)),
        "mdl_bones_per_hand": sum(1 for n in nodes.values() if f" {letter} " in n),
        "mapped_joints_per_finger": phalanges,
    }


def check(hand: str, mapping: dict[str, dict], summary: dict,
          standard: str = "openxr") -> bool:
    """Return True when the map is unique, anchored and phalanx-complete."""
    ok = True
    if summary["duplicate_indices"] != 0:
        print(f"[FAIL] {hand}: {summary['duplicate_indices']} duplicate index/indices")
        ok = False
    anchors = ("PALM", "WRIST") if standard == "openxr" else ("Root", "Wrist")
    for anchor in anchors:
        if mapping[anchor]["index"] is None:
            print(f"[FAIL] {hand}: {anchor} is unmapped")
            ok = False
    for guide, count in summary["mapped_joints_per_finger"].items():
        if count < 2:
            print(f"[FAIL] {hand}: {guide} maps only {count} joint/joints")
            ok = False
    return ok


def decompile(mdl_path: Path) -> dict[int, str]:
    """Decompile ``mdl_path`` into a temporary directory and return its bones."""
    if not mdl_path.is_file():
        raise RuntimeError(f"missing model: {mdl_path.relative_to(REPO_ROOT)}")
    with tempfile.TemporaryDirectory(prefix="handmap_") as tmp:
        try:
            subprocess.run([str(MDLDEC), str(mdl_path), tmp], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("mdldec failed")
        for candidate in sorted(Path(tmp).glob("*.smd")):
            nodes, _parent, _local = parse_nodes_and_skeleton(candidate)
            if nodes:
                return nodes
    raise RuntimeError("no SMD with a nodes block")


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="assets/valve_vr/models/v_hand.mdl",
                        help="model to inspect (relative to repo root)")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the mapping as JSON to PATH")
    parser.add_argument("--hand", choices=("right", "left", "both"), default="right",
                        help="hand to map (default: right)")
    parser.add_argument("--standard", choices=("openxr", "openvr"), default="openxr",
                        help="joint standard to map (default: openxr)")
    args = parser.parse_args()

    model = resolve(args.model)
    try:
        nodes = decompile(model)
    except RuntimeError as exc:
        print(f"[FAIL] {exc}")
        return 1

    hands = ["right", "left"] if args.hand == "both" else [args.hand]
    joint_count = OPENVR_JOINT_COUNT if args.standard == "openvr" else XR_JOINT_COUNT
    payload: dict[str, object] = {
        "runtime": "openxr", "openvr_is_guide_only": True,
        "standard": args.standard, "joint_count": joint_count,
        "model": str(model.relative_to(REPO_ROOT)), "hand": args.hand,
    }
    if args.standard == "openxr":
        # XR_EXT_hand_tracking is not consumed yet: the shipped hands are baked
        # viewmodel geometry with a procedural curl, so the joint set is only a
        # naming/index reference until a later stage wires the extension up.
        payload["xr_ext_hand_tracking_consumed"] = False
        payload["xr_ext_hand_tracking_note"] = (
            "not consumed: hands are baked plus procedural curl today")
    ok = True
    summaries = {}
    for hand in hands:
        mapping = build_map(nodes, hand, args.standard)
        summary = summaries[hand] = summarise(nodes, hand, mapping, args.standard)
        payload[hand] = mapping
        print(f"== {hand} hand ({payload['model']}, {args.standard} "
              f"{joint_count} joints) ==")
        print(f"{'guide name':22s} {'MDL bone':24s} index\n{'-' * 60}")
        for guide, entry in mapping.items():
            bone = entry["bone"] or "-"
            index = "-" if entry["index"] is None else str(entry["index"])
            print(f"{guide:22s} {bone:24s} {index}")
        print("-" * 60)
        print(f"entries={summary['total_entries']} mapped={summary['mapped']} "
              f"unmapped={summary['unmapped']} "
              f"duplicate_indices={summary['duplicate_indices']} "
              f"mdl_bones_per_hand={summary['mdl_bones_per_hand']}")
        if not check(hand, mapping, summary, args.standard):
            ok = False

    payload["summary"] = summaries
    print(f"[{'PASS' if ok else 'FAIL'}] {args.standard} guide map, OpenXR runtime; "
          "no OpenVR dependency")
    if args.json is not None:
        out_path = resolve(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
