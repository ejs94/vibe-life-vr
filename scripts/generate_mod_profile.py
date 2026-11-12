#!/usr/bin/env python3
"""Generate a Silver-tier v2 VR weapon calibration profile for one Xash3D gamedir.

The profile is DATA ONLY: it is emitted from the P2 bore ground truth and never
edits MDLs, DLLs or engine code. The engine resolves it through
``<gamedir>_vr/models/vr_weapons.json`` before the gamedir and ``valve``
defaults, so a single JSON file can calibrate a mod without touching its assets.

Every emitted entry uses the authored two-point bore basis (attachment 0 muzzle
-> attachment 2 rear anchor) the renderer aligns, keeps ``pitch_adjust`` at 0.0
and carries the measured confidence verbatim. ``UNKNOWN`` (LOW confidence) is
never promoted to a pass; it is written with ``muzzle_attachment -1`` and the
LOW string so ``V3`` keeps reporting it as ``UNKNOWN``.

Usage:
    python3 scripts/generate_mod_profile.py --ground-truth <P2 json> \
        --gamedir <id> --models-dir <dir> --out <path> [--vanilla-fallback]
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402  (import after bytecode opt-out)
import importlib.util  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
from collections import Counter  # noqa: E402
from pathlib import Path  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_URL = "https://raw.githubusercontent.com/xash3d-fwgs-vr/schemas/main/vr_weapons.schema.json"
VIEWMODEL_RE = re.compile(r"^v_[A-Za-z0-9_]+\.mdl$", re.I)
MEASURABLE = {"HIGH", "MEDIUM"}
BORE_BASIS_ATTACHMENT = 2
MUZZLE_ATTACHMENT = 0
NO_MUZZLE = -1
CONFIDENCE_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ground-truth", required=True,
                   help="P2 JSON (measure_bore_basis.py) with a models map")
    p.add_argument("--gamedir", required=True,
                   help="Target gamedir id written to the profile header")
    p.add_argument("--models-dir", required=True,
                   help="Directory holding the mod's bundled v_*.mdl files")
    p.add_argument("--out", required=True, help="Output v2 profile JSON path")
    p.add_argument("--vanilla-fallback", action="store_true",
                   help="Report HLSDK requests with no bundled model; the "
                        "engine loads the vanilla viewmodel for those")
    return p.parse_args()


def load_requested_names() -> set[str]:
    """Return the viewmodel names the HLSDK requests via check_viewmodel_names.

    P1 parses argv at import time, so argv is masked while its module loads.
    """
    path = SCRIPT_DIR / "check_viewmodel_names.py"
    if not path.is_file():
        return set()
    spec = importlib.util.spec_from_file_location("_p1_viewmodel_names", path)
    module = importlib.util.module_from_spec(spec)
    saved_argv = sys.argv
    sys.argv = [str(path)]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = saved_argv
    return module.requested_names()


def build_entry(model: str, record: dict) -> dict:
    confidence = str(record.get("confidence") or "UNKNOWN").upper()
    measurable = confidence in MEASURABLE and bool(record.get("authored_bore"))
    return {
        "name": Path(model).stem,
        "type": "hitscan",
        "muzzle_attachment": MUZZLE_ATTACHMENT if measurable else NO_MUZZLE,
        "bore_basis_attachment": BORE_BASIS_ATTACHMENT,
        "legacy_flash_pair": True,
        "bore_confidence": confidence,
        # Never emit a Euler trim: a bad bore anchor must be fixed at the asset.
        "pitch_adjust": 0.0,
    }


def main() -> int:
    args = parse_args()
    ground_truth = Path(args.ground_truth)
    if not ground_truth.is_file():
        print(f"[FAIL] missing ground truth: {args.ground_truth}")
        return 1
    data = json.loads(ground_truth.read_text(encoding="utf-8"))
    sources = {
        name: record
        for name, record in (data.get("models") or {}).items()
        if VIEWMODEL_RE.match(name)
    }
    if not sources:
        print(f"[FAIL] no v_*.mdl entries in {args.ground_truth}")
        return 1

    models_dir = Path(args.models_dir)
    if models_dir.is_dir():
        bundled = sorted(p.name for p in models_dir.glob("*.mdl")
                         if VIEWMODEL_RE.match(p.name))
    else:
        bundled = []
        print(f"[WARN] models directory not found: {args.models_dir}")

    requested = load_requested_names()
    canonical_by_lower = {name.lower(): name for name in requested}
    if not requested:
        print("[WARN] no HLSDK viewmodel requests found; case check skipped")

    weapons: dict[str, dict] = {}
    mismatches = 0
    duplicates = 0

    for model in sorted(sources):
        key = model
        canonical = canonical_by_lower.get(model.lower())
        if canonical and canonical != model:
            print(f"CASE-MISMATCH {model} -> {canonical} "
                  f"(bundled case does not satisfy the HLSDK request)")
            key = canonical
            mismatches += 1
        entry = build_entry(key, sources[model])
        previous = weapons.get(key)
        if previous is not None:
            duplicates += 1
            keep_new = (CONFIDENCE_RANK.get(entry["bore_confidence"], 0)
                        > CONFIDENCE_RANK.get(previous["bore_confidence"], 0))
            print(f"DUPLICATE {key}: keeping the "
                  f"{'newer' if keep_new else 'existing'} measurement")
            if not keep_new:
                continue
        weapons[key] = entry

    vanilla_fallbacks = 0
    if args.vanilla_fallback:
        present = {name.lower() for name in bundled}
        for name in sorted(requested):
            if name.lower() in present:
                continue
            vanilla_fallbacks += 1
            print(f"VANILLA-FALLBACK {name} missing from {args.models_dir}; "
                  f"the engine loads the vanilla model")

    profile = {
        "$schema": SCHEMA_URL,
        "version": 2,
        "gamedir": args.gamedir,
        "description": (f"Silver-tier VR weapon calibration for gamedir "
                        f"'{args.gamedir}', generated from measured authored "
                        f"bore bases (P2). Data only; never edits MDLs."),
        "weapons": weapons,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")

    counts = Counter(entry["bore_confidence"] for entry in weapons.values())
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    print(f"models found: {len(bundled)} (gamedir '{args.gamedir}')")
    print(f"entries emitted: {len(weapons)} -> {args.out}")
    print(f"case mismatches: {mismatches}")
    print(f"duplicate keys: {duplicates}")
    print(f"vanilla fallbacks: {vanilla_fallbacks}")
    print(f"confidence: {summary or 'none'}")
    return 0 if weapons else 1


if __name__ == "__main__":
    sys.exit(main())
