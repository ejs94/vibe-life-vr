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
| Bore axis | `A9`: 7/10 off-axis (asset pair only) | `A9` (FINDING) + `M1` assertion 52 | runtime grip->muzzle axis + 2-hand HIL |
| Hand skeleton semantics | `v_hand.mdl` layout differs | `S1`/`A3`/`A4` | rig axis + name map, no re-skin; OpenVR enum is a guide only |
| Quest freshness | `Q1` 2026-11-07 | `Q1` | fresh run on maintainer request |
| Test integrity | `M1` log greps | `T1` | negative control passes |

## Stage 1 bore axis (code complete; HIL pending)

- `ref/gl_vr/gl_studio.c` `R_VR_RotateViewmodelToPalm` derives the bore at
  runtime from the world-space grip-bone -> muzzle-bone vector; there is no
  model-space axis, no Blender/MDL/OpenXR axis conversion, and no per-weapon
  override.
- `engine/platform/openxr/xr_input.c` keeps the raw aim angles for
  `models/native/` weapons, so the authoritative firing line is unchanged.
- The `muzzle_pos -> muzzle_pos2` pair is a lateral muzzle-flash quad, not the
  barrel; nothing aligns to it.
- `M1` assertion 52 rejects a vertical green tracer in the weapon captures that
  the earlier log greps could not see.
- Exit: `M1`/`R1`/`W0` green plus two-handed HIL confirmation.

## Stage 2 pitch_adjust removal (DONE data + muzzle precedence)

- Zero the one non-zero `pitch_adjust`; keep adjust as no-anchor fallback.
- Optional hand/aim cleanup in `xr_input.c` (~1896-2070) remains.
- Exit: `M1`/`R1`/`A5`/`A6`/`W0` green.

## Stage 3 hand skeleton map (OpenVR enum as a guide; runtime is OpenXR)

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