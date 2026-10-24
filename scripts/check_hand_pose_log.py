#!/usr/bin/env python3
"""Parse [HAND_POSE] telemetry lines and assert hand orientation/selection.

Reads a Xash3D VR engine log produced with `vr_debug_hand_pose 1` and verifies,
per emitted landmark line:

  * the fingers point along the hand's forward axis (pose-invariant)
  * the thumb points along the hand's up axis (pose-invariant)
  * the bodygroup selects the correct chain for the entity and handedness
  * the wrist->fingertip reach is within the canonical hand size

Lines look like:
  [HAND_POSE] ent=primary body=0 chain=R palm=(x y z) fingertip=(x y z) \
    thumb=(x y z) thumbbase=(x y z) wrist=(x y z) fwd=(x y z) up=(x y z)

When the `fwd`/`up` frame is present the assertions are invariant to the
player's world heading, so the same gate works on PCVR simulation and on a real
headset. Without it (older telemetry) the tool falls back to the world +X/+Y
axis checks used by the deterministic PCVR pose.
"""

from __future__ import annotations

import argparse
import math
import re
import sys

# Minimum cosine between a bone direction and the hand's reference axis.
FORWARD_DOT = 0.70
UP_DOT = 0.20

# Fallback thresholds for telemetry without the hand frame.
DOMINANCE = 0.5
SIGN_EPS = 0.05

LINE_RE = re.compile(
    r"\[HAND_POSE\]\s+ent=(\w+)\s+body=(-?\d+)\s+chain=(\w+)\s+"
    r"palm=\(([^)]+)\)\s+fingertip=\(([^)]+)\)\s+thumb=\(([^)]+)\)\s+"
    r"thumbbase=\(([^)]+)\)(?:.*wrist=\(([^)]+)\))?"
    r"(?:\s+fwd=\(([^)]+)\)\s+up=\(([^)]+)\))?"
)

REACH_MIN, REACH_MAX = 5.8, 7.2


def parse_vec(text: str) -> tuple[float, float, float]:
    parts = [float(x) for x in text.split()]
    return (parts[0], parts[1], parts[2])


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def dot(a, b) -> float:
    return sum(a[i] * b[i] for i in range(3))


def norm(v):
    length = math.sqrt(dot(v, v))
    if length < 1e-9:
        return (0.0, 0.0, 0.0), 0.0
    return (v[0] / length, v[1] / length, v[2] / length), length


def dominant(v, axis: int, sign: int) -> bool:
    other = [abs(v[i]) for i in range(3) if i != axis]
    return sign * v[axis] > 0 and abs(v[axis]) > DOMINANCE * max(other)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log")
    parser.add_argument("--expect-hands", default="primary,offhand",
                        help="comma-separated entity names that must appear")
    args = parser.parse_args()

    samples = []
    with open(args.log, encoding="latin1", errors="replace") as handle:
        for line in handle:
            m = LINE_RE.search(line)
            if not m:
                continue
            samples.append({
                "ent": m.group(1),
                "body": int(m.group(2)),
                "chain": m.group(3),
                "palm": parse_vec(m.group(4)),
                "fingertip": parse_vec(m.group(5)),
                "thumb": parse_vec(m.group(6)),
                "thumbbase": parse_vec(m.group(7)),
                "wrist": parse_vec(m.group(8)) if m.group(8) else None,
                "fwd": parse_vec(m.group(9)) if m.group(9) else None,
                "up": parse_vec(m.group(10)) if m.group(10) else None,
            })

    failures = []
    checks = 0
    print(f"Parsed {len(samples)} [HAND_POSE] landmark lines.")

    if not samples:
        print("[FAIL] no [HAND_POSE] telemetry found in the log")
        return 1

    for s in samples:
        tag = f"{s['ent']}(body={s['body']},chain={s['chain']})"
        fdir = sub(s["fingertip"], s["palm"])
        tdir = sub(s["thumb"], s["palm"])

        if s["fwd"] and s["up"]:
            # Pose-invariant: express the bones in the hand's own frame.
            fnorm = norm(fdir)[0]
            tnorm = norm(tdir)[0]
            fwd = norm(s["fwd"])[0]
            up = norm(s["up"])[0]

            checks += 1
            if dot(fnorm, fwd) < FORWARD_DOT:
                failures.append(f"{tag}: fingers not along hand forward "
                                f"(dot={dot(fnorm, fwd):.2f})")

            checks += 1
            if dot(tnorm, up) < UP_DOT:
                failures.append(f"{tag}: thumb not along hand up "
                                f"(dot={dot(tnorm, up):.2f})")
        else:
            # Fallback: deterministic PCVR pose (player faces +X).
            checks += 1
            if not dominant(fdir, 0, +1):
                failures.append(f"{tag}: fingers not forward (+X) -> {fdir}")

            checks += 1
            if not dominant(tdir, 2, +1):
                failures.append(f"{tag}: thumb not up (+Z) -> {tdir}")

            checks += 1
            want = +1 if s["chain"] == "R" else -1
            base_off = sub(s["thumbbase"], s["palm"])
            if want * base_off[1] <= SIGN_EPS:
                failures.append(f"{tag}: palm not inward, thumbbase.y={base_off[1]:.2f}")

        # Reach sanity, pose-invariant.
        if s["wrist"]:
            checks += 1
            reach = math.dist(s["wrist"], s["fingertip"])
            if not (REACH_MIN <= reach <= REACH_MAX):
                failures.append(f"{tag}: wrist->fingertip reach {reach:.2f} out of range")

        # Bodygroup selection: chain R is body 0, chain L is body 3.
        checks += 1
        expect_body = 0 if s["chain"] == "R" else 3
        if s["body"] != expect_body:
            failures.append(f"{tag}: chain {s['chain']} should be body {expect_body}")

    # Both entities must have produced telemetry at least once.
    seen = {s["ent"] for s in samples}
    for ent in args.expect_hands.split(","):
        ent = ent.strip()
        if not ent:
            continue
        checks += 1
        if ent not in seen:
            failures.append(f"no [HAND_POSE] telemetry for entity '{ent}'")

    # Both handedness modes exercise the swap: primary chain must appear as
    # both R and L across the run (right-handed and left-handed primary).
    primary_chains = {s["chain"] for s in samples if s["ent"] == "primary"}
    checks += 1
    if not {"R", "L"}.issubset(primary_chains):
        failures.append("primary hand never swapped chain for vr_lefthanded "
                        f"(saw {sorted(primary_chains)})")

    print("\n" + "=" * 58)
    print(f"Hand pose assertions: {checks}   failures: {len(failures)}")
    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("ALL HAND POSE TELEMETRY ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
