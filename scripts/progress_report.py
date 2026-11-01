#!/usr/bin/env python3
"""Print the current validation and task-progress marker.

The checklist source is the ``## Progress`` section of
``Documentation/vr/STATUS.md``. Gate freshness comes from the manifests under
``out/qa/<gate>/latest``. A gate is stale when its manifest commit does not
match HEAD or the working tree was dirty when it ran.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS = REPO_ROOT / "Documentation" / "vr" / "STATUS.md"
GATES = REPO_ROOT / "Documentation" / "vr" / "GATES.md"
QA_ROOT = REPO_ROOT / "out" / "qa"


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def parse_sections(text: str) -> dict[str, list[tuple[bool, str]]]:
    sections: dict[str, list[tuple[bool, str]]] = {}
    current: str | None = None
    in_progress = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_progress = line.strip() == "## Progress"
            current = None
            continue
        if not in_progress:
            continue
        if line.startswith("### "):
            current = line[4:].strip()
            sections[current] = []
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped.startswith("- [x] "):
            sections[current].append((True, stripped[6:]))
        elif stripped.startswith("- [ ] "):
            sections[current].append((False, stripped[6:]))
    return sections


def parse_active_gates(text: str) -> list[str]:
    gates = []
    for line in text.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        gate = cells[0].strip("`")
        status = cells[2]
        if status in {"active", "pending"}:
            gates.append(gate)
    return gates


def gate_states(head: str) -> tuple[dict[str, str], dict[str, dict]]:
    states: dict[str, str] = {}
    manifests: dict[str, dict] = {}
    if not QA_ROOT.exists():
        return states, manifests
    for gate_dir in sorted(p for p in QA_ROOT.iterdir() if p.is_dir()):
        manifest_path = gate_dir / "latest" / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            states[gate_dir.name] = "INVALID"
            continue
        manifests[gate_dir.name] = manifest
        if manifest.get("commit") != head or manifest.get("dirty"):
            states[gate_dir.name] = "STALE"
        else:
            states[gate_dir.name] = manifest.get("status", "UNKNOWN")
    return states, manifests


def format_section(name: str, items: list[tuple[bool, str]]) -> str:
    done = sum(1 for checked, _ in items if checked)
    total = len(items)
    remaining = total - done
    percent = (100 * done // total) if total else 0
    return f"{name:<28} {done}/{total} done ({percent}%), {remaining} remaining"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit 1 on FAIL or STALE gates")
    args = parser.parse_args()

    head = git_head()
    text = STATUS.read_text(encoding="utf-8", errors="replace")
    sections = parse_sections(text)
    active_gates = parse_active_gates(GATES.read_text(encoding="utf-8", errors="replace"))
    states, manifests = gate_states(head)

    print(f"HEAD {head[:12]}")
    print("")
    for name, items in sections.items():
        print(format_section(name, items))

    counts = {"PASS": 0, "FAIL": 0, "STALE": 0, "RUNNING": 0, "INCONCLUSIVE": 0, "UNKNOWN": 0}
    for gate in active_gates:
        state = states.get(gate, "PENDING")
        counts[state] = counts.get(state, 0) + 1

    print("")
    print(
        "Gates: "
        f"{counts.get('PASS', 0)} PASS, "
        f"{counts.get('FAIL', 0)} FAIL, "
        f"{counts.get('INCONCLUSIVE', 0)} INCONCLUSIVE, "
        f"{counts.get('STALE', 0)} STALE, "
        f"{counts.get('PENDING', 0)} PENDING"
    )

    missing = [gate for gate in active_gates if gate not in states]
    if missing:
        print("Pending gates: " + ", ".join(missing))

    current = next(
        (name for name in sections if name.lower().startswith("current task")),
        None,
    )
    if current:
        pending = [label for checked, label in sections[current] if not checked]
        if pending:
            print(f"Next step: {pending[0]}")
        else:
            print(f"Current task complete: {current}")

    if not states:
        print("No gate evidence found under out/qa.")
    else:
        stale_active = [gate for gate in active_gates if states.get(gate) == "STALE"]
        if stale_active:
            print("Warning: stale active gates: " + ", ".join(stale_active))

    if args.strict and (counts.get("FAIL", 0) or counts.get("STALE", 0)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
