#!/usr/bin/env python3
"""Check that generated evidence stays under the canonical out/qa root.

The project uses ``out/qa/<gate>/runs/<timestamp>/`` for gate evidence. Working
sets such as ``out/mmod_import`` and ``out/viewmodel_work`` may contain source
meshes, textures and compiled models, but not review images, audit folders,
score files or manifests. This check catches evidence that escaped the root
before it becomes permanent clutter.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = REPO_ROOT / "out"
QA_ROOT = OUT_ROOT / "qa"
SCRIPTS_ROOT = REPO_ROOT / "scripts"

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ppm"}
EVIDENCE_DIR_SUFFIXES = ("_audit", "_360")
EVIDENCE_FILE_NAMES = {
    "manifest.json",
    "result.json",
    "repair_manifest.json",
    "structure_check.json",
    "baseline_structure_check.json",
}
EVIDENCE_FILE_SUFFIXES = (
    "_holes.json",
    "_holes.csv",
    "_holes_summary.json",
    "_score.json",
    "_baseline_score.json",
    "_structure_check.json",
)


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def scan_out(errors: list[str]) -> None:
    if not OUT_ROOT.exists():
        return
    for path in OUT_ROOT.rglob("*"):
        if path == QA_ROOT or QA_ROOT in path.parents:
            continue
        if path.is_dir():
            if path.name.endswith(EVIDENCE_DIR_SUFFIXES):
                errors.append(f"evidence directory outside out/qa: {relative(path)}")
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() in IMAGE_SUFFIXES:
            errors.append(f"image outside out/qa: {relative(path)}")
        if path.name in EVIDENCE_FILE_NAMES or path.name.endswith(EVIDENCE_FILE_SUFFIXES):
            errors.append(f"evidence file outside out/qa: {relative(path)}")
        if path.name.endswith(".diff") and "baseline" in path.name.lower():
            errors.append(f"baseline diff outside out/qa: {relative(path)}")


def scan_scripts(errors: list[str]) -> None:
    if not SCRIPTS_ROOT.exists():
        return
    for path in SCRIPTS_ROOT.rglob("__pycache__"):
        if path.is_dir():
            errors.append(f"python cache under scripts: {relative(path)}")
    for path in SCRIPTS_ROOT.rglob("*.pyc"):
        errors.append(f"python bytecode under scripts: {relative(path)}")


def scan_root(errors: list[str]) -> None:
    for path in REPO_ROOT.glob("*.log"):
        if path.is_file():
            errors.append(f"loose log at repository root: {relative(path)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="reserved for future machine-readable output")
    args = parser.parse_args()

    errors: list[str] = []
    scan_out(errors)
    scan_scripts(errors)
    scan_root(errors)

    if errors:
        print("EVIDENCE HYGIENE FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("EVIDENCE HYGIENE PASSED: generated evidence is under out/qa")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
