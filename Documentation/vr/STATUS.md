# Status

**Last updated:** 2026-10-31
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

### Current task: Glock hole repair

- [ ] `A1` boundary-loop report for the Glock
- [ ] Classify intentional versus accidental holes
- [ ] Implement the radial liner repair
- [ ] Pass `A2` MDL roundtrip
- [ ] Pass `A4` visual comparison with maintainer approval
- [ ] Pass `M1` and `R1` after the repair
- [ ] Repeat the pilot on the crossbow
- [ ] Batch the remaining 13 viewmodels

## Current state

| Item | Result |
|---|---|
| Monado unit suite (`M1`) | 44/44 PASS |
| Regression battery (`R1`) | 19/19 PASS |
| Documentation gate (`D1`) | See `out/qa/D1/latest` |
| Quest hardware-in-the-loop (`Q1`) | Pending; maintainer decides when to run |
| Asset repair epic | Not started; top priority |

The 44/44 result was produced with the Monado suite on 2026-10-31. The suite
default timeout was raised from 55s to 90s because the unarmed-hand phase could
be cut off after the viewmodel telemetry grew. A clean run must finish the
`UNARMED_HAND_TEST_BEGIN` phase and produce `unit_23_unarmed_rest.png` and
`unit_24_unarmed_moved.png`.

## Active blockers

1. **Holed viewmodel meshes.** Several 1998-era weapon meshes have open
   boundary loops that are visible in VR. This is the top asset-repair task.
2. **Manual reload coverage.** The Glock staged reload is implemented. The
   remaining weapons and the interaction contract still need gates.
3. **Quest pass is pending.** No Quest result is implied by the Monado or
   regression results.

## Next steps

1. Add boundary-loop diagnostics and classify intentional versus accidental
   holes on the Glock viewmodel.
2. Implement radial duplication/liner repair in Python while preserving bones,
   UVs, weights and bodygroups.
3. Validate the repaired Glock with asset audit, MDL roundtrip, 360-degree
   renders and the Monado suite before touching the next weapon.

## Evidence

A gate result is only current if it is reachable from
`out/qa/<gate-id>/latest`. Do not cite an old `out/evidence` directory; that
root was retired on 2026-10-31. If a gate has no run, record it as `pending`,
not as passed.
