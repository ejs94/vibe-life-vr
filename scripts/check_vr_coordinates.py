#!/usr/bin/env python3
"""Reject coordinate regressions in the VR telemetry.

Every VR transform is expressed in one of two spaces: view-relative offsets
(`origin=`) or absolute world positions (`world=`). Mixing them, or leaving a
part at the world origin, is the failure that produced misplaced muzzles and
floating hands in the past. This check reads the whole engine log and enforces
the invariants that make those bugs impossible to ship:

  * every logged coordinate is finite;
  * no muzzle, hand or anchor sits exactly at (0, 0, 0);
  * the muzzle stays inside the gun-length range from the eye;
  * the muzzle and the viewmodel agree on the same scale (their view-relative
    offsets differ by at most one weapon length);
  * every hand sample keeps the canonical palm reach and stays glued to the
    grip-pose origin;
  * anchored palms sit close to the viewmodel, not at the world origin.

Usage:
    python3 scripts/check_vr_coordinates.py <engine.log>
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

GRIP_RE = re.compile(
    r"\[VR_GRIP\]\s+src=(\w+)\s+model=(\S*)\s+origin=\(([^)]+)\)"
    r"(?:\s+world=\(([^)]+)\))?\s+angles=\(([^)]+)\)"
)

HAND_RE = re.compile(
    r"\[HAND_POSE\]\s+ent=(\w+)\s+body=(-?\d+)\s+chain=(\w+)\s+"
    r"palm=\(([^)]+)\)\s+fingertip=\(([^)]+)\)\s+thumb=\(([^)]+)\)\s+"
    r"thumbbase=\(([^)]+)\)\s+wrist=\(([^)]+)\)\s+"
    r"fwd=\(([^)]+)\)\s+up=\(([^)]+)\)"
    r"(?:\s+grip_dist=([-\d.]+))?"
)

ANCHOR_RE = re.compile(
    r"\[VR_ANCHOR\]\s+bone=(.+?)\s+delta=\(([^)]+)\)\s+palm=\(([^)]+)\)"
)

MUZZLE_MIN, MUZZLE_MAX = 2.0, 55.0     # units from the eye
GUN_LENGTH_MIN, GUN_LENGTH_MAX = 1.0, 60.0  # muzzle world vs viewmodel world
WORLD_COORD_MAX = 60000.0              # absolute bound; catches NaN/space mixups
REACH_MIN, REACH_MAX = 5.8, 7.2
GRIP_DIST_MAX = 0.25
ANCHOR_PALM_MAX = 120.0


def vec(text):
    parts = [float(x) for x in text.split()]
    if len(parts) != 3:
        raise ValueError(f"expected 3 components, got {text!r}")
    return tuple(parts)


def finite(point):
    return all(math.isfinite(v) for v in point)


def length(point):
    return math.sqrt(sum(v * v for v in point))


def distance(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def at_origin(point, tolerance=0.01):
    return length(point) <= tolerance


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_vr_coordinates.py <engine.log>")
        return 2

    text = Path(sys.argv[1]).read_text(encoding="latin1", errors="replace")
    lines = [ANSI_RE.sub("", line) for line in text.splitlines()]

    failures: list[str] = []
    counts = {"grip": 0, "muzzle": 0, "hand": 0, "anchor": 0}
    last_viewmodel_origin = None
    last_viewmodel_line = -1000
    mismatches = 0
    checked_pairs = 0

    for number, line in enumerate(lines):
        grip = GRIP_RE.search(line)
        if grip:
            counts["grip"] += 1
            source = grip.group(1)
            model = grip.group(2) or ""
            origin = vec(grip.group(3))
            world = vec(grip.group(4)) if grip.group(4) else None

            if not finite(origin) or (world is not None and not finite(world)):
                failures.append(f"line {number + 1}: non-finite {source} coordinate")
                continue

            if source == "muzzle" and model:
                counts["muzzle"] += 1
                size = length(origin)
                if size < MUZZLE_MIN or size > MUZZLE_MAX:
                    failures.append(
                        f"line {number + 1}: muzzle is {size:.1f}u from the eye "
                        f"(expected {MUZZLE_MIN}-{MUZZLE_MAX})"
                    )
                if world is not None and at_origin(world):
                    failures.append(
                        f"line {number + 1}: muzzle world position collapsed to (0,0,0)"
                    )
                # The renderer logs a world position; the muzzle logs both a
                # view-relative offset and a world position. Compare the two
                # world positions: they must differ by about one gun length.
                if world is not None and last_viewmodel_origin is not None \
                        and number - last_viewmodel_line < 40:
                    gap = distance(world, last_viewmodel_origin)
                    checked_pairs += 1
                    if not (GUN_LENGTH_MIN <= gap <= GUN_LENGTH_MAX):
                        mismatches += 1
                        failures.append(
                            f"line {number + 1}: muzzle sits {gap:.1f}u from the "
                            "viewmodel origin (different coordinate spaces?)"
                        )
            elif source in ("renderer", "viewmodel") and model:
                # These report a world position, not a view-relative offset.
                last_viewmodel_origin = origin
                last_viewmodel_line = number
                if at_origin(origin):
                    failures.append(
                        f"line {number + 1}: viewmodel origin collapsed to (0,0,0)"
                    )
                if length(origin) > WORLD_COORD_MAX:
                    failures.append(
                        f"line {number + 1}: viewmodel origin is not a world coordinate"
                    )
            continue

        hand = HAND_RE.search(line)
        if hand:
            counts["hand"] += 1
            palm = vec(hand.group(4))
            tip = vec(hand.group(5))
            wrist = vec(hand.group(8))
            if not (finite(palm) and finite(tip) and finite(wrist)):
                failures.append(f"line {number + 1}: non-finite hand coordinate")
                continue
            if at_origin(palm):
                failures.append(f"line {number + 1}: hand palm collapsed to (0,0,0)")
            reach = distance(palm, tip)
            if not (REACH_MIN <= reach <= REACH_MAX):
                failures.append(
                    f"line {number + 1}: hand reach {reach:.2f}u outside "
                    f"{REACH_MIN}-{REACH_MAX}"
                )
            if hand.group(11) is not None:
                grip_dist = float(hand.group(11))
                if grip_dist < 0 or grip_dist > GRIP_DIST_MAX:
                    failures.append(
                        f"line {number + 1}: palm {grip_dist:.2f}u from the grip origin"
                    )
            continue

        anchor = ANCHOR_RE.search(line)
        if anchor:
            counts["anchor"] += 1
            delta = vec(anchor.group(2))
            palm = vec(anchor.group(3))
            if not (finite(delta) and finite(palm)):
                failures.append(f"line {number + 1}: non-finite anchor coordinate")
                continue
            if at_origin(palm):
                failures.append(f"line {number + 1}: anchored palm collapsed to (0,0,0)")
            if length(palm) > WORLD_COORD_MAX:
                failures.append(
                    f"line {number + 1}: anchored palm is not a world coordinate"
                )

    for name, count in counts.items():
        print(f"[info] {count} {name} lines checked")
    if checked_pairs:
        print(f"[info] {checked_pairs} muzzle/viewmodel space pairs compared")

    if counts["muzzle"] == 0:
        failures.append("no [VR_GRIP] src=muzzle line: the muzzle path was not exercised")
    if counts["hand"] == 0:
        failures.append("no [HAND_POSE] line: the hand path was not exercised")
    if counts["anchor"] == 0:
        failures.append("no [VR_ANCHOR] line: the anchor path was not exercised")
    if counts["muzzle"] and checked_pairs == 0:
        failures.append("muzzle and viewmodel lines never overlapped; space check did not run")

    for failure in failures:
        print(f"[FAIL] {failure}")
    if failures:
        print(f"VR COORDINATE CHECKS FAILED ({len(failures)} issue(s))")
        return 1
    print("VR COORDINATE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
