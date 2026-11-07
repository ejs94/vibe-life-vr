# Status

**Last updated:** 2026-11-06
**Branch:** `feature/openxr-vr`
**Baseline tag:** `baseline-clean-2026-10-31`
**Previous checkpoint:** `pre-cleanup-2026-10-31`
**Evidence root:** `out/qa/`

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
- [x] `M1` Monado 44/44
- [x] `R1` regression 19/19
- [x] `A7` Glock manual reload
- [ ] `Q1` Quest hardware-in-the-loop (maintainer decision)

### Current task: native weapon path

- [x] `W0` native route + legacy fallback
- [x] `W1` coordinate calibration and human approval
- [x] `W2` native Glock mesh adopted (Half-Life: VR SD, unmodified) and routed
- [x] `W3` Glock sequences present in the asset (idle, fire, reload, draw, holster)
- [ ] `W2` Glock guard/trigger detail (paused, needs modelling)
- [ ] `W3` Glock physical interaction (sockets are a modelling task)
- [ ] `W4` full arsenal behind the native route
- [x] `W5` HEV glove on both hands (one two-hand model, mirrored left chain)
- [ ] `W6` Magnum replication with no per-weapon code

## Native base adopted 2026-11-06

Native weapon production was frozen on 2026-11-01 after the source-derived
blockout reproduced MMOD mesh defects. It resumed on 2026-11-06 with a different
method: instead of sculpting a mesh, the project adopted the complete GoldSrc
viewmodel shipped by Half-Life: VR's SD set, which already carries the four
model-authored anchors (`muzzle_pos`, `muzzle_pos2`, `hud_pos`, `hud_pos2`), ten
sequences and Gordon/HEV glove hands.

`W2` shipped on 2026-11-06 as
`assets/valve_vr/models/native/v_9mmhandgun.mdl`, unmodified, selected by the
native route:

```text
[VR_WEAPON_ROUTE] legacy=models/v_9mmhandgun.mdl native=models/native/v_9mmhandgun.mdl route=native
```

The trigger, guard and magazine-release modelling is paused, not abandoned. The
measurements, the reason for stopping and the brief for a future attempt are in
[`reference/W2_HANDOFF.md`](reference/W2_HANDOFF.md). The next work is asset
adoption, aim anchoring, the HEV gloves and interaction reuse; none of it needs
new geometry.

## Current state

| Item | Result |
|---|---|
| Monado unit suite (`M1`) | 44/44 PASS |
| Regression battery (`R1`) | 19/19 PASS |
| Documentation gate (`D1`) | See `out/qa/D1/latest` |
| Evidence hygiene (`H1`) | See `out/qa/H1/latest` |
| Asset audit (`A1`) | PASS (audit); Glock baseline verdict FAIL |
| Glock topology score | 9.67/35 provisional; 2 accidental defects, 0 uncertain |
| Visual review (`V1`) | Available: `out/qa/V1/compare_glock/` (non-blocking) |
| Native route/fallback (`W0`) | PASS: native selected, legacy fallback observed |
| Coordinate calibration (`W1`) | PASS: barrel bore, trigger, rear sight and hammer approved 2026-11-01 |
| Quest hardware-in-the-loop (`Q1`) | Pending; maintainer decides when to run |
| Weapon epic | **W2 SHIPPED 2026-11-06**: Half-Life: VR (SD) Glock as the native base |
| Native asset | `models/native/v_9mmhandgun.mdl`, 3 bodies, 4 anchors, 10 sequences, Gordon gloves |

The 44/44 result was produced with the Monado suite on 2026-10-31. The suite
default timeout was raised from 55s to 90s because the unarmed-hand phase could
be cut off after the viewmodel telemetry grew. A clean run must finish the
`UNARMED_HAND_TEST_BEGIN` phase and produce `unit_23_unarmed_rest.png` and
`unit_24_unarmed_moved.png`.

## Active blockers

1. **Trigger, guard and magazine release need modelling.** The original mesh has
   no trigger geometry and its guard is a near-solid block with a 0.3-unit slot,
   so patching it produces artefacts. Four trigger generations and three guard
   attempts were rejected. Stopped until a human Blender session or a premium
   model is available; see [`reference/W2_HANDOFF.md`](reference/W2_HANDOFF.md).
2. **The six interaction sockets do not exist yet.** Primary grip, offhand grip,
   magwell, ejection, slide rack and trigger contact are a modelling task. Until
   then the reload and touch contracts reuse the bodies and hitboxes that the
   adopted assets already contain.
3. **Old weapon assets are experimental.** MMOD Glock/Magnum, the A/B entries
   and the blockouts are not an approved baseline.
4. **A2 roundtrip toolchain caveat.** The patched and pristine MMOD Glock both
   drift by about `1e-6` on the attachment float. A2 needs a documented
   tolerance or a toolchain fix before it is a clean binary gate.
5. **Quest pass is pending.** No Quest result is implied by the Monado or
   regression results.

## Next steps

1. Adopt the remaining Half-Life: VR SD viewmodels behind `models/native/`, with
   the exact legacy basename (Android is case-sensitive).
2. Derive the ballistic direction from `muzzle_pos2 - muzzle_pos` and verify the
   right-handed result is unchanged.
3. Ship the HEV glove on both hands as a two-chain model.
4. Reuse the `clip_reference` body and the `Box*` hitboxes for the reload and
   touch contracts.
5. Keep the legacy route working and re-run `W0`, `M1` and `R1` after each step.

## Evidence

A gate result is only current if it is reachable from
`out/qa/<gate-id>/latest`. Do not cite an old `out/evidence` directory; that
root was retired on 2026-10-31. If a gate has no run, record it as `pending`,
not as passed.
