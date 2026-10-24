#!/usr/bin/env python3
"""Static integrity + orientation check for the standalone two-hand model.

This gate runs entirely offline: it decompiles `models/v_hand.mdl` with the
canonical mdldec, then validates the two-hand structure, the Valve bone
naming convention and, most importantly, the *rendered* hand orientation.

Background: pxstudiomdl applies a built-in +90 degree Z rotation to the
animation (g_defaultrotation in studiomdl.cpp) while the reference bind uses
zero rotation, so the runtime transform of any authored vertex is:

    runtime = entity * Rz(+90) * authored

The authored SMD therefore has the fingers pointing roughly along -Y and the
palms facing -Z (both hands are authored palms-down). After the compiler's
+Rz(90) the model must end up fingers forward (+X), palms facing inward
(+Y for the right hand, -Y for the left) and thumbs up (+Z).

Any regression in the build pipeline (yaw, per-hand pitch, scale, bone
rename) fails this gate without needing the Monado runtime.

Exit code 0 = all checks passed, 1 = one or more failures.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

import smd_lib  # noqa: E402

# The compiler's built-in animation rotation: Rz(+90 degrees).
COMPILER_ROT = smd_lib.rot_z(math.pi / 2.0)

# Tolerance for the orientation dot products. The hands are authored with a
# small natural tilt, so we require the intended axis to dominate, not match
# exactly.
DOMINANCE = 0.5   # |intended component| must exceed DOMINANCE * |other axes|
SIGN_EPS = 0.15   # minimum absolute value for a signed axis assertion

EXPECTED_BONES = 35
REQUIRED_BONE_NAMES = [
    "Bip01 R Hand",
    "Bip01 L Hand",
    "Bip01 R Palm",
    "Bip01 L Palm",
    "Bip01 R Finger22",
    "Bip01 L Finger22",
    "Bip01 R Finger01",
    "Bip01 L Finger01",
]

FAILURES: list[str] = []
CHECKS = 0


def check(condition: bool, label: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  [PASS] {label}")
    else:
        print(f"  [FAIL] {label}" + (f"  ({detail})" if detail else ""))
        FAILURES.append(label)


def rt(v):
    """Apply the compiler's built-in rotation to an authored vector."""
    return smd_lib.mat_vec(COMPILER_ROT, v)


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def dominant_axis(v, axis: int, sign: int) -> tuple[bool, str]:
    other = [abs(v[i]) for i in range(3) if i != axis]
    ok = sign * v[axis] > 0 and abs(v[axis]) > DOMINANCE * max(other)
    return ok, f"v=({v[0]:.2f}, {v[1]:.2f}, {v[2]:.2f})"


