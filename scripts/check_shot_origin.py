#!/usr/bin/env python3
"""Verify where a VR shot starts and whether it follows the visible barrel.

Per weapon segment (marker `SHOT_PROBE weapon=...`) the engine logs:

  [VR_IMPACT_DBG] Shot #N start=(x y z) hit at (...) dist=... normal=(...)
  [VR_GRIP] src=muzzle model=... world=(x y z) angles=(...)
  [VR_ANCHOR] bone=... delta=(...) palm=(x y z)

The shot must start at the muzzle attachment (not at the eye and not at the
hand), and the shot direction must follow an INDEPENDENT bore axis derived from
the weapon body hitbox (check_weapon_bore.py), not the muzzle_pos ->
muzzle_pos2 pair that defines the firing line. Comparing against that pair is
circular and always reports zero degrees. Palm -> muzzle is only the fallback
for models without a body hitbox. A sideways or downward start is what makes a
VR shot look crooked even when the viewmodel is aligned.

Usage:
    python3 scripts/check_shot_origin.py <engine.log>
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

# Importing a sibling helper must not leave bytecode in scripts/, which the
# evidence-hygiene gate H1 rejects.
sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from check_weapon_bore import diagnose_model, profile_muzzles as bore_profile_muzzles
    from check_weapon_bore import NATIVE_DIR as BORE_NATIVE_DIR
except Exception:  # pragma: no cover - optional dependency
    diagnose_model = None
    bore_profile_muzzles = None
    BORE_NATIVE_DIR = None

REPO_ROOT = Path(__file__).resolve().parent.parent

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
MARK = re.compile(r"SHOT_PROBE weapon=(\w+)")
IMPACT = re.compile(
    r"\[VR_IMPACT_DBG\]\s+Shot #\d+\s+(?:reported_start=\(([^)]+)\)\s+)?"
    r"start=\(([^)]+)\)\s+hit at \(([^)]+)\)"
)
MUZZLE = re.compile(
    r"\[VR_GRIP\]\s+src=muzzle\s+model=(\S+).*?world=\(([^)]+)\)"
    r"(?:.*?bore2=\(([^)]+)\))?(?:.*?angles=\(([^)]+)\))?"
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


def angle_vectors(angles):
    """GoldSrc AngleVectors: return (forward, right, up) for (pitch, yaw, roll)."""
    pitch, yaw, roll = (math.radians(a) for a in angles)
    sp, cp = math.sin(pitch), math.cos(pitch)
    sy, cy = math.sin(yaw), math.cos(yaw)
    sr, cr = math.sin(roll), math.cos(roll)
    forward = (cp * cy, cp * sy, -sp)
    right = (-sr * sp * cy - cr * -sy,
             -sr * sp * sy - cr * cy,
             -sr * cp)
    up = (cr * sp * cy - sr * -sy,
          cr * sp * sy - sr * cy,
          cr * cp)
    return forward, right, up


def rotate_model_to_world(vec_model, angles):
    """Rotate a model-space vector into world space using an AngleVectors basis."""
    forward, right, up = angle_vectors(angles)
    return (
        vec_model[0] * forward[0] + vec_model[1] * right[0] + vec_model[2] * up[0],
        vec_model[0] * forward[1] + vec_model[1] * right[1] + vec_model[2] * up[1],
        vec_model[0] * forward[2] + vec_model[1] * right[2] + vec_model[2] * up[2],
    )


def resolve_independent_axis(model_name, angles):
    """Return (world_axis_tuple, None) or (None, reason)."""
    if diagnose_model is None:
        return None, "diagnose_model unavailable"
    if not model_name:
        return None, "no model in log"
    basename = Path(model_name).name
    mdl_path = None
    candidates = []
    if BORE_NATIVE_DIR is not None:
        p = BORE_NATIVE_DIR / basename
        if p.is_file():
            candidates.append(p)
    # Search the valve_vr models tree as a fallback.
    models_root = REPO_ROOT / "assets" / "valve_vr" / "models"
    if not candidates and models_root.is_dir():
        for p in models_root.rglob(basename):
            candidates.append(p)
            break
    if not candidates:
        return None, "model file not found"
    mdl_path = candidates[0]
    try:
        muzzles = bore_profile_muzzles() if bore_profile_muzzles else {}
    except Exception:
        muzzles = {}
    ma = muzzles.get(basename)
    try:
        row = diagnose_model(mdl_path, ma)
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"diagnose failed: {exc}"
    if "barrel" not in row:
        return None, row.get("note", row.get("state", "no bore_axis"))
    bore_axis = row["barrel"]
    if angles is not None and any(abs(v) > 1e-9 for v in angles):
        world_axis = rotate_model_to_world(bore_axis, angles)
    else:
        world_axis = tuple(float(x) for x in bore_axis)
    n = norm(world_axis)
    if all(abs(v) < 1e-9 for v in n):
        return None, "degenerate bore_axis"
    return n, None


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
                                          "palm": None, "bore2": None, "model": None,
                                          "angles": None, "reported_start": None})
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
            segments[current]["model"] = muzzle.group(1)
            segments[current]["muzzle"] = vec(muzzle.group(2))
            if muzzle.group(3):
                segments[current]["bore2"] = vec(muzzle.group(3))
            if muzzle.group(4):
                segments[current]["angles"] = vec(muzzle.group(4))
            continue

        impact = IMPACT.search(line)
        if impact:
            shots += 1
            if segments[current]["start"] is None:
                # group(1) is reported_start (optional), group(2) start, group(3) hit
                if impact.group(1):
                    segments[current]["reported_start"] = vec(impact.group(1))
                segments[current]["start"] = vec(impact.group(2))
                segments[current]["hit"] = vec(impact.group(3))

    failures: list[str] = []
    rows = []
    for weapon, data in segments.items():
        start, hit, muzzle_w, palm_w = data["start"], data["hit"], data["muzzle"], data["palm"]
        if not all((start, hit, muzzle_w, palm_w)):
            failures.append(f"{weapon}: missing telemetry (start/hit/muzzle/palm)")
            continue

        start_error = length(sub(start, muzzle_w))

        # Independent bore axis: derived from the weapon body hitboxes via
        # check_weapon_bore.diagnose_model, NOT from the muzzle_pos->muzzle_pos2
        # pair (which is the same pair xr_input uses to define the firing line).
        angles = data.get("angles")
        axis, reason = resolve_independent_axis(data.get("model"), angles)
        reported_start = data.get("reported_start")

        if reason is not None:
            status = "FAIL"
            failures.append(f"{weapon}: INDEPENDENT_AXIS_UNAVAILABLE ({reason})")
            shot = norm(sub(hit, start))
            angle = float("nan")
            offset = float("nan")
            barrel = (0.0, 0.0, 1.0)
            axis_origin = muzzle_w
            dpitch = 0.0
            dyaw = 0.0
        else:
            barrel = axis
            # Keep the axis-offset check anchored at the muzzle when the
            # independent axis is available.
            axis_origin = muzzle_w
            shot = norm(sub(hit, start))
            cosine = max(-1.0, min(1.0, dot(barrel, shot)))
            angle = math.degrees(math.acos(cosine))

            # Perpendicular distance from the shot start to the barrel line.
            delta = sub(start, axis_origin)
            along = dot(delta, barrel)
            offset = length(sub(delta, tuple(barrel[i] * along for i in range(3))))

            barrel_pitch = math.degrees(math.asin(max(-1.0, min(1.0, -barrel[2]))))
            shot_pitch = math.degrees(math.asin(max(-1.0, min(1.0, -shot[2]))))
            barrel_yaw = math.degrees(math.atan2(barrel[1], barrel[0]))
            shot_yaw = math.degrees(math.atan2(shot[1], shot[0]))
            dpitch = shot_pitch - barrel_pitch
            dyaw = shot_yaw - barrel_yaw

            tol = TOLERANCES.get(weapon, DEFAULT_TOL)
            status = "PASS"
            if start_error > tol["start"]:
                status = "FAIL"
                failures.append(f"{weapon}: shot starts {start_error:.1f}u from the muzzle")
            if angle > tol["angle"]:
                status = "FAIL"
                failures.append(f"{weapon}: shot is {angle:.1f}deg off the independent bore axis")
            if offset > tol["axis"]:
                status = "FAIL"
                failures.append(f"{weapon}: shot start is {offset:.1f}u off the barrel axis")

        tol = TOLERANCES.get(weapon, DEFAULT_TOL)
        if status == "PASS" and start_error > tol["start"]:
            status = "FAIL"

        rows.append({
            "weapon": weapon,
            "start_error": start_error,
            "angle": angle,
            "offset": offset,
            "status": status,
            "dpitch": dpitch,
            "dyaw": dyaw,
            "reported_start": reported_start,
            "independent": reason is None,
        })

    print(f"{'weapon':<22} {'start->muzzle':>13} {'vs barrel':>10} {'axis':>6} {'dpitch':>7} {'dyaw':>7}  status")
    for r in rows:
        angle = r["angle"]
        offset = r["offset"]
        angle_s = f"{angle:10.2f}" if angle == angle else "       nan"
        offset_s = f"{offset:6.2f}" if offset == offset else "   nan"
        print(f"{r['weapon']:<22} {r['start_error']:>13.2f} {angle_s} {offset_s} "
              f"{r['dpitch']:>7.2f} {r['dyaw']:>7.2f}  {r['status']}")
        if r.get("reported_start") is not None:
            rs = r["reported_start"]
            print(f"  reported_start=({rs[0]:.2f}, {rs[1]:.2f}, {rs[2]:.2f})")

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
