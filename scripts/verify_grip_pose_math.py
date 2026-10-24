#!/usr/bin/env python3
"""Sprint B: source-replay equivalence check for XR_GetWeaponPose.

The refactor moved the weapon pose math out of three duplicated call sites
into XR_GetWeaponPose. For right-handed players the numeric result must be
unchanged. This script replays the pre-refactor formulas (kept in the Sprint B
backup) and the post-refactor formula over a randomized input grid and
reports the maximum deviation.

Run:
    python3 scripts/verify_grip_pose_math.py
"""

import math
import random

TOL = 1e-4


def anglemod(a):
    return (a % 360.0 + 360.0) % 360.0


def angle_vectors(angles):
    yaw = math.radians(angles[1])
    pitch = math.radians(angles[0])
    roll = math.radians(angles[2])
    sy, cy = math.sin(yaw), math.cos(yaw)
    sp, cp = math.sin(pitch), math.cos(pitch)
    sr, cr = math.sin(roll), math.cos(roll)
    fwd = (cp * cy, cp * sy, -sp)
    rt = (-sr * sp * cy + -cr * -sy, -sr * sp * sy + -cr * cy, -sr * cp)
    up = (cr * sp * cy + -sr * -sy, cr * sp * sy + -sr * cy, cr * cp)
    return fwd, rt, up


def old_selector(hand, hand_ang, turn_yaw, view, scale, prof, glob, lefthanded):
    """Pre-refactor renderer/viewmodel formula (no muzzle extension)."""
    hx, hy, hz = hand
    c, s = math.cos(math.radians(turn_yaw)), math.sin(math.radians(turn_yaw))
    world = ((hx * c - hy * s) * scale,
             (hx * s + hy * c) * scale,
             hz * scale)

    angles = (hand_ang[0] + prof["pitch"],
              anglemod(hand_ang[1] + turn_yaw + prof["yaw"]),
              hand_ang[2] + prof["roll"])

    fwd, rt, up = angle_vectors(angles)
    off_fwd = glob["fwd"] + prof["grip"][0]
    off_rt = glob["rt"] + prof["grip"][1]
    off_up = glob["up"] + prof["grip"][2]
    if lefthanded:
        off_rt = -off_rt

    origin = tuple(view[i] + world[i] + fwd[i] * off_fwd + rt[i] * off_rt + up[i] * off_up
                   for i in range(3))
    return origin, angles


def new_pose(hand, hand_ang, turn_yaw, view, scale, prof, glob, lefthanded):
    """Post-refactor XR_GetWeaponPose formula (verbatim)."""
    hx, hy, hz = hand
    c, s = math.cos(math.radians(turn_yaw)), math.sin(math.radians(turn_yaw))
    world = ((hx * c - hy * s) * scale,
             (hx * s + hy * c) * scale,
             hz * scale)

    out = [view[i] + world[i] for i in range(3)]
    angles = (hand_ang[0] + prof["pitch"],
              anglemod(hand_ang[1] + turn_yaw + prof["yaw"]),
              hand_ang[2] + prof["roll"])

    fwd, rt, up = angle_vectors(angles)
    off_fwd = glob["fwd"] + prof["grip"][0]
    off_rt = glob["rt"] + prof["grip"][1]
    off_up = glob["up"] + prof["grip"][2]
    if lefthanded:
        off_rt = -off_rt

    for i in range(3):
        out[i] += fwd[i] * off_fwd + rt[i] * off_rt + up[i] * off_up
    return tuple(out), angles


def old_fallback(hand, hand_ang, turn_yaw, scale, prof, glob, lefthanded, mz):
    """Pre-refactor muzzle fallback (vieworg-relative offset)."""
    hx, hy, hz = hand
    c, s = math.cos(math.radians(turn_yaw)), math.sin(math.radians(turn_yaw))
    world = ((hx * c - hy * s) * scale,
             (hx * s + hy * c) * scale,
             hz * scale)
    angles = (hand_ang[0] + prof["pitch"],
              anglemod(hand_ang[1] + turn_yaw + prof["yaw"]),
              hand_ang[2] + prof["roll"])
    fwd, rt, up = angle_vectors(angles)
    barrel_len = mz[1] if mz[1] > 0.0 else 18.0
    off_fwd = glob["fwd"] + prof["grip"][0] + barrel_len
    off_rt = glob["rt"] + prof["grip"][1] + mz[0]
    off_up = glob["up"] + prof["grip"][2] + mz[2]
    return tuple(world[i] + fwd[i] * off_fwd + rt[i] * off_rt + up[i] * off_up
                 for i in range(3))


def new_fallback(hand, hand_ang, turn_yaw, view, scale, prof, glob, lefthanded, mz):
    """Post-refactor fallback: shared pose + barrel extension."""
    pose, angles = new_pose(hand, hand_ang, turn_yaw, view, scale, prof, glob, lefthanded)
    fwd, rt, up = angle_vectors(angles)
    barrel_len = mz[1] if mz[1] > 0.0 else 18.0
    return tuple((pose[i] - view[i]) + fwd[i] * barrel_len + rt[i] * mz[0] + up[i] * mz[2]
                 for i in range(3))


def main():
    rng = random.Random(0xB17E)
    worst_pose = 0.0
    worst_fb = 0.0
    worst_pose_ang = 0.0

    for _ in range(20000):
        hand = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6))
        hand_ang = (rng.uniform(-80, 80), rng.uniform(-180, 180), rng.uniform(-45, 45))
        turn_yaw = rng.uniform(-180, 180)
        view = (rng.uniform(-2000, 2000), rng.uniform(-2000, 2000), rng.uniform(-2000, 2000))
        scale = rng.uniform(20.0, 60.0)
        prof = {
            "grip": (rng.uniform(-10, 10), rng.uniform(-10, 10), rng.uniform(-10, 10)),
            "pitch": rng.uniform(-10, 10),
            "yaw": rng.uniform(-10, 10),
            "roll": rng.uniform(-10, 10),
        }
        glob = {
            "fwd": rng.uniform(-20, 20),
            "rt": rng.uniform(-20, 20),
            "up": rng.uniform(-20, 20),
        }
        mz = (rng.uniform(-5, 5), rng.uniform(0, 30), rng.uniform(-5, 5))

        op, oa = old_selector(hand, hand_ang, turn_yaw, view, scale, prof, glob, False)
        np_, na = new_pose(hand, hand_ang, turn_yaw, view, scale, prof, glob, False)
        worst_pose = max(worst_pose, max(abs(op[i] - np_[i]) for i in range(3)))
        worst_pose_ang = max(worst_pose_ang, max(abs(oa[i] - na[i]) for i in range(3)))

        of = old_fallback(hand, hand_ang, turn_yaw, scale, prof, glob, False, mz)
        nf = new_fallback(hand, hand_ang, turn_yaw, view, scale, prof, glob, False, mz)
        worst_fb = max(worst_fb, max(abs(of[i] - nf[i]) for i in range(3)))

    print(f"[verify] samples=20000")
    print(f"[verify] right-handed pose max delta   = {worst_pose:.6f} u")
    print(f"[verify] right-handed angles max delta = {worst_pose_ang:.6f} deg")
    print(f"[verify] right-handed fallback max delta = {worst_fb:.6f} u")

    ok = worst_pose < TOL and worst_pose_ang < TOL and worst_fb < TOL
    print("[verify] " + ("PASS: right-handed math unchanged" if ok else "FAIL: math changed"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
