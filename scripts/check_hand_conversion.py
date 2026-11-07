#!/usr/bin/env python3
"""Verify the OpenXR -> GoldSrc hand angle conversion maps the right axes.

The engine converts a controller quaternion to GoldSrc pitch/yaw/roll. If an
OpenXR pitch lands on the GoldSrc roll axis (or a yaw lands on pitch), every
imported viewmodel appears rotated and the laser cannot follow the barrel. This
check feeds three known OpenXR rotations through the engine probe and asserts
the axis mapping.

Usage:
    python3 scripts/check_hand_conversion.py <engine.log>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
LINE_RE = re.compile(
    r"\[VR_CONV\]\s+openxr=\(([-\d.]+) ([-\d.]+) ([-\d.]+)\)\s+"
    r"legacy=\(([-\d.]+) ([-\d.]+) ([-\d.]+)\)"
)

TOL = 2.0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_hand_conversion.py <engine.log>")
        return 2

    text = Path(sys.argv[1]).read_text(encoding="latin1", errors="replace")
    samples = {}
    for line in text.splitlines():
        match = LINE_RE.search(ANSI_RE.sub("", line))
        if not match:
            continue
        openxr = tuple(float(match.group(i)) for i in (1, 2, 3))
        legacy = tuple(float(match.group(i)) for i in (4, 5, 6))
        samples[openxr] = legacy

    failures: list[str] = []

    def expect(openxr, pitch, yaw, roll):
        legacy = samples.get(openxr)
        if legacy is None:
            failures.append(f"missing probe for openxr={openxr}")
            return
        for index, value, name in ((0, pitch, "pitch"), (1, yaw, "yaw"), (2, roll, "roll")):
            if abs(legacy[index] - value) > TOL:
                failures.append(
                    f"openxr={openxr}: {name} {legacy[index]:.1f}, expected {value:.1f}"
                )

    # OpenXR pitch is about +X (right). GoldSrc pitch is about -Y, so a
    # controller tilting up must produce a negative GoldSrc pitch.
    expect((30.0, 0.0, 0.0), -30.0, 0.0, 0.0)
    # OpenXR yaw is about +Y (up), same as GoldSrc yaw about +Z.
    expect((0.0, 30.0, 0.0), 0.0, 30.0, 0.0)
    # OpenXR roll is about +Z (back); GoldSrc roll is negated by the engine.
    expect((0.0, 0.0, 30.0), 0.0, 0.0, -30.0)

    for failure in failures:
        print(f"[FAIL] {failure}")
    if failures:
        print("HAND CONVERSION CHECKS FAILED")
        return 1
    print(f"HAND CONVERSION CHECKS PASSED ({len(samples)} probes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
