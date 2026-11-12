# OpenXR hand joint reference

There is no separate "OpenXR hand skeleton wiki" in this repository. The
specification equivalent of the OpenVR hand skeleton is the
`XR_EXT_hand_tracking` extension, whose default joint set has **26**
`XrHandJointEXT` joints (not the 31 bones of OpenVR).

| Joints | Names |
|---|---|
| 0-1 | `PALM`, `WRIST` |
| 2-5 | `THUMB_METACARPAL`, `THUMB_PROXIMAL`, `THUMB_DISTAL`, `THUMB_TIP` |
| 6-10 | `INDEX_METACARPAL` .. `INDEX_TIP` |
| 11-15 | `MIDDLE_METACARPAL` .. `MIDDLE_TIP` |
| 16-20 | `RING_METACARPAL` .. `RING_TIP` |
| 21-25 | `LITTLE_METACARPAL` .. `LITTLE_TIP` |

The enum is in `3rdparty/openxr/include/openxr/openxr.h` (`XrHandJointEXT`,
around lines 3002-3041). Beyond `XR_HAND_JOINT_SET_DEFAULT_EXT` there are
vendor/extended sets, for example the UltraLeap forearm set and Meta/FB/MSFT
variants.

## Project policy

- The **primary** naming reference for Stage 3 is this 26-joint OpenXR set.
  The OpenVR 31-bone enum (`Root`/`Wrist`/`Thumb0-3`/.../`Aux_*`) is a
  **secondary semantic guide** for names and indices only.
- The target device is the Meta Quest 3, whose input path is **OpenXR only**.
  No OpenVR runtime dependency may be added.
- This project does **not** consume `XR_EXT_hand_tracking` today. Hands are
  baked viewmodel hands plus procedural finger curl (`vr_finger_curling`,
  `vr_hand_pose_source`, `vr_hand_anim_blend`); see
  [`HAND_IK_AND_PHYSICS.md`](HAND_IK_AND_PHYSICS.md).
- `scripts/check_hand_skeleton_map.py` (`S2`) maps `v_hand.mdl` to the 26
  OpenXR joints by default; `--standard openvr` keeps the 31-name view.
  It is a static asset check, not a runtime integrator.

See [`PLAN.md`](../PLAN.md) Stage 3 and [`DECISIONS.md`](../DECISIONS.md) D-028.
