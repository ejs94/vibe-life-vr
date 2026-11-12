#!/usr/bin/env python3
"""Report the adoption state of the per-class VR-ready fallback manifest.

This is a READINESS gate, not a pass/fail acceptance gate. The manifest
(``assets/valve_vr/models/vr_fallback.json``) lists candidate viewmodels for
each weapon class; a candidate only counts as adopted when it is validated by
a labelled fixed-camera comparison sheet approved by the maintainer. Until
then this script reports PENDING and never claims the weapons work.

Usage:
    python3 scripts/check_vr_fallback.py
        [--manifest PATH] [--json PATH]
Exit 0 when the manifest is structurally valid; the adoption state is printed
separately so a green exit code can never be mistaken for "assets adopted".
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_DIR / "assets" / "valve_vr" / "models" / "vr_fallback.json"


def check_candidate(source: str, sha_prefix: str, size: int):
    """Verify a reference copy still matches the recorded checksum, if present.

    The candidates live in read-only reference repos outside this repo, so a
    missing file is reported as a warning rather than a hard failure.
    """
    path = (REPO_DIR / source).resolve()
    if not path.is_file():
        return "MISSING (reference repo not mounted)"
    data = path.read_bytes()
    if len(data) != size:
        return f"SIZE CHANGED ({len(data)} != {size})"
    if not hashlib.sha256(data).hexdigest().startswith(sha_prefix):
        return "CHECKSUM CHANGED"
    return "OK"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    p.add_argument("--json", dest="json_path", default=None)
    a = p.parse_args()

    path = Path(a.manifest)
    if not path.is_file():
        print(f"[FAIL] manifest not found: {a.manifest}")
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[FAIL] invalid JSON: {exc}")
        return 1

    classes = data.get("weapon_classes")
    if not isinstance(classes, dict) or not classes:
        print("[FAIL] manifest has no weapon_classes")
        return 1

    rows = []
    for name, entry in sorted(classes.items()):
        candidate = entry.get("candidate") or {}
        legacy = entry.get("legacy_models") or []
        source = candidate.get("source", "")
        integrity = check_candidate(
            source, candidate.get("sha256_prefix", ""), int(candidate.get("bytes", 0))
        ) if source else "NO SOURCE"
        validated = bool(candidate.get("validated"))
        rows.append({
            "class": name,
            "legacy_models": legacy,
            "validated": validated,
            "integrity": integrity,
            "validation": candidate.get("validation", ""),
        })

    adopted = [r["class"] for r in rows if r["validated"]]
    state = "ADOPTED" if adopted else "PENDING"

    print(f"{'class':<22} {'legacy':<28} {'candidate':<14} validated")
    print("-" * 78)
    for r in rows:
        print(f"{r['class']:<22} {','.join(r['legacy_models']):<28} "
              f"{r['integrity']:<14} {r['validated']}")
        if r["validation"]:
            print(f"    note: {r['validation']}")
    print()
    print(f"[FINDING] fallback adoption: {state} "
          f"({len(adopted)}/{len(rows)} classes validated)")
    print("No candidate is adopted. Engine-side model substitution is NOT implemented.")
    print("Do not read exit 0 as 'weapons work'.")

    if a.json_path:
        report = {
            "status": state,
            "manifest_status": data.get("status"),
            "human_decision": data.get("human_decision"),
            "adopted_classes": adopted,
            "classes": rows,
        }
        out = Path(a.json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
