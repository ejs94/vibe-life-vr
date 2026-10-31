# Status

**Last updated:** 2026-10-31
**Branch:** `feature/openxr-vr`
**Baseline tag:** `pre-cleanup-2026-10-31`
**Evidence root:** `out/qa/`

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
