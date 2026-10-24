---
description: Run the Monado OpenXR unit suite
agent: build
---

Run the Monado OpenXR unit suite from the repository root.

If `$ARGUMENTS` is empty, run the full 43-gate suite:

```sh
./scripts/test_simulated_monado.sh
```

Otherwise pass the arguments through unchanged (for example, a single map name).

Report the evidence directory, the gate count, and every FAIL line. If the
suite cannot start, report the exact missing prerequisite instead of guessing.
