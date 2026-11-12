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
- [x] Shot direction follows the visible barrel (runtime grip->muzzle axis; HIL validation pending)
- [ ] Hand rig mapped to the OpenVR 31-bone enum (guide only; input is OpenXR)
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
| Bore alignment (runtime) | PARTIAL: gun pose and vertical tracer fixed, but the laser is still ~40deg off the slide on Glock/SMG (OPEN, blocker 5) |
| Test integrity (`T1`) | PASS: 43/48 baseline assertions ROBUST (89.6%) under log mutation |
| Quest (`Q1`) | PASS 2026-11-07; a fresh run is the maintainer's decision |

The overlay trap still applies: update both `out/valve/models` and
`out/valve_vr/models`, and confirm in the log which file was loaded.

## Active blockers

1. **Bore axis: partial fix, ray/barrel collinearity OPEN.** The runtime
   grip->muzzle axis removed the ~90deg Glock twist and the vertical shot
   tracer, but the laser still leaves the muzzle roughly 40 degrees off the
   visible slide on the Glock and SMG. `grip -> muzzle` is a wrist-to-tip
   diagonal, `muzzle_pos -> muzzle_pos2` is a lateral flash quad, and the QC
   hitbox axes disagree with mesh principal axes on several converted MDLs.
   No runtime vector is proven to be the visible bore. HIL/asset work required;
   do not claim appearance from Monado.
2. **The hand rig is not mapped yet.** The OpenVR hand skeleton is a naming
   guide (31 bones, `Root`, `Wrist`, `Thumb0-3`, four fingers `0-4`, five aux
   bones), NOT a runtime dependency: the Quest 3 target is OpenXR-only. The
   shipped `v_hand.mdl` has a Bip01 layout with a different index order; a
   name/index mapping is needed before any re-skin. Gate `S1` verifies the rig
   finger curl axis is local Z, so procedural curl closes the fist instead of
   sweeping every finger down towards -Z.
3. **Quest freshness.** `Q1` passed on 2026-11-07 at an older commit. Monado is
   the default local gate; never infer a Quest pass from Monado.
5. **Ray is not collinear with the barrel (OPEN).** See blocker 1; the M1
   gates verify the pose and the absence of a vertical tracer, NOT that the
   ray leaves straight out of the barrel.
4. **Test integrity, closed.** `M1` now requires a clean engine exit, the
   suite sentinel, log events (no OR-to-PNG fallbacks) and non-blank captures;
   `T1` mutates the log and requires assertions to flip. `D1` checks gate
   references dynamically, and diagnostics record `FINDING`, not `PASS`.

## Next steps

1. **Stage 1, bore axis (code done; HIL is the remaining exit criterion).**
   The renderer now uses the runtime grip->muzzle bone vector; the simulator
   run is green. Validate on a real headset with two hands engaged before
   claiming appearance. See [`PLAN.md`](PLAN.md#stage-1-bore-axis-code-complete-hil-pending).
2. **Stage 2, `pitch_adjust` removal (data + precedence done).** All 16
   shipped profiles are zero; the Euler adjust is now only a fallback for mods
   without bore anchors. The optional hand/aim transform cleanup remains.
   Exit: `M1`/`R1`/`A5`/`A6`/`W0` green.
3. **Stage 3, hand skeleton map.** Map the shipped rig onto the OpenVR enum
   (guide only) without a re-skin; consume poses via OpenXR. Exit: `S1`, `A3`
   pass and an `A4` comparison sheet is approved.
4. **Stage 4, spatial reload.** Add the magwell, ejection and slide sockets and
   replace the staged B presses. Exit: `A7` passes with the new sockets.
5. Re-run `W0`, `M1` and `R1` after each stage; one labelled comparison sheet
   for visual approval. Unresolved Quest reports are triaged in
   [`reference/QUEST_FIELD_REPORTS.md`](reference/QUEST_FIELD_REPORTS.md).

## Bore axis: partial fix, ray/barrel still open

The renderer, the laser and the bullet used to disagree. D-024 made
`muzzle_pos -> muzzle_pos2` the shared axis, but that pair is a lateral
muzzle-flash quad, so aligning it to the aim pose twisted every native
viewmodel by roughly 90 degrees and the MP5 shot left the barrel as a vertical
tracer.

The fix (D-027) derives the bore at runtime:

- `ref/gl_vr/gl_studio.c` `R_VR_RotateViewmodelToPalm` rotates the viewmodel
  with the world-space grip-bone -> muzzle-bone vector. No model-space axis is
  involved and no Blender/MDL/OpenXR axis conversion is applied.
- `engine/platform/openxr/xr_input.c` keeps the raw aim angles for
  `models/native/` weapons, so the firing line stays on the aim pose.
- The `muzzle_pos -> muzzle_pos2` pair is treated as the muzzle-flash quad.

Simulator evidence: the MP5 capture went from 986 bright-green pixels in a
28x254 vertical line (tracer firing up) to 0 after the fix; the Glock is seated
in the hand with the laser leaving the slide; the `[VR_ALIGN]` Glock correction
dropped from ~90deg to ~52deg. Captures are in `out/qa/V2/`.

`A9` still reports 7/10 weapons OFF-AXIS. That is expected: it measures the
asset pair, which is not the bore, so it stays a `FINDING` and never gates
automation.

Open items:

- Two-handed headset confirmation that the visible barrel, the laser and the
  bullet agree. Monado cannot prove appearance.
- The circular shot-origin harness still needs an independent reference:
  `scripts/aim_shot_evidence.sh` measures the bullet against the same pair and
  forces every hand and head angle to zero.

## Evidence

A gate result is only current if it is reachable from
`out/qa/<gate-id>/latest`. `out/qa/INDEX.md` lists the newest result per gate.
Do not cite the retired `out/evidence` root. If a gate has no run, record it as
`pending`, not as passed.
