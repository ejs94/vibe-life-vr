# Status

**Last updated:** 2026-11-09
**Branch:** `feature/openxr-vr`
**Baseline tag:** `baseline-clean-2026-10-31`
**Evidence root:** `out/qa/`

This is the single page of truth. The abandoned Glock guard/trigger modelling
sessions and their evidence were removed on 2026-11-09; the shipped native
Glock is untouched. Do not resume cosmetic mesh work before the shot-vector and
hand-skeleton blockers below are resolved.

## Progress

`[x]` done, `[ ]` pending. Run `python3 scripts/progress_report.py` for the
current counts and gate freshness.

### Baseline

- [x] Freeze current work in logical commits
- [x] Tag `pre-cleanup-2026-10-31`
- [x] Consolidate canonical documentation
- [x] Retire `out/evidence` and standardize `out/qa`
- [x] Add the `GATES.md` registry and the `@gate-runner` agent
- [x] Remove obsolete scripts, cfgs and caches
- [x] Tag `baseline-clean-2026-10-31`

### Validation

- [x] `D1` documentation gate
- [x] `M1` Monado 49/49
- [x] `R1` regression 19/19
- [x] `A7` Glock manual reload
- [x] `Q1` Quest hardware-in-the-loop (2026-11-07)

### Current task: native weapon path

- [x] `W0` native route + legacy fallback
- [x] `W1` coordinate calibration and human approval
- [x] Native Glock adopted (Half-Life: VR SD, unmodified)
- [x] Native arsenal (15 viewmodels) routed
- [x] HEV glove on both hands (`v_hand.mdl`)
- [x] Shot direction follows the visible barrel (aim-pose fix; HIL validation pending)
- [ ] Hand matches the OpenVR 31-bone skeleton
- [ ] Manual reload driven by 6DoF hands

## Current state

| Item | Result |
|---|---|
| Monado unit suite (`M1`) | 49/49 PASS |
| Regression battery (`R1`) | 19/19 PASS |
| Documentation (`D1`) / hygiene (`H1`) | PASS |
| Native route (`W0`) | PASS: native selected, legacy fallback observed |
| Native asset | `models/native/v_9mmhandgun.mdl`, 3 bodies, 4 anchors, 10 sequences, HEV gloves |
| Deployed models | `assets/valve_vr/models/native/` (15), `out/valve/models/native/` (15), `out/valve_vr/models/native/` (15) |
| Load proof | `[VR_WEAPON_ROUTE] ... route=native` and `[VM_DBG_CHANGE] ... models/native/v_9mmhandgun.mdl` in `out/qa/M1/runs/20261109_215814/monado_unittest_engine.log` |
| Manual reload (`A7`) | PASS (staged vertical slice) |
| Quest (`Q1`) | PASS 2026-11-07; a fresh run is the maintainer's decision |

The overlay trap still applies: update both `out/valve/models` and
`out/valve_vr/models`, and confirm in the log which file was loaded.

## Active blockers

1. **Shot direction: fixed in code, HIL validation pending.** The firing line
   read `XR_GetPrimaryHandTransform`, which applies `XR_ApplyTwoHandStabilizer`
   and blends the angle toward the off-hand grip line, while the renderer reads
   the raw aim pose. Two-handed shots therefore diverged from the visible
   barrel. The muzzle path now reads `XR_GetPrimaryAimPose` (2026-11-10);
   `aim_shot_evidence.sh`, `M1`, `R1` and `W0` pass. The simulated harness
   cannot engage the stabilizer (primary and off-hand poses are identical), so
   a headset check with two hands is still required. See the handoff below.
2. **The hand is not a VR skeleton.** The target is the OpenVR hand skeleton
   (31 bones, `Root`, `Wrist`, `Thumb0-3`, four fingers `0-4`, five aux bones).
   The shipped `v_hand.mdl` has 31 bones but a different layout (arm chain plus
   5 fingers x 3); a name/index mapping is needed before any re-skin.
3. **Quest freshness.** `Q1` passed on 2026-11-07 at an older commit. Monado is
   the default local gate; never infer a Quest pass from Monado.

## Next steps

