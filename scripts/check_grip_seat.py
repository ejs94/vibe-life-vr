#!/usr/bin/env python3
"""Grip seating gates for the VR weapon pose.

Parses the [VR_GRIP_BONE] telemetry emitted by vr_grip_probe and verifies that
the weapon's real grip anchor lands on the hand origin used by
XR_GetWeaponPose. A small residual (the wrist/palm offset) is expected.

Usage:
    check_grip_seat.py <engine.log>

Exit status 0 = all gates pass, 1 = at least one gate failed.
"""

import re
import sys

LINE_RE = re.compile(
    r"\[VR_GRIP_BONE\] model=(\S+) bone=(.+?) seq=(\d+) label=(\S*)"
    r".*?seat_err=([-\d.]+)"
)

# The palm bone sits a fraction of a unit ahead of the wrist bone used as the
# weapon anchor; anything above half a GoldSrc unit means the seed is wrong.
TOL = 0.5


def main():
    if len(sys.argv) < 2:
        print("usage: check_grip_seat.py <log>")
        return 2

    samples = {}
    with open(sys.argv[1], encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = LINE_RE.search(line)
            if not m:
                continue
            model, bone, seq, label = m.group(1), m.group(2), m.group(3), m.group(4)
            err = float(m.group(5))
            if err < 0.0:
                # XR_GetPrimaryHandTransform was unavailable in this frame.
                continue
            samples.setdefault(model, []).append((bone, seq, label, err))

    if not samples:
        print("[gate] FAIL: no [VR_GRIP_BONE] samples with a valid seat_err")
        return 1

    failures = []
    print(f"[gate] models with a valid seat sample: {len(samples)}")
    for model in sorted(samples):
        rows = samples[model]
        worst = max(r[3] for r in rows)
        idle = [r for r in rows if "idle" in r[2].lower() or "fidget" in r[2].lower()]
        idle_worst = max((r[3] for r in idle), default=None)
        status = "ok" if worst < TOL else "FAIL"
        extra = "" if idle_worst is None else f" idle_worst={idle_worst:.3f}"
        print(f"[gate] {model}: worst={worst:.3f} samples={len(rows)}"
              f" bone={rows[0][0]}{extra} ({status})")
        if worst >= TOL:
            failures.append(f"{model}: seat_err {worst:.3f} >= {TOL}")

    if failures:
        print("[gate] FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("[gate] all grip seating gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
