---
description: Capture weapon turntable and animation GIFs for human review
agent: build
---

Run the non-blocking weapon visual review from the repository root:

```sh
./scripts/compare_weapon_review.sh $ARGUMENTS
```

If no arguments are given, compare the patched Glock against the original
MMOD Glock. The command writes labelled GIFs and a contact sheet under
`out/qa/V1/compare_glock/`.

Report the comparison directory and the artifact paths. This is a human review
aid, not a gate: do not mark a stage failed because the visual review is
pending, and do not deploy the model.
