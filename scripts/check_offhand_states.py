#!/usr/bin/env python3
"""Validate baked-support vs free-blocky offhand states."""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

MARK_RE = re.compile(r"OFFHAND_BEGIN\s+(\w+)\s+(support_baked|free_block)")
STATE_RE = re.compile(r"\[VR_HAND_STATE\]\s+model=(\S+)\s+baked_primary=(\d)\s+baked_offhand=(\d)")
POSE_RE = re.compile(r"\[HAND_POSE\]\s+ent=(\w+).*?grip_dist=([-\d.]+)\s+grip_lock=(\d+)")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_offhand_states.py <log>")
        return 2
    text = Path(sys.argv[1]).read_text(encoding="latin1", errors="replace")
    lines = text.splitlines()

    sections = []
    current = None
    last_state = None
    for line in lines:
        sm = STATE_RE.search(line)
        if sm:
            last_state = {"model": sm.group(1), "baked_primary": int(sm.group(2)),
                          "baked_offhand": int(sm.group(3))}
        m = MARK_RE.search(line)
        if m:
            current = {"weapon": m.group(1), "state": m.group(2),
                       "poses": [], "baked_offhand": last_state["baked_offhand"] if last_state else None}
            sections.append(current)
            continue
        if current is None:
            continue
        p = POSE_RE.search(line)
        if p:
            current["poses"].append({"ent": p.group(1), "grip_dist": float(p.group(2)),
                                     "grip_lock": int(p.group(3))})

    failures = []
    matrix = defaultdict(dict)
    for sec in sections:
        weapon, state = sec["weapon"], sec["state"]
        matrix[weapon][state] = sec
        if state == "free_block":
            off = [p for p in sec["poses"] if p["ent"] == "offhand"]
            pri = [p for p in sec["poses"] if p["ent"] == "primary"]
            if not pri:
                failures.append(f"{weapon}/free_block: no primary hand sample")
            if not off:
                failures.append(f"{weapon}/free_block: no offhand sample")
            elif any(p["grip_dist"] > 0.25 or p["grip_lock"] != 0 for p in off):
                failures.append(f"{weapon}/free_block: offhand is not free "
                                f"(grip_dist={off[0]['grip_dist']:.3f}, lock={off[0]['grip_lock']})")
        elif state == "support_baked":
            if sec["baked_offhand"] is None:
                failures.append(f"{weapon}/support_baked: missing baked-hand state log")
            elif sec["baked_offhand"] == 0:
                # Explicitly unavailable, not a false pass.
                matrix[weapon]["support_baked"] = "n/a"

    for weapon in sorted(matrix):
        free = "ok" if "free_block" in matrix[weapon] else "missing"
        support = matrix[weapon].get("support_baked", "missing")
        support_label = "n/a" if support == "n/a" else ("available" if isinstance(support, dict) else support)
        print(f"  {weapon:16} free={free:7} baked_support={support_label}")

    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OFFHAND STATE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
