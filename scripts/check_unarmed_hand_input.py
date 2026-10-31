#!/usr/bin/env python3
"""Verify the unarmed hand is natural, controller-driven and not a baked grip.

Reads the Monado unit-test log and checks:
  * two or more primary [HAND_POSE] samples;
  * the hand forward vector changes between the rest and moved captures;
  * the palm is at the controller grip-pose origin (grip_dist ~ 0);
  * the open-hand model path was selected while unarmed.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

LINE_RE = re.compile(
    r"\[HAND_POSE\]\s+ent=(\w+).*?palm=\(([^)]+)\)\s+fingertip=\(([^)]+)\).*?"
    r"fwd=\(([^)]+)\)\s+up=\(([^)]+)\).*?grip_dist=([-\d.]+)"
)

PROFILE_RE = re.compile(
    r"\[VR_HAND_PROFILE\]\s+slot=primary\s+profile=(\w+)\s+unarmed=(\d+)\s+path=(\S+)"
)


def vec(text: str):
    return tuple(float(x) for x in text.split())


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_unarmed_hand_input.py <log> [output_dir]")
        return 2
    log_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    text = log_path.read_text(encoding="latin1", errors="replace")

    marker = text.find("UNARMED_HAND_TEST_BEGIN")
    if marker < 0:
        print("FAILED: unarmed test marker not found")
        return 1
    unarmed_text = text[marker:]

    samples = []
    for match in LINE_RE.finditer(unarmed_text):
        if match.group(1) != "primary":
            continue
        samples.append({
            "palm": vec(match.group(2)),
            "fwd": vec(match.group(4)),
            "grip_dist": float(match.group(6)),
        })

    failures = []
    if len(samples) < 2:
        failures.append(f"expected >=2 primary hand samples, got {len(samples)}")
    else:
        fwds = [s["fwd"] for s in samples]
        distinct = any(dot(fwds[0], f) < 0.999 for f in fwds[1:])
        if not distinct:
            failures.append("hand forward vector did not change between rest and moved captures")
        for s in samples:
            if s["grip_dist"] > 0.25:
                failures.append(f"palm is {s['grip_dist']:.3f}u from controller grip origin")

    profiles = PROFILE_RE.findall(text)
    open_profiles = [p for p in profiles if p[1] == "1" and "v_hand.mdl" in p[2]]
    if not open_profiles:
        failures.append("no unarmed primary [VR_HAND_PROFILE] line with v_hand.mdl")

    if out_dir:
        for name in ("unit_23_unarmed_rest.png", "unit_24_unarmed_moved.png"):
            if not (out_dir / name).exists():
                failures.append(f"missing capture {name}")

    print(f"Parsed {len(samples)} primary hand samples; {len(open_profiles)} unarmed profile lines.")
    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("UNARMED HAND INPUT CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
