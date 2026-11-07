#!/usr/bin/env python3
"""Prove the VR hands follow 6DoF controller input, and that the weapon follows.

The earlier hand check only proved that one forward vector changed between two
static captures. That passes even when translation is dead, when both hands are
copies of each other, or when the viewmodel drifts away from the palm, which is
exactly the class of failure that looks fine in Monado and breaks on a headset.

This checker consumes the `HAND_MOTION` sweep from `scripts/monado_unit_tests.cfg`
and verifies, against the commanded values:

  * the primary palm tracks every commanded translation at `vr_worldscale`;
  * the hand returns to rest with no drift;
  * the forward/up frame matches the commanded pitch/yaw/roll;
  * every pose stays stable (no teleports) and keeps the canonical hand reach;
  * both hands produce samples in every pose;
  * the offhand tracks its own offset instead of copying the primary hand;
  * with a weapon equipped, the anchored grip stays on the moving palm;
  * the two motion captures differ, so the render matches the telemetry.

Usage:
    python3 scripts/check_hand_motion.py <engine.log> [capture_dir]
"""

from __future__ import annotations

import math
import re
import statistics
import sys
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

MARKER_RE = re.compile(
    r"HAND_MOTION pose=(\w+) offset=([-\d.,]+) angles=([-\d.,]+)"
    r"(?: offhand_offset=([-\d.,]+) offhand_angles=([-\d.,]+))?"
)

POSE_RE = re.compile(
    r"\[HAND_POSE\]\s+ent=(\w+)\s+body=(-?\d+)\s+chain=(\w+)\s+"
    r"palm=\(([^)]+)\)\s+fingertip=\(([^)]+)\)\s+thumb=\(([^)]+)\)\s+"
    r"thumbbase=\(([^)]+)\)\s+wrist=\(([^)]+)\)\s+"
    r"fwd=\(([^)]+)\)\s+up=\(([^)]+)\)"
)

ANCHOR_RE = re.compile(
    r"\[VR_ANCHOR\]\s+bone=(.+?)\s+delta=\(([^)]+)\)\s+palm=\(([^)]+)\)"
)

POS_TOL = 2.0          # units; 5 cm of error would already be a bug
REST_DRIFT_TOL = 0.8   # units between the first and final rest pose
STEP_TOL = 5.0         # units between consecutive samples inside one pose
REACH_MIN, REACH_MAX = 5.8, 7.2
ANGLE_DOT = math.cos(math.radians(12.0))
ANCHOR_TOL = 60.0      # sanity bound for the per-frame grip correction
MIN_SAMPLES = 5


def vec(text: str):
    return tuple(float(x) for x in text.split())


def parse_triplet(text: str):
    return tuple(float(x) for x in text.split(","))


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def scale(a, k):
    return tuple(a[i] * k for i in range(3))


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def length(a):
    return math.sqrt(dot(a, a))


def norm(a):
    n = length(a)
    return tuple(x / n for x in a) if n > 1e-9 else (0.0, 0.0, 0.0)


def median_point(points):
    return tuple(statistics.median(p[i] for p in points) for i in range(3))


def angle_vectors(pitch, yaw, roll):
    sp, cp = math.sin(math.radians(pitch)), math.cos(math.radians(pitch))
    sy, cy = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    sr, cr = math.sin(math.radians(roll)), math.cos(math.radians(roll))
    forward = (cp * cy, cp * sy, -sp)
    up = (cr * sp * cy + sr * sy, cr * sp * sy - sr * cy, cr * cp)
    return forward, up


class Pose:
    def __init__(self, name, offset, angles, offhand_offset, offhand_angles):
        self.name = name
        self.offset = offset
        self.angles = angles
        self.offhand_offset = offhand_offset
        self.offhand_angles = offhand_angles
        self.samples = {"primary": [], "offhand": []}
        self.anchors = []


