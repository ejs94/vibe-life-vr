#!/usr/bin/env python3
"""Assert the weapon follows the aim pose, not the tilted grip pose.

``monado_unit_tests.cfg`` Phase 17 sets ``vr_test_grip_delta_pitch 35`` while
keeping the simulated aim pitch at 0, then brackets the run with
``AIM_GRIP_PROBE_BEGIN`` / ``AIM_GRIP_PROBE_END`` markers. A regression to the
old grip-oriented viewmodel shows a ~35 degree pitch in the last
``[VR_GRIP] src=viewmodel`` line; the correct aim-oriented path stays at 0.

Usage: check_aim_pose.py <engine.log>
Exit code 0 = PASS.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ANGLES_RE = re.compile(r"src=(\w+).*angles=\(([-0-9. ]+)\)")


def parse_angles(line: str) -> tuple[str, tuple[float, float, float]] | None:
    match = ANGLES_RE.search(line)
    if not match:
        return None
    values = [float(v) for v in match.group(2).split()]
    if len(values) != 3:
        return None
    return match.group(1), (values[0], values[1], values[2])


def pitch_delta(a: float, b: float) -> float:
    diff = (a - b + 180.0) % 360.0 - 180.0
    return abs(diff)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_aim_pose.py <engine.log>")
        return 2

    log = Path(sys.argv[1]).read_text(errors="replace")
    begin = log.find("AIM_GRIP_PROBE_BEGIN")
    end = log.find("AIM_GRIP_PROBE_END", begin if begin >= 0 else 0)

    if begin < 0 or end < 0 or end <= begin:
        print("[FAIL] aim/grip probe markers missing from the engine log")
        return 1

    region = log[begin:end]
    last: dict[str, tuple[float, float, float]] = {}
    for line in region.splitlines():
        parsed = parse_angles(line)
        if parsed:
            src, angles = parsed
            last[src] = angles

    missing = [src for src in ("renderer", "viewmodel") if src not in last]
    if missing:
        print(f"[FAIL] missing [VR_GRIP] telemetry for: {', '.join(missing)}")
        return 1

    failures: list[str] = []
    limit = 1.0
    for src in ("renderer", "viewmodel"):
        pitch = last[src][0]
        if abs(pitch) > limit:
            failures.append(
                f"{src} pitch={pitch:.1f}deg (expected ~0; grip delta was 35deg)"
            )

    drift = pitch_delta(last["renderer"][0], last["viewmodel"][0])
    if drift > 0.5:
        failures.append(
            f"renderer/viewmodel pitch disagree by {drift:.1f}deg"
        )

    print(
        "aim/grip probe: "
        f"renderer=({last['renderer'][0]:.1f},{last['renderer'][1]:.1f},{last['renderer'][2]:.1f}) "
        f"viewmodel=({last['viewmodel'][0]:.1f},{last['viewmodel'][1]:.1f},{last['viewmodel'][2]:.1f})"
    )

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1

    print("[PASS] viewmodel and renderer follow the aim pose with a 35deg grip offset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
