# Status

**Last updated:** 2026-11-11
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
- [x] `A4` hands gate (baked vs standalone hand)
- [x] `A5` grip seat against the latest `M1` engine log

### Current task: native weapon path

- [x] `W0` native route + legacy fallback
- [x] `W1` coordinate calibration and human approval
- [x] Native Glock adopted (Half-Life: VR SD, unmodified)
- [x] Native arsenal (15 viewmodels) routed
- [x] HEV glove on both hands (`v_hand.mdl`)
- [x] Shot direction follows the visible barrel (model bore anchors; HIL validation pending)
- [ ] Hand matches the OpenVR 31-bone skeleton
- [ ] Manual reload driven by 6DoF hands

## Current state

| Item | Result |
|---|---|
| Monado unit suite (`M1`) | 49/49 PASS |
| Regression battery (`R1`) | 19/19 PASS |
| Documentation (`D1`) | PASS |
| Evidence hygiene (`H1`) | PASS (2026-11-11) |
| Native route (`W0`) | PASS: native selected, legacy fallback observed |
| Native asset | `models/native/v_9mmhandgun.mdl`, 3 bodies, 4 anchors, 10 sequences, HEV gloves |
| Deployed models | `assets/valve_vr/models/native/` (15), `out/valve/models/native/` (15), `out/valve_vr/models/native/` (15) |
| Load proof | `[VR_WEAPON_ROUTE] ... route=native` and `[VM_DBG_CHANGE] ... models/native/v_9mmhandgun.mdl` in `out/qa/M1/runs/20261110_005848/monado_unittest_engine.log` |
| Manual reload (`A7`) | PASS (staged vertical slice) |
| Hands (`A4`) | PASS 2026-11-11 (baked vs standalone comparison sheets) |
| Grip seat (`A5`) | PASS 2026-11-11 (3 models, worst 0.000 against `M1` 20261110_005848) |
| Quest (`Q1`) | PASS 2026-11-07; a fresh run is the maintainer's decision |

The overlay trap still applies: update both `out/valve/models` and
`out/valve_vr/models`, and confirm in the log which file was loaded.

## Active blockers

1. **Shot direction: fixed in code, HIL validation pending.** The renderer and
   the muzzle path now read the same model-owned axis, `muzzle_pos` ->
   `muzzle_pos2`, so the bullet follows the visible bore by construction. The
   old split (renderer aligned `muzzle - grip`, bullet used hand angles) is
   gone. `aim_shot_evidence.sh`, `M1`, `R1` and `W0` pass; a headset check with
   two hands is still required on the real reference space.
2. **The hand is not a VR skeleton.** The target is the OpenVR hand skeleton
   (31 bones, `Root`, `Wrist`, `Thumb0-3`, four fingers `0-4`, five aux bones).
   The shipped `v_hand.mdl` has 31 bones but a different layout (arm chain plus
   5 fingers x 3); a name/index mapping is needed before any re-skin.
3. **Quest freshness.** `Q1` passed on 2026-11-07 at an older commit. Monado is
   the default local gate; never infer a Quest pass from Monado.

## Next steps

1. Validate the bore-anchor firing line on a real headset with two hands
   engaged, and fix the circular shot-origin test (it forces zero angles and
   overwrites the logged start).
2. Map the existing hand rig onto the OpenVR 31-bone enum without replacing the
   MDL. Verify whether the input layer already consumes skeletal data.
3. Keep the shipped native Glock as the HL1-like base (no Beretta, no sculpting)
   and drive manual reload with `A7` plus `clip_reference` and `Box02`.
4. Re-run `W0`, `M1` and `R1` after each step; one labelled comparison sheet
   for visual approval.
5. Arm IK, Box3D contact and the spatial reload gate are specified in
   [`reference/HAND_IK_AND_PHYSICS.md`](reference/HAND_IK_AND_PHYSICS.md).
   Start with `H0` (semantic map) and `H1` (IK math); neither needs Box3D.
   Unresolved Quest reports are triaged in
   [`reference/QUEST_FIELD_REPORTS.md`](reference/QUEST_FIELD_REPORTS.md).

## Resolved: shot vector

The firing line and the visible barrel used to have two sources of truth: the
renderer aligned a grip->muzzle axis while the bullet used hand angles plus the
per-weapon `pitch_adjust`. The model-owned pair `muzzle_pos -> muzzle_pos2` now
drives both (`ref/gl_vr/gl_studio.c`, `engine/platform/openxr/xr_input.c`); see
[`DECISIONS.md`](DECISIONS.md) D-024. `scripts/aim_shot_evidence.sh` measures
against that bore: Glock 0.00, .357 0.19, Gauss 0.00, shotgun 1.44 degrees;
`M1` 49/49, `R1` 19/19 and `W0` pass.

Two things remain before this is closed:

- Validate the result on the headset reference space with two hands engaged.
- Fix the circular shot-origin harness: `scripts/aim_shot_evidence.sh` forces
  every hand and head angle to zero and `engine/platform/openxr/xr_core.c`
  overwrites the logged shot start with the computed muzzle, so the reported
  angle proves arithmetic consistency, not that the visible barrel agrees in a
  headset.

## Evidence

A gate result is only current if it is reachable from
`out/qa/<gate-id>/latest`. `out/qa/INDEX.md` lists the newest result per gate.
Do not cite the retired `out/evidence` root. If a gate has no run, record it as
`pending`, not as passed.
