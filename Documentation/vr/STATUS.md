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

### Current task: native weapon path

- [x] `W0` native route + legacy fallback
- [ ] `W1` coordinate calibration and human approval
- [ ] `W2` Glock `socketed` rig
- [ ] `W2` Glock native mesh and blockout approval
- [ ] `W3` Glock animations baked and played in engine
- [ ] `W3` Glock physical interaction
- [ ] `W4` Magnum replication with no per-weapon code
- [ ] `W5` Gordon hand asset

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
| Coordinate calibration (`W1`) | INCONCLUSIVE: markers align; human sign-off pending |
| Quest hardware-in-the-loop (`Q1`) | Pending; maintainer decides when to run |
| Weapon epic | Native path reset; no native Glock/Magnum mesh approved |

The 44/44 result was produced with the Monado suite on 2026-10-31. The suite
default timeout was raised from 55s to 90s because the unarmed-hand phase could
be cut off after the viewmodel telemetry grew. A clean run must finish the
`UNARMED_HAND_TEST_BEGIN` phase and produce `unit_23_unarmed_rest.png` and
`unit_24_unarmed_moved.png`.

## Active blockers

1. **W1 calibration is awaiting human sign-off.** The latest marker sheet
   places muzzle, trigger and top on the expected landmarks; the maintainer
   still has to confirm FRONT/REAR.
2. **Native weapon contract is incomplete.** W0 routing/fallback works, but
   `socketed` rig, animation baking, state machine and native assets are not
   implemented.
3. **Old weapon assets are experimental.** MMOD Glock/Magnum, the A/B entries
   and the blockouts are not an approved baseline.
4. **A2 roundtrip toolchain caveat.** The patched and pristine MMOD Glock both
   drift by about `1e-6` on the attachment float. A2 needs a documented
   tolerance or a toolchain fix before it is a clean binary gate.
5. **Quest pass is pending.** No Quest result is implied by the Monado or
   regression results.

## Next steps

1. Approve W1 coordinate calibration: the latest orthographic marker sheet
   shows muzzle/trigger/top on the expected landmarks.
2. Only after W1 approval, design the `socketed` Glock rig and start the native
   mesh blockout.
3. Keep the legacy route working; do not deploy a native asset until W0/W1/W2
   pass. Resolve the A2 attachment-float tolerance separately.

## Evidence

A gate result is only current if it is reachable from
`out/qa/<gate-id>/latest`. Do not cite an old `out/evidence` directory; that
root was retired on 2026-10-31. If a gate has no run, record it as `pending`,
not as passed.