1. Validate the aim-pose firing line on a real headset with two hands engaged,
   and fix the circular shot-origin test (it forces zero angles and overwrites
   the logged start). A model-anchor direction (`muzzle_pos2 - muzzle_pos`)
   remains an option only after that.
2. Map the existing hand rig onto the OpenVR 31-bone enum without replacing the
   MDL. Verify whether the input layer already consumes skeletal data.
3. Keep the shipped native Glock as the HL1-like base (no Beretta, no sculpting)
   and drive manual reload with `A7` plus `clip_reference` and `Box02`.
4. Re-run `W0`, `M1` and `R1` after each step; one labelled comparison sheet
   for visual approval.

## Handoff: why the shot vector is wrong

**Facts, verified in code.** The firing direction is never derived from the
model:

1. `engine/platform/openxr/xr_input.c:1634-1654` builds `local_angles` from
   `handAngles + turn_yaw + (pitch_adjust, yaw_adjust, roll_adjust)`.
2. `xr_input.c:1656-1659` copies those angles to `out_aim_angles`.
3. `engine/server/sv_pmove.c:945-950` writes them to `clent->v.vuser2` and the
   muzzle offset to `vuser1`.
4. `3rdparty/patches/hlsdk-vibe-life.patch:1071-1075` calls
   `UTIL_MakeVectors( pev->vuser2 )` to produce `v_forward`, the authoritative
   ballistics direction.
5. Meanwhile the **visible barrel** is oriented by the renderer:
   `ref/gl_vr/gl_studio.c:2491` calls `R_VR_RotateViewmodelToPalm`
   (`:1890`), gated by `vr_anchor_rotation` (default `1`,
   `engine/platform/openxr/xr_core.c:382`), and by the aim/grip pose split in
   `DECISIONS.md` D-016 and D-017.

`xr_input.c:1671-1674` states the split explicitly: the muzzle position follows
the visual pose, the firing direction follows the aim pose. **No code path
derives the direction from the rendered barrel.** The HL:VR reference combines
attachments 0 and 1 for ballistics
([`reference/REFERENCE_PORTS.md`](reference/REFERENCE_PORTS.md) section 3.8);
this project adopted attachment 0 for position only. `DECISIONS.md` D-014 still
promises that direction will follow `muzzle_pos2 - muzzle_pos` "once that
change lands" — it never landed (`9a5ba043` recorded the rejected measurement).

**Why the test passed anyway.** `scripts/aim_shot_evidence.sh:39-48` forces every
hand and head angle to zero; `engine/platform/openxr/xr_core.c:243-248`
overwrites the logged shot `start` with the computed muzzle; and
`scripts/check_shot_origin.py:114` defines the "barrel" as `palm -> muzzle`,
where that muzzle is itself built from the same calibrated angles
(`xr_input.c:1689-1703`). The reported 0.01-0.18 degrees therefore proves
internal arithmetic consistency, not that the visible barrel and the bullet
agree in a headset. `scripts/check_aim_pose.py` uses only a simulated 35 degree
grip tilt and checks the renderer, not the bullet.

**Resolved 2026-11-10.** The root cause was not the numeric calibration but the
pose source: `XR_GetPrimaryHandMuzzleTransform` read
`XR_GetPrimaryHandTransform`, which applies `XR_ApplyTwoHandStabilizer` and
blends the angle toward the off-hand grip line, while the renderer reads
`XR_GetPrimaryAimPose`. The muzzle path now reads the aim pose first
(`engine/platform/openxr/xr_input.c`); `aim_shot_evidence.sh`, `M1`, `R1` and
`W0` pass. Remaining: the harness forces zero angles and overwrites the logged
start, so it cannot engage the stabilizer; validate with a real two-hand grip on
the headset. `scripts/test_aim_shot_twohand.sh` reproduces the old 20 degree
divergence and now passes (control and stress both 0.00 degrees).

## Evidence

A gate result is only current if it is reachable from
`out/qa/<gate-id>/latest`. `out/qa/INDEX.md` lists the newest result per gate.
Do not cite the retired `out/evidence` root. If a gate has no run, record it as
`pending`, not as passed.
