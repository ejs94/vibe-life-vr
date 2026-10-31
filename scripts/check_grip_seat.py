#!/usr/bin/env python3
"""Grip seating gates for the VR weapon pose.

Parses the [VR_GRIP_BONE] telemetry emitted by vr_grip_probe and verifies that
the weapon's real grip anchor lands on the hand palm, i.e. the OpenXR grip pose
origin. The explicit palm_dist field is preferred; older logs fall back to
seat_err. A small residual below half a GoldSrc unit is accepted.

Usage:
    check_grip_seat.py <engine.log>

Exit status 0 = all gates pass, 1 = at least one gate failed.
"""

import argparse
import re
import sys

LINE_RE = re.compile(
    r"\[VR_GRIP_BONE\] model=(\S+) bone=(.+?) seq=(\d+) label=(\S*)"
    r".*?seat_err=([-\d.]+)(?:\s+palm_dist=([-\d.]+))?"
)

# The palm bone sits a fraction of a unit ahead of the wrist bone used as the
# weapon anchor; anything above half a GoldSrc unit means the seed is wrong.
TOL = 0.5


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log")
    parser.add_argument(
        "--strict-phases",
        action="store_true",
        help="require idle, fire and reload samples for the selected models",
    )
    parser.add_argument(
        "--models",
        default="",
        help="comma-separated model basenames to check (default: all)",
    )
    args = parser.parse_args()

    wanted = {m.strip() for m in args.models.split(",") if m.strip()}
    samples = {}
    with open(args.log, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = LINE_RE.search(line)
            if not m:
                continue
            model, bone, seq, label = m.group(1), m.group(2), m.group(3), m.group(4)
            if wanted and model.rsplit("/", 1)[-1] not in wanted:
                continue
            # Prefer the explicit palm_dist field; fall back to seat_err for
            # logs produced before the palm reference was added.
            value = m.group(6) if m.group(6) is not None else m.group(5)
            err = float(value)
            if err < 0.0:
                # XR_GetPrimaryHandTransform was unavailable in this frame.
                continue
            samples.setdefault(model, []).append((bone, seq, label, err))

    if not samples:
        print("[gate] FAIL: no [VR_GRIP_BONE] samples with a valid palm_dist")
        return 1

    failures = []
    print(f"[gate] models with a valid palm sample: {len(samples)}")
    for model in sorted(samples):
        rows = samples[model]
        worst = max(r[3] for r in rows)
        idle = [r for r in rows if "idle" in r[2].lower() or "fidget" in r[2].lower()]
        fire = [r for r in rows if "fire" in r[2].lower() or "shoot" in r[2].lower()]
        reload_rows = [r for r in rows if "reload" in r[2].lower()]
        idle_worst = max((r[3] for r in idle), default=None)
        fire_worst = max((r[3] for r in fire), default=None)
        reload_worst = max((r[3] for r in reload_rows), default=None)
        status = "ok" if worst < TOL else "FAIL"
        extra = ""
        if idle_worst is not None:
            extra += f" idle_worst={idle_worst:.3f}"
        if fire_worst is not None:
            extra += f" fire_worst={fire_worst:.3f}"
        if reload_worst is not None:
            extra += f" reload_worst={reload_worst:.3f}"
        print(f"[gate] {model}: worst={worst:.3f} samples={len(rows)}"
              f" bone={rows[0][0]}{extra} ({status})")
        if worst >= TOL:
            failures.append(f"{model}: palm_dist {worst:.3f} >= {TOL}")
        if args.strict_phases:
            for phase, phase_rows in (("idle", idle), ("fire", fire), ("reload", reload_rows)):
                if not phase_rows:
                    failures.append(f"{model}: no {phase} sample with a valid palm_dist")

    if failures:
        print("[gate] FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("[gate] all grip seating gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
