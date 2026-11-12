#!/usr/bin/env python3
"""Mutation-test the M1 assertions against a real engine log."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ASSERT_RE = re.compile(
    r'assert_test\s+(\d+)\s+"([^"]*)"\s*\\\s*\n\s*\'([^\']*)\'',
    re.MULTILINE,
)

MUTATIONS = [
    ("M1", "remove [VR_GRIP] lines", lambda lines: [ln for ln in lines if "[VR_GRIP]" not in ln]),
    ("M2", "remove [VR_MENU] lines", lambda lines: [ln for ln in lines if "[VR_MENU]" not in ln]),
    ("M3", "remove Head flashlight toggled lines", lambda lines: [ln for ln in lines if "Head flashlight toggled" not in ln]),
    ("M4", "remove ALL MONADO UNIT TEST PHASES COMPLETED lines", lambda lines: [ln for ln in lines if "ALL MONADO UNIT TEST PHASES COMPLETED" not in ln]),
    ("M5", "truncate to first 20 lines", lambda lines: lines[:20]),
]


def parse_assertions(script_path: Path) -> list:
    text = script_path.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in ASSERT_RE.finditer(text):
        out.append((int(m.group(1)), m.group(2), m.group(3)))
    return out


def run_condition(condition: str, env: dict) -> bool:
    cmd = "if " + condition + "; then exit 0; else exit 1; fi"
    try:
        proc = subprocess.run(
            ["bash", "-c", cmd],
            env=env,
            timeout=10,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except OSError:
        return False


def evaluate_all(assertions, log_path: Path, captures: Path, script_dir: Path, repo_dir: Path) -> dict:
    results = {}
    env = dict(os.environ)
    env["TEST_LOG"] = str(log_path)
    env["OUTPUT_DIR"] = str(captures)
    env["SCRIPT_DIR"] = str(script_dir)
    env["REPO_DIR"] = str(repo_dir)
    env["RUN_EXIT"] = "0"
    env["CAPTURED_IMAGES"] = str(len(list(captures.glob("*.png"))))
    for aid, _desc, cond in assertions:
        results[aid] = run_condition(cond, env)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--captures", required=True)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    script_path = Path(args.script).resolve()
    log_path = Path(args.log).resolve()
    captures = Path(args.captures).resolve()
    script_dir = script_path.parent
    repo_dir = script_path.parent.parent

    assertions = parse_assertions(script_path)
    if not assertions:
        print("No assertions parsed", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        baseline_log = td_path / "baseline.log"
        shutil.copyfile(log_path, baseline_log)
        baseline_results = evaluate_all(assertions, baseline_log, captures, script_dir, repo_dir)

        mutation_results = {mid: {} for mid, _, _ in MUTATIONS}
        for mid, _label, mut in MUTATIONS:
            mut_log = td_path / (mid + ".log")
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            mutated = mut(lines)
            mut_log.write_text("".join(mutated), encoding="utf-8")
            res = evaluate_all(assertions, mut_log, captures, script_dir, repo_dir)
            for aid, _desc, _cond in assertions:
                mutation_results[mid][aid] = res[aid]

    records = []
    robust_count = 0
    baseline_passing = 0
    for aid, desc, _cond in assertions:
        base_pass = baseline_results[aid]
        classification = "UNTESTABLE"
        flipping = "none"
        if base_pass:
            baseline_passing += 1
            flipped = False
            for mid, _label, _mut in MUTATIONS:
                if not mutation_results[mid][aid]:
                    flipped = True
                    flipping = mid
                    break
            if flipped:
                classification = "ROBUST"
                robust_count += 1
            else:
                classification = "INSENSITIVE"
        records.append({
            "id": aid,
            "description": desc,
            "baseline": "PASS" if base_pass else "FAIL",
            "classification": classification,
            "flipping_mutation": flipping,
            "mutations": {mid: ("PASS" if mutation_results[mid][aid] else "FAIL") for mid, _, _ in MUTATIONS},
        })

    print("{:>3} | {:8} | {:12} | flipping mutation".format("id", "baseline", "classification"))
    print("-" * 60)
    for r in records:
        print("{:>3} | {:8} | {:12} | {}".format(r["id"], r["baseline"], r["classification"], r["flipping_mutation"]))

    robust_pct = (100.0 * robust_count / baseline_passing) if baseline_passing else 0.0
    counts = {"ROBUST": 0, "INSENSITIVE": 0, "UNTESTABLE": 0}
    for r in records:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    print("")
    print("Baseline-passing: {}".format(baseline_passing))
    print("ROBUST: {}".format(counts.get("ROBUST", 0)))
    print("INSENSITIVE: {}".format(counts.get("INSENSITIVE", 0)))
    print("UNTESTABLE: {}".format(counts.get("UNTESTABLE", 0)))
    print("Robust %: {:.1f}%".format(robust_pct))

    payload = {
        "script": str(script_path),
        "log": str(log_path),
        "captures": str(captures),
        "assertions": records,
        "summary": {
            "baseline_passing": baseline_passing,
            "robust": counts.get("ROBUST", 0),
            "insensitive": counts.get("INSENSITIVE", 0),
            "untestable": counts.get("UNTESTABLE", 0),
            "robust_pct": robust_pct,
        },
    }
    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("JSON written: {}".format(out_path))

    exit_code = 0
    if robust_pct < 60.0:
        exit_code = 1
    rec38 = next((r for r in records if r["id"] == 38), None)
    if rec38 is not None and rec38["classification"] == "INSENSITIVE":
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
