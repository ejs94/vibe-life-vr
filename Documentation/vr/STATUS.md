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
- [ ] Hand rig mapped to the OpenXR 26-joint `XrHandJointEXT` set (OpenVR is a guide only)
- [ ] Manual reload driven by 6DoF hands

## Current state

| Item | Result |
|---|---|
| Monado unit suite (`M1`) | **FAIL (expected)**: 52/53; assertion 53 = asset readiness |
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
| Bore alignment (runtime) | **FAIL (expected)**: `V3`/`R2` measure raw asset geometry; D-031 disabled the compensating bone rotation |
| Test integrity (`T1`) | PASS: 43/48 baseline assertions ROBUST (89.6%) under log mutation |
| Acceptance gate (`V3`) | **FAIL (expected)**: assets are not VR-ready; see blocker 1 and `F1` |
| Quest (`Q1`) | PASS 2026-11-07 at an older commit; **HIL blocked while `V3`/`R2` are red** |

The overlay trap still applies: update both `out/valve/models` and
`out/valve_vr/models`, and confirm in the log which file was loaded.

## Active blockers

1. **Weapon assets are not VR-ready (OPEN, primary blocker).** The labelled
   sheet `out/qa/V2/bore_fix_comparison.png` shows the MP5 inclined ~40deg,
   the baked hand detached from the grip, and the laser leaving diagonally.
   `S0.5` proved the shipped MDLs are byte-identical to HL:VR SD and that
   swapping the MP5 original only improved 18.6deg -> 10.0deg. D-031 disabled
   the compensating bone rotation (`vr_anchor_rotation` now 0): it twisted
   every bone 33-94deg to force a proxy vector onto the aim ray, which is not
   the visible barrel. `grip -> muzzle` is a wrist-to-tip diagonal,
   `muzzle -> hud` is an internal rig anchor, `muzzle_pos2` is the flash quad,
   `$hbox` is a body cross-section, and `mdldec` mesh vertices are in a
   different coordinate space. **No engine math repairs an asset authored for
   flat-screen play.** Exit: adopt VR-ready viewmodels per weapon class (`F1`)
   with maintainer-approved comparison sheets.
2. **The hand rig is not mapped yet.** The OpenVR hand skeleton is a naming
   guide (31 bones, `Root`, `Wrist`, `Thumb0-3`, four fingers `0-4`, five aux
   bones), NOT a runtime dependency: the Quest 3 target is OpenXR-only. The
   shipped `v_hand.mdl` has a Bip01 layout with a different index order; a
   name/index mapping is needed before any re-skin. Gate `S1` verifies the rig
   finger curl axis is local Z, so procedural curl closes the fist instead of
   sweeping every finger down towards -Z.
3. **Quest freshness.** `Q1` passed on 2026-11-07 at an older commit. Monado is
   the default local gate; never infer a Quest pass from Monado.
5. **Simulator acceptance: OPEN and RED.** The earlier `V3`/`R2` greens were
   tautological: the renderer forced the exact vector the gate measured onto
   the aim ray. With D-031 that rotation is OFF, so the gates now measure the
   raw asset and fail. Thresholds were NOT loosened. `vr_hide_arms 2` debug
   phases and no-barrel `N/A` remain excluded. Do not mark either gate PASS
   from an older run; Quest 3 HIL stays blocked.
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
3. **Stage 3, hand skeleton map.** Map the shipped rig onto the OpenXR
   26-joint `XrHandJointEXT` set (`S2` default) without a re-skin; keep the
   OpenVR 31-bone enum as a secondary guide; consume poses via OpenXR only.
   Exit: `S1`, `S2`, `A3` pass and an `A4` comparison sheet is approved.
4. **Stage 4, spatial reload.** Add the magwell, ejection and slide sockets and
   replace the staged B presses. Exit: `A7` passes with the new sockets.
5. Re-run `W0`, `M1` and `R1` after each stage; one labelled comparison sheet
   for visual approval. Unresolved Quest reports are triaged in
   [`reference/QUEST_FIELD_REPORTS.md`](reference/QUEST_FIELD_REPORTS.md).

## Bore axis: simulator aligned, HIL open

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

## Mod port status

One row per Xash3D gamedir. `S0` intake, `S1` measure, `S2` profile,
`S3` simulator acceptance, `S4` Gold SDK, `S5` Quest HIL. A mod may sit at
any stage without blocking the others. `UNKNOWN` is never a pass.

| gamedir | tier | state | V3 | R2 | next |
|---|---|---|---|---|---|
| `valve` | gold | `S1` | **FAIL** | **FAIL** | adopt VR-ready viewmodels per class (`F1`) |
| `gearbox` | silver | `S0` | pending | pending | model inventory |
| `bshift` | silver | `S1` | pending | pending | fix `v_9mmar.mdl` -> `v_9mmAR.mdl` case mismatch found by `P1`; 16/16 bore bases measured |
| `cstrike` | silver | `S0` | pending | pending | no-pair fallback test |
| `hunger` | bronze | `S0` | UNKNOWN | pending | graceful degradation |

### Intake findings

- `P1` on the Blue-Shift-VR payload (16 viewmodels): FAIL — `v_9mmar.mdl`
  is bundled with the wrong case; the HLSDK requests `v_9mmAR.mdl`, so
  the vanilla model loads on case-sensitive filesystems. This is the
  same overlay trap documented for `valve`, now generalised per gamedir.
- `P2` measured the authored two-point bore basis on **16/16** of those
  models with no code change (4 HIGH, 11 MEDIUM, 1 LOW): the contract is
  reusable across mods, not specific to the shipped `valve` assets.
