#!/usr/bin/env python3
"""Check overlay viewmodel filenames against the names the HLSDK requests.

The engine loads viewmodels by the exact path string used by the game DLL
(for example ``models/v_9mmAR.mdl``). On Android/Linux the filesystem is
case-sensitive, so a bundled ``v_9mmar.mdl`` does not satisfy a request for
``v_9mmAR.mdl``. When that happens the vanilla model loads instead and the
MMOD asset silently stops being used.

This gate fails when an overlay model matches a requested name only
case-insensitively but not exactly, or when a bundled model has no matching
HLSDK request at all. Missing overlay models are reported as a warning because
the vanilla fallback is a supported state.

Usage:
    python3 scripts/check_viewmodel_names.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
HLSDK_DIRS = [
    REPO_DIR / "3rdparty" / "hlsdk-portable" / "dlls",
    REPO_DIR / "3rdparty" / "hlsdk-portable" / "cl_dll",
]
OVERLAY_DIR = REPO_DIR / "assets" / "valve_vr" / "models"
# The native route resolves models/native/<legacy-basename>.mdl, so a native
# file is subject to the same exact-case rule as the overlay it replaces.
OVERLAY_DIRS = [OVERLAY_DIR, OVERLAY_DIR / "native"]

MODEL_RE = re.compile(r"models/v_[A-Za-z0-9_]+\.mdl", re.I)


def requested_names() -> set[str]:
    names: set[str] = set()
    for directory in HLSDK_DIRS:
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.suffix.lower() not in {".cpp", ".c", ".h"}:
                continue
            text = path.read_text(encoding="latin1", errors="replace")
            for match in MODEL_RE.findall(text):
                names.add(match.rsplit("/", 1)[-1])
    return names


def main() -> int:
    requested = requested_names()
    if not requested:
        print("[FAIL] no HLSDK viewmodel requests found")
        return 1

    bundled_by_dir = {
        directory: {path.name for path in directory.glob("*.mdl")}
        for directory in OVERLAY_DIRS
        if directory.is_dir()
    }
    bundled = set().union(*bundled_by_dir.values()) if bundled_by_dir else set()
    requested_lower = {name.lower(): name for name in requested}

    failures: list[str] = []
    warnings: list[str] = []

    for directory, names in bundled_by_dir.items():
        folder = directory.relative_to(REPO_DIR).as_posix()
        for name in sorted(names):
            if name in requested:
                continue
            canonical = requested_lower.get(name.lower())
            if canonical:
                failures.append(
                    f"{folder}/{name}: case mismatch; the HLSDK requests {canonical}"
                )
            else:
                warnings.append(f"{folder}/{name}: bundled but not requested by the HLSDK")

    for name in sorted(requested):
        if name not in bundled:
            warnings.append(f"{name}: not bundled (vanilla fallback will be used)")

    print(f"[gate] HLSDK requests: {len(requested)}")
    print(f"[gate] overlay models: {len(bundled)}")

    for message in warnings:
        print(f"[warn] {message}")
    for message in failures:
        print(f"[FAIL] {message}")

    if failures:
        return 1

    print("[gate] all bundled viewmodel names match the HLSDK exactly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
