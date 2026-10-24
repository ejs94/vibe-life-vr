---
description: Run the Meta Quest hardware-in-the-loop gate
agent: quest-tester
---

Run the Quest HIL gate. Load the `xash-vr-quest` skill first.

If `$ARGUMENTS` is empty, use `25 crossfire`; otherwise pass the arguments
through unchanged.

1. Check `quest doctor` and `quest state`. Unlock the headset if needed.
2. If the APK or VR assets changed since the last run, rebuild and deploy them
   before testing.
3. Run `./scripts/test_quest_auto.sh $ARGUMENTS`.
4. Report the evidence directory, the pass/fail lines, and whether
   `vr_eye0.png` contains a non-black rendered frame.

Do not edit source files. Do not claim a pass from `screencap_os.png`; it is
expected to be black in VR.