def parse(text: str):
    poses: list[Pose] = []
    current: Pose | None = None
    saw_begin = saw_end = False

    for line in text.splitlines():
        line = ANSI_RE.sub("", line)
        if "HAND_MOTION_TEST_BEGIN" in line:
            saw_begin = True
            continue
        if "HAND_MOTION_TEST_END" in line:
            saw_end = True
            continue

        marker = MARKER_RE.search(line)
        if marker:
            current = Pose(
                marker.group(1),
                parse_triplet(marker.group(2)),
                parse_triplet(marker.group(3)),
                parse_triplet(marker.group(4)) if marker.group(4) else None,
                parse_triplet(marker.group(5)) if marker.group(5) else None,
            )
            poses.append(current)
            continue

        if current is None:
            continue

        sample = POSE_RE.search(line)
        if sample:
            entity = sample.group(1)
            if entity in current.samples and sample.group(9):
                current.samples[entity].append({
                    "palm": vec(sample.group(4)),
                    "fingertip": vec(sample.group(5)),
                    "fwd": vec(sample.group(9)),
                    "up": vec(sample.group(10)),
                })
            continue

        anchor = ANCHOR_RE.search(line)
        if anchor:
            current.anchors.append({
                "delta": vec(anchor.group(2)),
                "palm": vec(anchor.group(3)),
            })

    return poses, saw_begin, saw_end


