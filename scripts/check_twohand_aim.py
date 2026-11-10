#!/usr/bin/env python3
"""Check that the firing line ignores the two-hand transform offset.

The engine log is split by the TWO_HAND_CONTROL and TWO_HAND_STRESS markers.
In the control segment `vr_test_hand_transform_yaw` is 0; in the stress segment
it is 20 degrees. The muzzle path must report the aim angles in both, because
it must not follow the two-hand stabilizer.

Usage:
    python3 scripts/check_twohand_aim.py <engine.log>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
GRIP_RE = re.compile(r"\[VR_GRIP\]\s+src=muzzle\s+model=(\S*).*?angles=\(([^)]+)\)")
CONTROL = "TWO_HAND_CONTROL"
STRESS = "TWO_HAND_STRESS"
TOLERANCE = 0.5


def normalise_yaw(value: float) -> float:
    return ((value + 180.0) % 360.0) - 180.0


def collect(lines: list[str], segment: str) -> list[tuple[float, float]]:
    samples: list[tuple[float, float]] = []
    inside = False
    for line in lines:
        if f"{segment}_BEGIN" in line:
            inside = True
            continue
        if f"{segment}_END" in line:
            inside = False
            continue
        if not inside:
            continue
        match = GRIP_RE.search(line)
        if not match or not match.group(1).startswith("models/"):
            continue
        pitch, yaw, _roll = (float(value) for value in match.group(2).split())
        samples.append((pitch, normalise_yaw(yaw)))
    return samples


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_twohand_aim.py <engine.log>")
        return 2

    lines = [
        ANSI_RE.sub("", line)
        for line in Path(sys.argv[1]).read_text(encoding="latin1", errors="replace").splitlines()
    ]
    control = collect(lines, CONTROL)
    stress = collect(lines, STRESS)

    if not control or not stress:
        print(
            f"[FAIL] missing samples: control={len(control)} stress={len(stress)}; "
            "the muzzle telemetry was not exercised in both segments"
        )
        return 1

    control_yaw = max(abs(yaw) for _pitch, yaw in control)
    stress_yaw = max(abs(yaw) for _pitch, yaw in stress)
    control_pitch = max(abs(pitch) for pitch, _yaw in control)
    stress_pitch = max(abs(pitch) for pitch, _yaw in stress)

    print(
        f"control: samples={len(control)} max|yaw|={control_yaw:.2f} "
        f"max|pitch|={control_pitch:.2f}"
    )
    print(
        f"stress:  samples={len(stress)} max|yaw|={stress_yaw:.2f} "
        f"max|pitch|={stress_pitch:.2f}"
    )

    failures = []
    if control_yaw > TOLERANCE:
        failures.append(f"control firing line drifted {control_yaw:.2f} deg")
    if stress_yaw > TOLERANCE:
        failures.append(
            f"stress firing line followed the two-hand offset by {stress_yaw:.2f} deg"
        )
    if stress_pitch > TOLERANCE:
        failures.append(f"stress firing line pitched {stress_pitch:.2f} deg")

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        print("TWO-HAND AIM CHECK FAILED: the firing line follows the hand transform")
        return 1

    print(
        "TWO-HAND AIM CHECK PASSED: a 20 degree two-hand offset did not move the "
        "firing line; it stayed on the aim pose"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
