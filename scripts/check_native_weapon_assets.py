#!/usr/bin/env python3
"""Check the native weapon overlay against the legacy models it replaces.

The client resolves a native viewmodel as ``models/native/<legacy-basename>.mdl``
(see ``engine/client/cl_view.c``). Because Android and Linux are case-sensitive,
a file whose name differs from the HLSDK request only by case is silently
ignored and the legacy model is used instead.

This is a static contract check, not a gate:

* every native file must be named exactly like the legacy basename;
* the MDL must be a GoldSrc v10 studio model;
* attachments 0..3 must be ``muzzle_pos``, ``muzzle_pos2``, ``hud_pos`` and
  ``hud_pos2`` in that order, because the weapon profile and the aim code index
  them by number;
* the sequence table must match the legacy model name-for-name and in order,
  because the game DLL sends sequence indices, not names;
* the profile must not point eject/magwell sockets at HUD anchors.

Usage:
    python3 scripts/check_native_weapon_assets.py
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_DIR / "assets" / "valve_vr" / "models"
NATIVE_DIR = MODEL_DIR / "native"
PROFILE_PATH = MODEL_DIR / "vr_weapons.json"

# Offsets inside a GoldSrc v10 studio header.
NUM_BONES = 140
BONE_INDEX = 144
NUM_SEQ = 164
SEQ_INDEX = 168
NUM_ATTACHMENTS = 212
ATTACHMENT_INDEX = 216

BONE_SIZE = 112
SEQ_SIZE = 176
ATTACHMENT_SIZE = 88
ATTACHMENT_BONE_OFFSET = 36

EXPECTED_ANCHORS = ["muzzle_pos", "muzzle_pos2", "hud_pos", "hud_pos2"]

# Anchor bone names that can seat the weapon in the palm. The renderer tries
# them in this order (ref/gl_vr/gl_studio.c, R_VR_AnchorViewmodelToGrip).
GRIP_ANCHORS = ["Bip01 R Hand", "Xbow biped R Hand", "Bone09", "Bip01 L Hand", "grip"]

# Sequence roles. The game DLL sends indices, not names, so a rename is safe as
# long as the role at each index is preserved.
SUFFIXES = ("_vanilla", "_orig", "_hl")


def sequence_role(name: str) -> str:
    lowered = name.lower()
    for suffix in SUFFIXES:
        if lowered.endswith(suffix):
            lowered = lowered[: -len(suffix)]
    if "reload" in lowered:
        return "reload"
    if "shoot" in lowered or "fire" in lowered:
        return "fire"
    if "draw" in lowered or "deploy" in lowered:
        return "draw"
    if "holster" in lowered:
        return "holster"
    if "idle" in lowered or "fidget" in lowered:
        return "idle"
    if "throw" in lowered or lowered in ("up", "down"):
        return "toss"
    if "grenade" in lowered:
        return "grenade"
    return "other"


def int32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def cstring(data: bytes, offset: int) -> str:
    end = data.find(b"\0", offset)
    if end < 0:
        return ""
    return data[offset:end].decode("latin-1")


def read_model(path: Path) -> dict:
    data = path.read_bytes()
    if data[:4] != b"IDST":
        raise ValueError(f"{path.name}: not a studio model")

    version = int32(data, 4)
    if version != 10:
        raise ValueError(f"{path.name}: version {version}, expected 10 (GoldSrc)")

    bones = []
    for i in range(int32(data, NUM_BONES)):
        bones.append(cstring(data, int32(data, BONE_INDEX) + i * BONE_SIZE))

    sequences = []
    for i in range(int32(data, NUM_SEQ)):
        sequences.append(cstring(data, int32(data, SEQ_INDEX) + i * SEQ_SIZE))

    attachments = []
    for i in range(int32(data, NUM_ATTACHMENTS)):
        entry = int32(data, ATTACHMENT_INDEX) + i * ATTACHMENT_SIZE
        bone = int32(data, entry + ATTACHMENT_BONE_OFFSET)
        name = cstring(data, entry)
        if not name and 0 <= bone < len(bones):
            name = bones[bone]
        attachments.append({"name": name, "bone": bone})

    return {
        "version": version,
        "bones": bones,
        "sequences": sequences,
        "attachments": attachments,
    }


def main() -> int:
    profiles = json.loads(PROFILE_PATH.read_text())["weapons"]
    legacy_names = {name for name in profiles if name != "v_hand.mdl"}

    failures: list[str] = []
    warnings: list[str] = []
    rows: list[tuple[str, str, str, str]] = []

    native_files = {path.name for path in NATIVE_DIR.glob("*.mdl")} if NATIVE_DIR.is_dir() else set()
    if not native_files:
        print(f"[FAIL] no native models under {NATIVE_DIR.relative_to(REPO_DIR)}")
        return 1

    for name in sorted(native_files - legacy_names):
        failures.append(f"native/{name}: no legacy profile entry with that exact name")

    for name in sorted(legacy_names & native_files):
        native_path = NATIVE_DIR / name
        legacy_path = MODEL_DIR / name
        profile = profiles[name]

        if not legacy_path.is_file():
            failures.append(f"{name}: native model has no legacy counterpart on disk")
            continue

        try:
            native = read_model(native_path)
            legacy = read_model(legacy_path)
        except ValueError as error:
            failures.append(str(error))
            continue

        anchors = [item["name"].lower() for item in native["attachments"]]
        anchor_bones = [item["bone"] for item in native["attachments"]]
        if anchor_bones[0] == anchor_bones[1]:
            failures.append(
                f"{name}: muzzle_pos and muzzle_pos2 share bone {anchor_bones[0]}"
            )
        if set(anchor_bones[:2]) & set(anchor_bones[2:]):
            failures.append(
                f"{name}: muzzle anchors share a bone with a HUD anchor ({anchor_bones})"
            )
        if any(bone < 0 or bone >= len(native["bones"]) for bone in anchor_bones):
            failures.append(f"{name}: attachment bone index out of range ({anchor_bones})")
        if anchors[:2] != ["muzzle_pos", "muzzle_pos2"] or not (
            anchors[2].startswith("hud") and anchors[3].startswith("hud")
        ):
            failures.append(
                f"{name}: attachments {anchors}, expected muzzle_pos, muzzle_pos2, "
                "hud_pos, hud_pos2 in that order"
            )
        elif anchors != EXPECTED_ANCHORS and name != "v_hgun.mdl":
            warnings.append(f"{name}: HUD anchors are {anchors[2:]}")

        legacy_sequences = legacy["sequences"]
        native_sequences = native["sequences"]
        shared = min(len(legacy_sequences), len(native_sequences))
        for index in range(shared):
            role = sequence_role(legacy_sequences[index])
            native_role = sequence_role(native_sequences[index])
            if role != native_role:
                failures.append(
                    f"{name}: sequence {index} is {legacy_sequences[index]!r} "
                    f"({role}) in the legacy model but {native_sequences[index]!r} "
                    f"({native_role}) in the native one"
                )
        for index in range(shared, len(legacy_sequences)):
            role = sequence_role(legacy_sequences[index])
            if role != "idle":
                failures.append(
                    f"{name}: native model is missing legacy sequence {index} "
                    f"({legacy_sequences[index]!r}, {role})"
                )
            else:
                warnings.append(
                    f"{name}: trailing {role} sequence {legacy_sequences[index]!r} "
                    "is not present in the native model"
                )

        if profile.get("muzzle_attachment") not in (0, -1):
            failures.append(
                f"{name}: muzzle_attachment {profile.get('muzzle_attachment')} "
                "is not 0 (muzzle_pos) or -1 (no muzzle)"
            )

        for field in ("ejection_attachment", "magwell_attachment"):
            if profile.get(field, -1) != -1:
                failures.append(
                    f"{name}: {field} is {profile.get(field)}, but attachment 2/3 "
                    "are HUD anchors on the native model"
                )

        grip = next((bone for bone in GRIP_ANCHORS if bone in native["bones"]), None)
        if grip is None:
            warnings.append(f"{name}: no palm anchor bone; falls back to grip_offset")

        rows.append(
            (
                name,
                f"{len(native['bones'])}",
                f"{len(native['sequences'])}",
                grip or "offset",
            )
        )

    print(f"{'model':<22} {'bones':>5} {'seqs':>5}  grip anchor")
    for row in rows:
        print(f"{row[0]:<22} {row[1]:>5} {row[2]:>5}  {row[3]}")

    for message in warnings:
        print(f"[warn] {message}")
    for message in failures:
        print(f"[FAIL] {message}")

    if failures:
        print(f"[FAIL] {len(failures)} native weapon contract violation(s)")
        return 1

    print(f"[PASS] {len(rows)}/{len(legacy_names)} native viewmodels match the contract")
    return 0


if __name__ == "__main__":
    sys.exit(main())
