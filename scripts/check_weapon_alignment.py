#!/usr/bin/env python3
"""Maintainer's simulator acceptance gate for weapon aim/barrel alignment.

A Quest 3 HIL run must not be requested while this gate is red, and it must
never be marked PASS from an older run. Three states are reported per weapon:

  PASS     authored visible barrel is within --max-angle of the firing/laser
           direction and the muzzle is in front of the eye;
  FAIL     measured and outside the acceptance criteria;
  UNKNOWN  no trustworthy measurement (missing telemetry, unstable samples,
           or a low-confidence authored basis). UNKNOWN is NOT a pass.
  N/A      weapon has no barrel (muzzle_attachment -1): melee, toss,
           placeable, hand. Excluded from every criterion.

Telemetry comes from [VR_AIM] in engine/platform/openxr/xr_input.c. The angle
is between the AUTHORED two-point barrel basis (attachment 0 "muzzle_pos" ->
attachment 2 "hud_pos"/"HUD_pos", world-space studio attachments) and the
direction the bullet/laser takes. The renderer aligns that same authored
basis to the aim direction, so the gate verifies the rendered geometry
against the firing ray rather than a self-confirming pair.

Usage:
    python3 scripts/check_weapon_alignment.py --log <engine.log>
        [--max-angle 8.0] [--min-weapons 6] [--ground-truth PATH]
        [--allow-unknown] [--json PATH]
Exit 0 = all criteria hold, 1 = at least one failed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b[@-Z\\-_]")
AIM_RE = re.compile(
    r"\[VR_AIM\]\s+model=(\S+)\s+angle=(N/A|MISSING|[-+0-9.eE]+)\s+in_front=(\d+)"
    r"(?:\s+barrel=\(([^)]*)\))?(?:\s+aim=\(([^)]*)\))?"
)


def _vec(text):
    if text is None:
        return None
    try:
        return [float(x) for x in text.split()]
    except ValueError:
        return None


def parse_log(text):
    """Keep the LAST sample per model; stale first-frame attachments are the
    cause of unstable readings right after a weapon is equipped."""
    text = ANSI_RE.sub("", text)
    samples: dict[str, list[dict]] = {}
    order: list[str] = []
    for line in text.splitlines():
        m = AIM_RE.search(line)
        if not m:
            continue
        model = m.group(1)
        raw = m.group(2)
        if model not in samples:
            samples[model] = []
            order.append(model)
        samples[model].append({
            "angle": None if raw in ("MISSING", "N/A") else float(raw),
            "state": raw,
            "in_front": int(m.group(3)),
            "barrel": _vec(m.group(4)),
            "aim": _vec(m.group(5)),
        })
    rows = {}
    for model in order:
        s = samples[model][-1]
        numeric = [x["angle"] for x in samples[model] if x["angle"] is not None]
        unstable = len(numeric) > 1 and (max(numeric) - min(numeric)) > 5.0
        rows[model] = {**s, "occurrences": len(samples[model]), "unstable": unstable,
                       "sample_angles": numeric}
    return rows, order


def load_ground_truth(path):
    if not path:
        return {}
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get("models", {})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", required=True)
    p.add_argument("--max-angle", type=float, default=8.0)
    p.add_argument("--min-weapons", type=int, default=6)
    p.add_argument("--ground-truth", default=None,
                   help="JSON from scripts/measure_bore_basis.py; low-confidence "
                        "authored bases are reported as UNKNOWN")
    p.add_argument("--allow-unknown", action="store_true",
                   help="For Bronze-tier mods: UNKNOWN rows do not fail the gate "
                        "but are still reported and never counted as passes")
    p.add_argument("--json", dest="json_path", default=None)
    a = p.parse_args()

    log_path = Path(a.log)
    if not log_path.is_file():
        print(f"[FAIL] log not found: {a.log}")
        return 1

    rows, order = parse_log(log_path.read_text(encoding="utf-8", errors="replace"))
    gt = load_ground_truth(a.ground_truth)
    ma, mw = a.max_angle, a.min_weapons
    failing, unknown, measured = [], [], []

    for model in order:
        r = rows[model]
        name = Path(model).name

        # Ground truth from the offline bone-position measurement. A model
        # whose authored basis is LOW confidence cannot be trusted as PASS.
        confidence = None
        if gt:
            entry = gt.get(name) or gt.get(model)
            if isinstance(entry, dict):
                confidence = entry.get("confidence")

        if r["state"] == "N/A":
            r["verdict"] = "N/A"
            continue

        measured.append(model)
        if r["state"] == "MISSING" or r["angle"] is None:
            r["verdict"] = "UNKNOWN"
            unknown.append((model, "missing barrel/aim telemetry"))
            continue
        if r["unstable"]:
            r["verdict"] = "UNKNOWN"
            unknown.append((model, "unstable samples "
                            f"{[round(x, 1) for x in r['sample_angles']]}"))
            continue
        if confidence in ("LOW", "NO_REAR_ANCHOR"):
            r["verdict"] = "UNKNOWN"
            unknown.append((model, f"low-confidence authored basis ({confidence})"))
            continue
        if r["in_front"] != 1:
            r["verdict"] = "FAIL"
            failing.append((model, f"forward weapon (in_front={r['in_front']})"))
            continue
        if r["angle"] > ma:
            r["verdict"] = "FAIL"
            failing.append((model, f"barrel/laser alignment "
                            f"(angle={r['angle']:.1f} > {ma})"))
            continue
        r["verdict"] = "PASS"

    na = [m for m in order if rows[m]["verdict"] == "N/A"]
    passes = [m for m in order if rows[m]["verdict"] == "PASS"]
    unknown_ok = bool(a.allow_unknown)
    criteria = {
        "coverage": len(measured) >= mw,
        "no_fail": not failing,
        "no_unknown": unknown_ok or not unknown,
    }
    ok = all(criteria.values())

    print(f"{'model':<40} {'angle':>8} {'in_front':>9}  verdict")
    print("-" * 62)
    for model in order:
        r = rows[model]
        ang = r["state"] if r["angle"] is None else f"{r['angle']:.1f}"
        print(f"{model:<40} {ang:>8} {r['in_front']:>9}  {r['verdict']}")
    print()
    if ok:
        print(f"[PASS] {len(passes)} weapons aligned (angle <= {ma}, in_front=1), "
              f"{len(na)} N/A (no barrel), no UNKNOWN")
    else:
        print("[FAIL] acceptance criteria not met:")
        if not criteria["coverage"]:
            print(f"  - coverage: only {len(measured)} measurable weapons (need {mw})")
        for model, reason in failing:
            print(f"  - {model}: {reason}")
        if unknown and not unknown_ok:
            for model, reason in unknown:
                print(f"  - {model}: UNKNOWN ({reason})")
    if unknown and unknown_ok:
        print(f"\nnote: {len(unknown)} UNKNOWN rows allowed by --allow-unknown "
              "(Bronze tier); these are NOT passes.")
    print(f"\nsummary: distinct={len(order)} measurable={len(measured)} "
          f"pass={len(passes)} fail={len(failing)} unknown={len(unknown)} "
          f"n_a={len(na)}")

    if a.json_path:
        report = {
            "models": {m: {k: rows[m][k] for k in
                           ("angle", "state", "in_front", "barrel", "aim",
                            "occurrences", "unstable", "verdict")}
                       for m in order},
            "summary": {"distinct_models": len(order), "measurable": len(measured),
                        "pass": len(passes), "fail": len(failing),
                        "unknown": len(unknown), "n_a": len(na),
                        "min_weapons": mw, "max_angle": ma,
                        "allow_unknown": unknown_ok,
                        "failing_models": [{"model": m, "reason": r} for m, r in failing],
                        "unknown_models": [{"model": m, "reason": r} for m, r in unknown],
                        "criteria": criteria},
            "status": "PASS" if ok else "FAIL",
        }
        out = Path(a.json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
