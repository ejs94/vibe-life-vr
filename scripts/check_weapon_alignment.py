#!/usr/bin/env python3
"""Maintainer's simulator acceptance gate for weapon aim/barrel alignment.

This is the maintainer's simulator acceptance gate. It is deliberately
expected to FAIL until the visible barrel, the laser/firing direction and the
hands are aligned; a Quest 3 HIL run must not be requested while it is red;
never mark it PASS from an older run.

Parses [VR_AIM] telemetry from engine/platform/openxr/xr_input.c and checks:
  1. >= --min-weapons distinct models with a numeric angle;
  2. no row has angle=MISSING;
  3. every numeric angle <= --max-angle degrees;
  4. every row has in_front == 1.
angle = degrees between authored visible barrel (attachment 0 -> 2) and aim
forward. in_front = 1 when muzzle lies in front of eye along aim direction.

Usage: python3 scripts/check_weapon_alignment.py --log <engine.log>
       [--max-angle 8.0] [--min-weapons 6] [--json PATH]
Exit 0 = all criteria hold, 1 = at least one failed.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b[@-Z\\-_]")
AIM_RE = re.compile(r"\[VR_AIM\]\s+model=(\S+)\s+angle=(MISSING|[-+0-9.eE]+)\s+in_front=(\d+)(?:\s+barrel=\(([^)]*)\))?(?:\s+aim=\(([^)]*)\))?")


def _vec(t):
    if t is None:
        return None
    try:
        return [float(x) for x in t.split()]
    except ValueError:
        return None


def parse_log(text):
    text = ANSI_RE.sub("", text)
    rows, order, dups = {}, [], []
    for line in text.splitlines():
        m = AIM_RE.search(line)
        if not m:
            continue
        model, raw, inf = m.group(1), m.group(2), int(m.group(3))
        if model in rows:
            dups.append(model)
            continue
        angle = None if raw == "MISSING" else float(raw)
        rows[model] = {"angle": angle, "in_front": inf, "barrel": _vec(m.group(4)),
                       "aim": _vec(m.group(5)), "occurrences": 1}
        order.append(model)
    counts = {}
    for line in text.splitlines():
        m = AIM_RE.search(line)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    for m in rows:
        rows[m]["occurrences"] = counts.get(m, 1)
    return rows, order, dups


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", required=True)
    p.add_argument("--max-angle", type=float, default=8.0)
    p.add_argument("--min-weapons", type=int, default=6)
    p.add_argument("--json", dest="json_path", default=None)
    a = p.parse_args()
    path = Path(a.log)
    if not path.is_file():
        print(f"[FAIL] log not found: {a.log}")
        return 1
    rows, order, dups = parse_log(path.read_text(encoding="utf-8", errors="replace"))
    ma, mw = a.max_angle, a.min_weapons
    failing = []
    for m in order:
        r = rows[m]
        if r["angle"] is None:
            r["verdict"] = "FAIL"
            failing.append((m, "missing barrel/aim telemetry (angle=MISSING)"))
            continue
        if r["in_front"] != 1:
            r["verdict"] = "FAIL"
            failing.append((m, f"forward weapon (in_front={r['in_front']})"))
            continue
        if r["angle"] > ma:
            r["verdict"] = "FAIL"
            failing.append((m, f"barrel/laser alignment (angle={r['angle']:.1f} > {ma})"))
            continue
        r["verdict"] = "PASS"
    numeric = sum(1 for m in order if rows[m]["angle"] is not None)
    missing = [m for m in order if rows[m]["angle"] is None]
    behind = [m for m in order if rows[m]["in_front"] != 1]
    criteria = {"coverage": numeric >= mw, "no_missing": not missing,
                "angle": all(rows[m]["angle"] is None or rows[m]["angle"] <= ma for m in order),
                "in_front": not behind}
    cov_fail = (f"coverage: only {numeric} distinct weapons with numeric angle (need {mw})"
                if not criteria["coverage"] else None)
    ok = all(criteria.values()) and not failing
    print(f"{'model':<40} {'angle':>8} {'in_front':>9}  verdict")
    print("-" * 62)
    for m in order:
        r = rows[m]
        ang = "MISSING" if r["angle"] is None else f"{r['angle']:.1f}"
        print(f"{m:<40} {ang:>8} {r['in_front']:>9}  {r['verdict']}")
    if dups:
        print(f"\nnote: duplicate [VR_AIM] lines for: {', '.join(sorted(set(dups)))}")
    print()
    if ok:
        print(f"[PASS] {numeric} distinct weapons, all angle <= {ma}, in_front=1, no MISSING")
    else:
        print("[FAIL] acceptance criteria not met:")
        if cov_fail:
            print(f"  - {cov_fail}")
        if missing:
            print(f"  - missing telemetry (angle=MISSING): {', '.join(missing)}")
        for m, r in failing:
            if r.startswith("barrel/laser") or r.startswith("forward weapon"):
                print(f"  - {m}: {r}")
    print(f"\nsummary: distinct={len(order)} numeric={numeric} missing={len(missing)} behind={len(behind)}")
    if a.json_path:
        models_json = {m: {"angle": rows[m]["angle"], "in_front": rows[m]["in_front"],
                           "barrel": rows[m]["barrel"], "aim": rows[m]["aim"],
                           "occurrences": rows[m]["occurrences"], "verdict": rows[m]["verdict"]}
                  for m in order}
        report = {"models": models_json,
                  "summary": {"distinct_models": len(order), "numeric_models": numeric,
                              "min_weapons": mw, "max_angle": ma,
                              "missing_models": missing, "behind_models": behind,
                              "failing_models": [{"model": m, "reason": r} for m, r in failing],
                              "coverage_failure": cov_fail, "criteria": criteria},
                  "status": "PASS" if ok else "FAIL"}
        out = Path(a.json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
