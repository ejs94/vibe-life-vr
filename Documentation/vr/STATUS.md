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

- [x] `A1` boundary-loop report for the Glock
- [x] Classify intentional versus accidental holes
- [x] Implement the radial liner repair
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
| Evidence hygiene (`H1`) | See `out/qa/H1/latest` |
| Asset audit (`A1`) | PASS (audit); Glock baseline verdict FAIL |
| Glock topology score | 9.67/35 provisional; 2 accidental defects, 0 uncertain |
| Visual review (`V1`) | Available: `out/qa/V1/compare_glock/` (non-blocking) |
| Quest hardware-in-the-loop (`Q1`) | Pending; maintainer decides when to run |
| Asset repair epic | A1 baseline complete; Glock repair implemented, A2/A4 pending |

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
3. **A1 classification review is pending.** The audit resolved all loops, but
   the two accidental defects and the medium-confidence intentional sleeves
   still need maintainer approval before deployment.
4. **A2 roundtrip toolchain caveat.** The patched Glock and the pristine MMOD
   Glock both drift by about `1e-6` on the attachment float
   (`4.249999` vs `4.250001`). This is compiler drift, not a repair regression;
   A2 needs a documented tolerance or a toolchain fix before it can be a clean
   binary gate.
5. **Quest pass is pending.** No Quest result is implied by the Monado or
   regression results.

## Next steps

1. Review `out/qa/V1/compare_glock/` and
   `out/viewmodel_work/glock_repair/repair_sheet.png`; the repair closes the
   clip side and dissolves the front-top feather.
2. Resolve the `A2` attachment-float tolerance, then re-run the patched audit
   and the in-engine visual review.
3. Approve the Glock before touching the crossbow. `A4` human approval remains
   the final visual gate.

## Evidence

A gate result is only current if it is reachable from
`out/qa/<gate-id>/latest`. Do not cite an old `out/evidence` directory; that
root was retired on 2026-10-31. If a gate has no run, record it as `pending`,
not as passed.
