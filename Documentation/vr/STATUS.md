# Status

**Last updated:** 2026-11-11
**Branch:** `feature/openxr-vr`
**Baseline tag:** `baseline-clean-2026-10-31`
**Evidence root:** `out/qa/`
**Plan:** [`PLAN.md`](PLAN.md) is the single plan of truth for stages and
blockers; this page tracks current state.

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
| Monado unit suite (`M1`) | 51/51 PASS (engine exit 0, sentinel, non-blank captures) |
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
| Bore diagnostic (`A9`) | FINDING: the pair is lateral on 7/10 weapons; `FINDING` is not a pass |
| Bore gate (`B1`) | PASS: 7 `bore_axis` overrides verified against the asset hitboxes |
| Test integrity (`T1`) | PASS: 43/48 baseline assertions ROBUST (89.6%) under log mutation |
| Quest (`Q1`) | PASS 2026-11-07; a fresh run is the maintainer's decision |

The overlay trap still applies: update both `out/valve/models` and
`out/valve_vr/models`, and confirm in the log which file was loaded.

## Active blockers

1. **Bore axis code complete, headset confirmation pending.** The pair is
   lateral on 7/10 barrel weapons (`A9`). Seven `bore_axis` overrides now live
   in `vr_weapons.json`; the renderer aligns them (sign resolved from
   muzzle-minus-grip) and the firing line stays on the raw aim. `B1` is green.
   The circular shot-origin harness is broken (independent hitbox axis, second
   tilted pose, `reported_start` preserved). Only a two-handed headset check can
   confirm the visible barrel and laser agree; do not claim it from Monado.
2. **The hand is not a VR skeleton.** The target is the OpenVR hand skeleton
   (31 bones, `Root`, `Wrist`, `Thumb0-3`, four fingers `0-4`, five aux bones).
   The shipped `v_hand.mdl` has 31 bones but a different layout (arm chain plus
   5 fingers x 3); a name/index mapping is needed before any re-skin.
3. **Quest freshness.** `Q1` passed on 2026-11-07 at an older commit. Monado is
   the default local gate; never infer a Quest pass from Monado.
4. **Test integrity, closed.** `M1` now requires a clean engine exit, the
   suite sentinel, log events (no OR-to-PNG fallbacks) and non-blank captures;
   `T1` mutates the log and requires assertions to flip. `D1` checks gate
   references dynamically, and diagnostics record `FINDING`, not `PASS`.

## Next steps

1. **Stage 1, bore axis (code done).** Validate on a real headset with two
   hands engaged; `B1`, `M1`, `R1` and `W0` are green locally. See
   [`PLAN.md`](PLAN.md#stage-1-bore-axis).
2. **Stage 2, `pitch_adjust` removal (data + precedence done).** All 16
   shipped profiles are zero; the Euler adjust is now only a fallback for mods
   without bore anchors. The optional hand/aim transform cleanup remains.
   Exit: `M1`/`R1`/`A5`/`A6`/`W0` green.
3. **Stage 3, hand skeleton map.** Map the shipped 31-bone rig onto the OpenVR
   enum without a re-skin. Exit: `A3` passes and an `A4` comparison sheet is
   approved.
4. **Stage 4, spatial reload.** Add the magwell, ejection and slide sockets and
   replace the staged B presses. Exit: `A7` passes with the new sockets.
5. Re-run `W0`, `M1` and `R1` after each stage; one labelled comparison sheet
   for visual approval. Unresolved Quest reports are triaged in
   [`reference/QUEST_FIELD_REPORTS.md`](reference/QUEST_FIELD_REPORTS.md).

## Bore axis: open

The renderer and the bullet used to have two sources of truth: the renderer
aligned a grip->muzzle axis while the bullet used hand angles plus the
per-weapon `pitch_adjust`. They now share one axis, `muzzle_pos ->
muzzle_pos2` (`ref/gl_vr/gl_studio.c`, `engine/platform/openxr/xr_input.c`;
[`DECISIONS.md`](DECISIONS.md) D-024).

That fixed the split, but it did not make the shared axis the visible bore.
`A9` compares the pair with the authored body hitbox and finds it 66-90° off on
7 of the 10 barrel weapons. `scripts/aim_shot_evidence.sh` reports 0.00 degrees
because it measures the bullet against the same pair, so the result is
circular. The weapon laser in the headset shows the mismatch directly.

Open items:

- Replace the pair with a per-weapon bore axis (or move `muzzle_pos2` onto the
  true bore) and make the renderer and the firing line use it.
- Fix the circular shot-origin harness: `scripts/aim_shot_evidence.sh` forces
  every hand and head angle to zero and `engine/platform/openxr/xr_core.c`
  overwrites the logged shot start with the computed muzzle.
- Validate the result on the headset reference space with two hands engaged.

## Evidence

A gate result is only current if it is reachable from
`out/qa/<gate-id>/latest`. `out/qa/INDEX.md` lists the newest result per gate.
Do not cite the retired `out/evidence` root. If a gate has no run, record it as
`pending`, not as passed.
