# Plan

Single plan of truth for stages and blockers. `STATUS.md` tracks current
state; `GATES.md` lists gate commands.

## Purpose

- Point readers to `STATUS.md` for current state and `GATES.md` for commands.
- One stage per session; end with a short handoff.

## Invariants

- D-002: `XR_GetWeaponPose()` is the single pose source.
- D-003: the baked hand is authoritative.
- D-004: no new viewmodel bones; append attachments only.
- D-027: the bore is the runtime grip->muzzle bone vector; `A9` is an asset
  diagnostic only.
- Green gates do not prove appearance; HIL confirmation required for visual changes.

## Blocker register

| Blocker | Evidence | Gate | Exit criterion |
|---|---|---|---|
| Bore axis | `V3` 6/6 at 0.0deg, `R2` roll 0/45/90/180 at 0.0deg | `V3` + `R2` + M1 53 (green) | two-handed headset confirmation |
| Hand skeleton semantics | `v_hand.mdl` layout differs | `S1`/`A3`/`A4` | rig axis + name map, no re-skin; OpenVR enum is a guide only |
| Quest freshness | `Q1` 2026-11-07 | `Q1` | fresh run on maintainer request |
| Test integrity | `M1` log greps | `T1` | negative control passes |

## Stage 1 bore axis (BLOCKED on VR-ready assets)

- D-031: `vr_anchor_rotation` is OFF. `R_VR_RotateViewmodelToPalm` is retained
  only as an A/B switch; forcing any proxy bone vector onto the aim ray rotated
  the model 33-94deg and detached the baked hand. The viewmodel follows the
  controller pose, as `VRHelper::UpdateViewEnt` does in the reference mods.
- Engine-side alignment is CLOSED as an approach. The reference mods do not
  compute a bore axis: they author the model and its attachments together, then
  copy the controller pose. We adopted third-party SD assets that were never
  authored for VR.
- **Stage 1 is now an ASSET stage, not an engine stage.** `F1` holds the
  per-class fallback manifest (`assets/valve_vr/models/vr_fallback.json`),
  currently `PROPOSED` with all candidates `validated: false`.
- Exit criterion: one labelled fixed-camera comparison sheet per weapon class
  with maintainer `ADVANCE`, followed by a fresh `V3`/`R2` PASS at that commit.
  Until then `V3`, `R2` and M1 assertion 53 are expected to FAIL.

## Stage 2 pitch_adjust removal (DONE data + muzzle precedence)

- Zero the one non-zero `pitch_adjust`; keep adjust as no-anchor fallback.
- Optional hand/aim cleanup in `xr_input.c` (~1896-2070) remains.
- Exit: `M1`/`R1`/`A5`/`A6`/`W0` green.

## Stage 3 hand skeleton map (OpenXR `XrHandJointEXT` primary; OpenVR secondary)

The PRIMARY reference is the OpenXR `XR_EXT_hand_tracking` default joint
set: 26 `XrHandJointEXT` joints (PALM, WRIST, thumb 4, index/middle/ring/
little 5 each). See [`reference/OPENXR_HANDS_NOTE.md`](reference/OPENXR_HANDS_NOTE.md)
and `3rdparty/openxr/include/openxr/openxr.h`. The OpenVR 31-bone enum is
only a SECONDARY naming guide, not a runtime dependency. `S2` maps the
shipped rig to the 26-joint set by default (`--standard openvr` keeps the
31-name view). The project does not consume `XR_EXT_hand_tracking` today:
hands are baked plus procedural curl. Quest 3 input is OpenXR-only.

The OpenVR 31-bone enum is a SEMANTIC GUIDE for bone names and indices, not a
runtime dependency. The target device is the Meta Quest 3, whose input path
is OpenXR only. Do not add OpenVR runtime code; map the shipped rig onto the
enum for naming, and consume skeletal poses through OpenXR. Gate `S1`
verifies the rig curl axis directly from the MDL rest bones.

- 31 bones, name/index mapping, no re-skin.
- Rename IK stages `IK1`/`IK2` to avoid the `H1` collision.

## Stage 4 spatial reload

- Add magwell/ejection/slide sockets.
- Rename unregistered `H0`/`H4a`.

## Stage 5 Box3D

- `S0`/`S1` queries only; no bodies.

## Deferred

- Cosmetic mesh repair.
- Procedural hands.
- Accessibility UI.

## Retired

- Retired gates: `A1`, `B1`, `W2`, `W4`, `H0`/`H4a` names, `out/mmod_import` pipelines.

## Gate map

- Docs: `D1`
- Hygiene: `H1`
- Assets: `A2`-`A9`, `V1`
- Engine: `M1`, `R1`, `T1`
- Quest: `Q1`
- Weapons: `W0`, `W1`
## HIL is blocked (maintainer criterion)

The maintainer will not test on the Quest 3 while the simulator shows
misaligned aim/laser/barrel/hands AND the tests pass. The earlier green `V3`/
`R2` were false positives by construction; D-031 removed the compensating
rotation and the gates are now red. **Quest 3 HIL is blocked** until `F1`
carries an approved VR-ready fallback per weapon class and a fresh `V3`/`R2`
at that commit is green. Never relax the 8-degree / `in_front=1` thresholds,
and never mark a gate PASS from an older run.