def decompile(mdl_path: str, out_dir: str) -> None:
    mdldec = os.path.join(SCRIPT_DIR, "mdldec.sh")
    env = dict(os.environ)
    env["MDLDEC_ACT_PATH"] = os.path.join(REPO_DIR, "utils", "mdldec", "res")
    subprocess.run([mdldec, mdl_path, out_dir], check=True, env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def parse_bodygroups(qc_path: str) -> dict[str, list[str]]:
    """Return {bodygroup_name: [mesh names]} from the decompiled QC."""
    groups: dict[str, list[str]] = {}
    current = None
    with open(qc_path, encoding="latin1") as handle:
        for line in handle:
            m = re.search(r'\$bodygroup\s+"([^"]+)"', line)
            if m:
                current = m.group(1)
                groups[current] = []
                continue
            if current is not None:
                m = re.search(r'\bstudio\s+"([^"]+)"', line)
                if m:
                    groups[current].append(m.group(1))
                    continue
                if re.search(r'\bblank\b', line):
                    groups[current].append("blank")
                    continue
                if line.strip() == "}":
                    current = None
    return groups


def load_chain(out_dir: str, qc: str, chain_mesh: str) -> smd_lib.Smd:
    """Load the SMD for one chain mesh named in the QC bodygroup."""
    path = os.path.join(out_dir, chain_mesh + ".smd")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return smd_lib.parse_smd(path)


def landmark(smd: smd_lib.Smd, name: str):
    by_name = {n.name: n.index for n in smd.nodes}
    if name not in by_name:
        return None
    positions = smd_lib.world_positions(smd)
    return positions[by_name[name]]


def check_chain(side: str, prefix: str, palm_y_sign: int, smd: smd_lib.Smd,
                chain_mesh: str) -> None:
    print(f"\n-- {side.upper()} chain (mesh '{chain_mesh}', suffix {prefix}) --")

    names = [n.name for n in smd.nodes]
    check(len(names) == EXPECTED_BONES,
          f"{side}: {EXPECTED_BONES} bones",
          f"got {len(names)}")

    wrist = landmark(smd, f"Bip01 {prefix} Hand")
    palm = landmark(smd, f"Bip01 {prefix} Palm")
    tip = landmark(smd, f"Bip01 {prefix} Finger22")
    thumb = landmark(smd, f"Bip01 {prefix} Finger01")
    if not all((wrist, palm, tip, thumb)):
        check(False, f"{side}: landmark bones present",
              f"wrist={wrist is not None} palm={palm is not None} "
              f"tip={tip is not None} thumb={thumb is not None}")
        return
    check(True, f"{side}: landmark bones present")

    # Fingers point forward: runtime (fingertip - palm) must be +X dominant.
    finger_dir = rt(sub(tip, palm))
    ok, detail = dominant_axis(finger_dir, 0, +1)
    check(ok, f"{side}: fingers point forward (+X)", detail)

    # Thumb points up at runtime: (thumb - palm) must be +Z dominant.
    thumb_dir = rt(sub(thumb, palm))
    ok, detail = dominant_axis(thumb_dir, 2, +1)
    check(ok, f"{side}: thumb points up (+Z)", detail)

    # Palm faces inward. The thumb sits on the palm side, so the runtime
    # thumb offset along Y has the same sign as the palm normal.
    check(palm_y_sign * thumb_dir[1] > SIGN_EPS,
          f"{side}: palm faces inward (Y sign {'+' if palm_y_sign > 0 else '-'})",
          f"thumb.y={thumb_dir[1]:.2f}")

    # Reach sanity: wrist -> middle fingertip close to the canonical 6.4558.
    reach = math.dist(wrist, tip)
    check(5.8 <= reach <= 7.2, f"{side}: wrist->fingertip reach in range",
          f"reach={reach:.3f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.path.join(
        REPO_DIR, "assets", "valve_vr", "models", "v_hand.mdl"),
        help="path to the compiled v_hand.mdl")
    parser.add_argument("--keep", action="store_true",
                        help="keep the decompiled output for inspection")
    args = parser.parse_args()

    if not os.path.isfile(args.model):
        print(f"[FAIL] model not found: {args.model}")
        return 1

    print(f"Checking hand asset: {args.model}")
    out_dir = tempfile.mkdtemp(prefix="handcheck_")
    try:
        try:
            decompile(args.model, out_dir)
        except subprocess.CalledProcessError as exc:
            print(f"[FAIL] mdldec failed: {exc}")
            return 1

        qc_path = os.path.join(out_dir, "v_hand.qc")
        check(os.path.isfile(qc_path), "decompiled QC produced")
        groups = parse_bodygroups(qc_path)
        check(set(groups.keys()) == {"rhand", "lhand"},
              "two bodygroups 'rhand' and 'lhand'",
              f"got {sorted(groups.keys())}")

        # Each bodygroup holds two variants: the chain mesh and a blank one.
        # mdldec renders a nameless empty reference mesh as a synthetic "_N"
        # SMD (a skeleton with no triangles) instead of the literal `blank`
        # keyword, so identify the chain as the variant that actually has
        # geometry and the blank as the one that does not.
        def variants(group: str) -> list[str]:
            return list(groups.get(group, []))

        def is_geometry(mesh: str) -> bool:
            path = os.path.join(out_dir, mesh + ".smd")
            if not os.path.isfile(path):
                return False
            return len(smd_lib.parse_smd(path).triangles) > 0

        def classify(group: str) -> tuple[str | None, str | None]:
            geo, blank = None, None
            for m in variants(group):
                if m == "blank":
                    blank = "blank"
                    continue
                if is_geometry(m):
                    geo = m
                else:
                    blank = m
            return geo, blank

        right_mesh, right_blank = classify("rhand")
        left_mesh, left_blank = classify("lhand")

        check(right_mesh == "hand_r", "rhand bodygroup selects hand_r",
              f"got {right_mesh!r}")
        check(left_mesh == "hand_l", "lhand bodygroup selects hand_l",
              f"got {left_mesh!r}")
        check(right_blank is not None, "rhand bodygroup has an empty blank variant")
        check(left_blank is not None, "lhand bodygroup has an empty blank variant")
        check(len(variants("rhand")) == 2, "rhand bodygroup has 2 variants",
              f"got {variants('rhand')}")
        check(len(variants("lhand")) == 2, "lhand bodygroup has 2 variants",
              f"got {variants('lhand')}")

        right = load_chain(out_dir, qc_path, right_mesh or "hand_r")
        left = load_chain(out_dir, qc_path, left_mesh or "hand_l")

        for name in REQUIRED_BONE_NAMES:
            present = any(n.name == name for n in right.nodes) or \
                      any(n.name == name for n in left.nodes)
            check(present, f"bone present: {name}")

        # GoldSrc has +Y to the LEFT, so the right hand (on the -Y side) faces
        # inward toward +Y, and the left hand toward -Y.
        check_chain("right", "R", +1, right, right_mesh or "hand_r")
        check_chain("left", "L", -1, left, left_mesh or "hand_l")

        if args.keep:
            print(f"\nDecompiled output kept at: {out_dir}")
    finally:
        if not args.keep:
            shutil.rmtree(out_dir, ignore_errors=True)

    print("\n" + "=" * 58)
    print(f"Hand asset checks run: {CHECKS}   failures: {len(FAILURES)}")
    if FAILURES:
        print("FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("ALL HAND ASSET CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
