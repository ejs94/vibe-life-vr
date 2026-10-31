---
description: Show current gate validation and remaining task steps
agent: build
---

Run the progress marker from the repository root:

```sh
python3 scripts/progress_report.py
```

Report the baseline, validation and current-task counts exactly as printed.
Do not infer a pass from a stale or missing gate. If `--strict` is used, treat
a `FAIL` or `STALE` gate as a blocker.
