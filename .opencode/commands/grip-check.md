---
description: Verify grip pose math, seating, and the hand asset
agent: build
---

Run the grip and hand asset checks from the repository root.

1. `python3 scripts/verify_grip_pose_math.py` - right-handed pose math must stay
   within `1e-4` of the pre-refactor formulas.
2. `python3 scripts/check_hand_asset.py` - validates the standalone two-hand
   model, bone naming, and rendered orientation.
3. If `$ARGUMENTS` contains a log path, run
   `python3 scripts/check_grip_seat.py <log>` and
   `python3 scripts/check_grip_pose.py <log>` to verify the probe lines.
   Without a log, say which checks were skipped and why.

Report the maximum pose deviation, every weapon whose seat error exceeds `0.001`
units, and any hand-asset failure. Do not change `grip_offset` without probe
evidence and a before/after seating result.
