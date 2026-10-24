---
description: Run the VR regression battery
agent: build
---

Run the VR regression battery from the repository root.

```sh
./scripts/run_regression_battery.sh $ARGUMENTS
```

If `$ARGUMENTS` is empty, run all 18 gates. Report the evidence directory, the
PASS/FAIL count, and every failure with its gate name and log excerpt. Do not
summarize a failure as a pass.