def settled(samples):
    if not samples:
        return []
    tail = max(MIN_SAMPLES // 2, len(samples) // 2)
    return samples[-tail:]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_hand_motion.py <engine.log> [capture_dir]")
        return 2

    log_path = Path(sys.argv[1])
    capture_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    text = log_path.read_text(encoding="latin1", errors="replace")

    poses, saw_begin, saw_end = parse(text)
    failures: list[str] = []
    notes: list[str] = []

    if not saw_begin:
        print("[FAIL] HAND_MOTION_TEST_BEGIN marker not found")
        return 1
    if not saw_end:
        failures.append("HAND_MOTION_TEST_END marker not found (sweep did not finish)")

    by_name = {pose.name: pose for pose in poses}
    required = ["rest", "forward", "left", "up", "rotate", "independent", "rest_again"]
    for name in required:
        if name not in by_name:
            failures.append(f"missing pose {name!r}")

    rest = by_name.get("rest")
    if not rest or not rest.samples["primary"]:
        print("[FAIL] no primary samples in the rest pose; nothing to compare")
        return 1
    rest_palm = median_point([s["palm"] for s in settled(rest.samples["primary"])])
    rest_offhand = None
    if rest.samples["offhand"]:
        rest_offhand = median_point([s["palm"] for s in settled(rest.samples["offhand"])])

    worldscale = 40.0

    for pose in poses:
        if not pose.name.startswith("armed_"):
            for entity in ("primary", "offhand"):
                samples = pose.samples[entity]
                if len(samples) < MIN_SAMPLES:
                    failures.append(
                        f"{pose.name}: only {len(samples)} {entity} samples (need {MIN_SAMPLES})"
                    )
                    continue
                for sample in samples:
                    reach = length(sub(sample["fingertip"], sample["palm"]))
                    if not (REACH_MIN <= reach <= REACH_MAX):
                        failures.append(
                            f"{pose.name}: {entity} reach {reach:.2f}u outside "
                            f"{REACH_MIN}-{REACH_MAX}"
                        )
                        break
                for previous, sample in zip(samples, samples[1:]):
                    step = length(sub(sample["palm"], previous["palm"]))
                    if step > STEP_TOL:
                        failures.append(
                            f"{pose.name}: {entity} palm jumped {step:.2f}u between frames"
                        )
                        break

    # Translation tracking and orientation.
    for name in ("forward", "left", "up", "rotate", "independent"):
        pose = by_name.get(name)
        if not pose:
            continue
        samples = settled(pose.samples["primary"])
        if len(samples) < MIN_SAMPLES:
            continue
        measured = median_point([s["palm"] for s in samples])
        expected = add(rest_palm, scale(pose.offset, worldscale))
        error = length(sub(measured, expected))
        if error > POS_TOL:
            failures.append(
                f"{name}: primary palm off by {error:.2f}u "
                f"(expected {expected}, measured {measured})"
            )
        else:
            notes.append(f"{name}: primary palm error {error:.2f}u")

        forward, up = angle_vectors(*pose.angles)
        sample = settled(pose.samples["primary"])[-1]
        if dot(norm(sample["fwd"]), forward) < ANGLE_DOT:
            failures.append(f"{name}: hand forward does not match the commanded angles")
        if dot(norm(sample["up"]), up) < ANGLE_DOT:
            failures.append(f"{name}: hand up does not match the commanded angles")

    # Return to rest without drift.
    if "rest_again" in by_name and by_name["rest_again"].samples["primary"]:
        again = median_point([s["palm"] for s in settled(by_name["rest_again"].samples["primary"])])
        drift = length(sub(again, rest_palm))
        if drift > REST_DRIFT_TOL:
            failures.append(f"rest_again: palm drifted {drift:.2f}u from the first rest pose")
        else:
            notes.append(f"rest_again: drift {drift:.2f}u")

    # Offhand independence.
    independent = by_name.get("independent")
    if independent and independent.offhand_offset and rest_offhand:
        samples = settled(independent.samples["offhand"])
        if len(samples) < MIN_SAMPLES:
            failures.append("independent: too few offhand samples to prove independence")
        else:
            measured = median_point([s["palm"] for s in samples])
            expected = add(rest_offhand, scale(independent.offhand_offset, worldscale))
            error = length(sub(measured, expected))
            primary_delta = scale(independent.offset, worldscale)
            offhand_delta = sub(measured, rest_offhand)
            separation = length(sub(offhand_delta, primary_delta))
            if error > POS_TOL:
                failures.append(f"independent: offhand palm off by {error:.2f}u")
            if separation < 1.0:
                failures.append(
                    "independent: offhand follows the primary hand instead of its own offset"
                )
            else:
                notes.append(f"independent: offhand separated by {separation:.2f}u")

            forward, up = angle_vectors(*independent.offhand_angles)
            sample = settled(independent.samples["offhand"])[-1]
            if dot(norm(sample["fwd"]), forward) < ANGLE_DOT:
                failures.append("independent: offhand forward ignores its commanded angles")
            if dot(norm(sample["up"]), up) < ANGLE_DOT:
                failures.append("independent: offhand up ignores its commanded angles")

    # Armed sweep: the viewmodel must stay anchored to the moving palm.
    armed = [pose for pose in poses if pose.name.startswith("armed_")]
    if not armed:
        failures.append("no armed poses found; the weapon anchor was not exercised")
    armed_rest = by_name.get("armed_rest")
    armed_rest_palm = None
    if armed_rest and armed_rest.anchors:
        armed_rest_palm = median_point([a["palm"] for a in armed_rest.anchors])
    for pose in armed:
        if not pose.anchors:
            failures.append(f"{pose.name}: no [VR_ANCHOR] sample (weapon anchor did not run)")
            continue
        for anchor in pose.anchors:
            # The logged delta is the per-frame correction that seats the
            # animated grip on the palm, not accumulated drift; a wild value
            # still means the pose math broke.
            correction = length(anchor["delta"])
            if correction > ANCHOR_TOL:
                failures.append(
                    f"{pose.name}: grip correction {correction:.2f}u outside the "
                    f"{ANCHOR_TOL:.0f}u sanity bound"
                )
                break
        if armed_rest_palm and pose.name != "armed_rest":
            measured = median_point([a["palm"] for a in pose.anchors])
            expected = add(armed_rest_palm, scale(pose.offset, worldscale))
            error = length(sub(measured, expected))
            if error > POS_TOL:
                failures.append(
                    f"{pose.name}: anchored palm off by {error:.2f}u "
                    f"(weapon does not follow the hand)"
                )
            else:
                notes.append(f"{pose.name}: anchored palm error {error:.2f}u")

    # Captures must differ, otherwise the render is not showing the motion.
    if capture_dir:
        names = ("unit_25_hand_motion_rest.png", "unit_26_hand_motion_forward.png")
        paths = [capture_dir / name for name in names]
        if not all(path.is_file() for path in paths):
            failures.append("missing hand motion captures " + ", ".join(names))
        else:
            try:
                from PIL import Image, ImageChops

                left = Image.open(paths[0]).convert("RGB")
                right = Image.open(paths[1]).convert("RGB")
                if left.size != right.size:
                    failures.append("hand motion captures have different sizes")
                else:
                    diff = ImageChops.difference(left, right)
                    if hasattr(diff, "get_flattened_data"):
                        pixels = list(diff.get_flattened_data())
                    else:
                        pixels = list(diff.getdata())
                    changed = sum(1 for p in pixels if max(p) > 16)
                    ratio = changed / len(pixels)
                    if ratio < 0.005:
                        failures.append(
                            f"hand motion captures are nearly identical ({ratio:.4%} pixels changed)"
                        )
                    else:
                        notes.append(f"motion captures differ on {ratio:.2%} of pixels")
            except Exception as error:  # noqa: BLE001 - report, never crash the gate
                failures.append(f"could not compare hand motion captures: {error}")

    for note in notes:
        print(f"[info] {note}")
    for failure in failures:
        print(f"[FAIL] {failure}")

    if failures:
        print(f"HAND MOTION CHECKS FAILED ({len(failures)} issue(s))")
        return 1
    print("HAND MOTION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
