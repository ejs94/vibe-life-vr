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
- D-024: bore anchors under review (`A9` 7/10 off).
- Green gates do not prove appearance; HIL confirmation required for visual changes.

## Blocker register

| Blocker | Evidence | Gate | Exit criterion |
|---|---|---|---|
| Bore axis | `A9`: 7/10 off-axis | `B1` | `B1` PASS + `M1`/`R1`/`W0` green + HIL |
| OpenVR 31-bone hand skeleton | `v_hand.mdl` layout differs | `A3`/`A4` | name/index map, no re-skin |
| Quest freshness | `Q1` 2026-11-07 | `Q1` | fresh run on maintainer request |
| Test integrity | `M1` log greps | `T1` | negative control passes |

## Stage 1 bore axis (code complete; HIL pending)

- `engine/platform/openxr/xr_profile.h/.c`: `bore_axis` field, parser, getter.
- `ref/gl_vr/gl_studio.c` `R_VR_RotateViewmodelToPalm` (~1972).
- `engine/platform/openxr/xr_input.c` `XR_GetPrimaryHandMuzzleTransform` (~1663).
- `assets/valve_vr/models/vr_weapons.json`: 7 overrides.
- `bore_axis` is NOT mirrored for left-handed players.
- Renderer resolves sign from the muzzle-minus-grip bone vector.
- Firing line stays numerically the raw aim.
- Exit: `B1` PASS + `M1`/`R1`/`W0` green + HIL confirmation.

## Stage 2 pitch_adjust removal (DONE data + muzzle precedence)

- Zero the one non-zero `pitch_adjust`; keep adjust as no-anchor fallback.
- Optional hand/aim cleanup in `xr_input.c` (~1896-2070) remains.
- Exit: `M1`/`R1`/`A5`/`A6`/`W0` green.

## Stage 3 hand skeleton map

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

- Retired gates: `A1`, `W2`, `W4`, `H0`/`H4a` names, `out/mmod_import` pipelines.

## Gate map

- Docs: `D1`
- Hygiene: `H1`
- Assets: `A2`-`A9`, `B1`, `V1`
- Engine: `M1`, `R1`, `T1`
- Quest: `Q1`
- Weapons: `W0`, `W1`