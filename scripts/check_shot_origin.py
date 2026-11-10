#!/usr/bin/env python3
"""Verify where a VR shot starts and whether it follows the visible barrel.

Per weapon segment (marker `SHOT_PROBE weapon=...`) the engine logs:

  [VR_IMPACT_DBG] Shot #N start=(x y z) hit at (...) dist=... normal=(...)
  [VR_GRIP] src=muzzle model=... world=(x y z) angles=(...)
  [VR_ANCHOR] bone=... delta=(...) palm=(x y z)

The shot must start at the muzzle attachment (not at the eye and not at the
hand), the muzzle_pos -> muzzle_pos2 line is the visible barrel axis, and the
shot direction must follow that axis. Palm -> muzzle is only the fallback for
models without the second bore anchor. A sideways or downward start is what
makes a VR shot look crooked even when the viewmodel is aligned.

Usage:
    python3 scripts/check_shot_origin.py <engine.log>
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
MARK = re.compile(r"SHOT_PROBE weapon=(\w+)")
IMPACT = re.compile(
    r"\[VR_IMPACT_DBG\]\s+Shot #\d+\s+start=\(([^)]+)\)\s+hit at \(([^)]+)\)"
)
MUZZLE = re.compile(
    r"\[VR_GRIP\]\s+src=muzzle\s+model=(\S+).*?world=\(([^)]+)\).*?bore2=\(([^)]+)\)"
)
ANCHOR = re.compile(r"\[VR_ANCHOR\]\s+bone=(.+?)\s+delta=\(([^)]+)\)\s+palm=\(([^)]+)\)")

# Per-weapon tolerances. The shotgun fires pellets with spread, so its first
# impact is not a bore measurement; the gauss tracer starts a few units inside
# its muzzle cap.
TOLERANCES = {
    "weapon_shotgun": {"start": 2.0, "angle": 8.0, "axis": 2.0},
    "weapon_gauss": {"start": 3.5, "angle": 4.0, "axis": 3.5},
}
DEFAULT_TOL = {"start": 2.0, "angle": 2.0, "axis": 2.0}


def vec(text):
    return tuple(float(x) for x in text.replace(",", " ").split())


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def norm(a):
    n = math.sqrt(dot(a, a))
    return tuple(x / n for x in a) if n > 1e-9 else (0.0, 0.0, 0.0)


def length(a):
    return math.sqrt(dot(a, a))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_shot_origin.py <engine.log>")
        return 2

    lines = [ANSI_RE.sub("", line) for line in
             Path(sys.argv[1]).read_text(encoding="latin1", errors="replace").splitlines()]

    segments: dict[str, dict] = {}
    current = None
    palm = None
    shots = 0

    for number, line in enumerate(lines):
        marker = MARK.search(line)
        if marker:
            current = marker.group(1)
            segments.setdefault(current, {"start": None, "hit": None, "muzzle": None,
                                          "palm": None, "bore2": None})
            palm = None
            continue
        if current is None:
            continue

        anchor = ANCHOR.search(line)
        if anchor:
            palm = vec(anchor.group(3))
            segments[current]["palm"] = palm
            continue

        muzzle = MUZZLE.search(line)
        if muzzle and muzzle.group(2):
            segments[current]["muzzle"] = vec(muzzle.group(2))
            segments[current]["bore2"] = vec(muzzle.group(3))
            continue

        impact = IMPACT.search(line)
        if impact:
            shots += 1
            if segments[current]["start"] is None:
                segments[current]["start"] = vec(impact.group(1))
                segments[current]["hit"] = vec(impact.group(2))

    failures: list[str] = []
    rows = []
    for weapon, data in segments.items():
        start, hit, muzzle_w, palm_w = data["start"], data["hit"], data["muzzle"], data["palm"]
        if not all((start, hit, muzzle_w, palm_w)):
            failures.append(f"{weapon}: missing telemetry (start/hit/muzzle/palm)")
            continue

        # The visible bore is the model-authored muzzle_pos -> muzzle_pos2 axis
        # when the model exposes it; fall back to palm -> muzzle for models
        # without the second anchor.
        bore2 = data["bore2"]
        if bore2 and any(abs(value) > 1e-6 for value in bore2):
            barrel = norm(sub(bore2, muzzle_w))
            axis_origin = muzzle_w
        else:
            barrel = norm(sub(muzzle_w, palm_w))
            axis_origin = palm_w
        shot = norm(sub(hit, start))
        cosine = max(-1.0, min(1.0, dot(barrel, shot)))
        angle = math.degrees(math.acos(cosine))
        start_error = length(sub(start, muzzle_w))

        # Perpendicular distance from the shot start to the barrel line.
        delta = sub(start, axis_origin)
        along = dot(delta, barrel)
        offset = length(sub(delta, tuple(barrel[i] * along for i in range(3))))

        tol = TOLERANCES.get(weapon, DEFAULT_TOL)
        status = "PASS"
        if start_error > tol["start"]:
            status = "FAIL"
            failures.append(f"{weapon}: shot starts {start_error:.1f}u from the muzzle")
        if angle > tol["angle"]:
            status = "FAIL"
            failures.append(f"{weapon}: shot is {angle:.1f}deg off the visible barrel")
        if offset > tol["axis"]:
            status = "FAIL"
            failures.append(f"{weapon}: shot start is {offset:.1f}u off the barrel axis")

        barrel_pitch = math.degrees(math.asin(max(-1.0, min(1.0, -barrel[2]))))
        shot_pitch = math.degrees(math.asin(max(-1.0, min(1.0, -shot[2]))))
        barrel_yaw = math.degrees(math.atan2(barrel[1], barrel[0]))
        shot_yaw = math.degrees(math.atan2(shot[1], shot[0]))
        rows.append((weapon, start_error, angle, offset, status,
                     shot_pitch - barrel_pitch, shot_yaw - barrel_yaw))

    print(f"{'weapon':<22} {'start->muzzle':>13} {'vs barrel':>10} {'axis':>6} {'dpitch':>7} {'dyaw':>7}  status")
    for weapon, start_error, angle, offset, status, dpitch, dyaw in rows:
        print(f"{weapon:<22} {start_error:>13.2f} {angle:>10.2f} {offset:>6.2f} "
              f"{dpitch:>7.2f} {dyaw:>7.2f}  {status}")

    if shots == 0:
        failures.append("no [VR_IMPACT_DBG] shot line: nothing was fired")
    if not rows:
        failures.append("no complete weapon segment")

    for failure in failures:
        print(f"[FAIL] {failure}")
    if failures:
        print(f"SHOT ORIGIN CHECKS FAILED ({len(failures)} issue(s))")
        return 1
    print(f"SHOT ORIGIN CHECKS PASSED ({len(rows)} weapons, {shots} shots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
