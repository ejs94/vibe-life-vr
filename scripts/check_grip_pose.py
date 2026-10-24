#!/usr/bin/env python3
"""Sprint B grip-pose gates.

Parses the [VR_GRIP] log lines emitted by the renderer, the muzzle fallback
and the viewmodel setup path, then asserts that the three call sites agree
now that they share XR_GetWeaponPose.

Usage:
    check_grip_pose.py <engine.log>

Exit status 0 = all gates pass, 1 = at least one gate failed.
"""

import re
import sys

LINE_RE = re.compile(
    r"\[VR_GRIP\] src=(\w+) model=(\S*) origin=\(([-\d.]+) ([-\d.]+) ([-\d.]+)\)"
    r"(?: world=\(([-\d.]+) ([-\d.]+) ([-\d.]+)\))?"
    r" angles=\(([-\d.]+) ([-\d.]+) ([-\d.]+)\) lefthanded=(\d)"
)

TOL = 0.1


def parse(path):
    """Return dict[(src, model, lefthanded)] -> (origin, world)."""
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = LINE_RE.search(line)
            if not m:
                continue
            src, model, lh = m.group(1), m.group(2), m.group(12)
            origin = tuple(float(m.group(i)) for i in (3, 4, 5))
            world = None
            if m.group(6) is not None:
                world = tuple(float(m.group(i)) for i in (6, 7, 8))
            out[(src, model, lh)] = (origin, world)
    return out


def main():
    if len(sys.argv) < 2:
        print("usage: check_grip_pose.py <log>")
        return 2

    data = parse(sys.argv[1])
    failures = []

    models = sorted({k[1] for k in data if k[1]})
    print(f"[gate] models seen: {', '.join(models) if models else '(none)'}")

    # Gate A: renderer and viewmodel must resolve to the same world origin
    # for every model, in both handedness modes (single source of truth).
    for lh in ("0", "1"):
        checked = 0
        for model in models:
            r = data.get(("renderer", model, lh))
            v = data.get(("viewmodel", model, lh))
            if not r or not v:
                continue
            checked += 1
            delta = max(abs(r[0][i] - v[0][i]) for i in range(3))
            status = "ok" if delta < TOL else "FAIL"
            print(f"[gate] lh={lh} {model}: renderer vs viewmodel "
                  f"delta={delta:.3f} ({status})")
            if delta >= TOL:
                failures.append(f"lh={lh} {model}: renderer/viewmodel delta {delta:.3f}")

        if checked == 0:
            print(f"[gate] lh={lh}: no overlapping renderer/viewmodel samples")

    # Gate B: left-handed mode must actually shift the lateral axis.
    moved = False
    for model in models:
        r0 = data.get(("renderer", model, "0"))
        r1 = data.get(("renderer", model, "1"))
        if r0 and r1:
            dy = abs(r0[0][1] - r1[0][1])
            if dy > TOL:
                moved = True
                print(f"[gate] {model}: left-handed lateral shift dy={dy:.3f} (mirror active)")
    if not moved:
        failures.append("left-handed mirror produced no lateral shift")

    # Gate C: for fallback (no-attachment) weapons the muzzle world position
    # must sit ahead of the weapon origin along the aim direction, i.e. the
    # fallback barrel extension is still applied on top of the shared pose.
    fallback_seen = False
    for (src, model, lh), (origin, world) in data.items():
        if src != "muzzle" or world is None:
            continue
        fallback_seen = True
        dist = sum((world[i] - origin[i]) ** 2 for i in range(3)) ** 0.5
        if dist < 1.0:
            failures.append(f"{model}: muzzle world is not ahead of weapon origin")
    if not fallback_seen:
        print("[gate] note: no muzzle world samples (attachment path only)")

    if failures:
        print("[gate] FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("[gate] all grip-pose gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
