---
description: Runs one read-only gate from Documentation/vr/GATES.md and records its evidence
mode: subagent
permissions:
  - action: edit
    resource: "*"
    effect: deny
  - action: shell
    resource: "*"
    effect: ask
  - action: shell
    resource: "scripts/*"
    effect: allow
  - action: shell
    resource: "./scripts/*"
    effect: allow
  - action: shell
    resource: "bash scripts/*"
    effect: allow
  - action: shell
    resource: "python3 scripts/*"
    effect: allow
  - action: shell
    resource: "git status *"
    effect: allow
  - action: shell
    resource: "git rev-parse *"
    effect: allow
---

Run exactly one gate from `Documentation/vr/GATES.md`.

Before doing anything:

1. Read `AGENTS.md`.
2. Read `Documentation/vr/GATES.md` and locate the requested gate ID.
3. Read `Documentation/vr/STATUS.md` to confirm the current baseline.

Then:

- Run only the command in that gate row, from the repository root.
- If the command supports `scripts/qa_evidence.py`, use it to create and finish
  the run under `out/qa/<gate-id>/`.
- Do not substitute a proxy check or an older run.
- Do not edit source, docs, assets, scripts, or configuration.
- Do not decide whether Quest hardware is required. That is the maintainer's
  decision.
- Report `PASS`, `FAIL` or `INCONCLUSIVE`, the exact command, the evidence path,
  and the key log lines. Separate facts from inference.
