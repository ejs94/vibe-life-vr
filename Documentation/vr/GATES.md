# Gates

This is the single gate registry. A gate is active only if it has a row here.
Do not create a separate specification document for each gate.

## How to use a gate

1. Read the row and run exactly the listed command from the repository root.
2. Write the result under `out/qa/<gate-id>/` using `scripts/qa_evidence.py`
   when the command supports it.
3. Record `PASS`, `FAIL` or `INCONCLUSIVE` in the run manifest.
4. Ask the maintainer to record `ADVANCE`, `REWORK` or `BLOCK` in
   `manifest.json` under `human_decision` when the gate is visual or risky.
5. Never mark a gate passed from an older run. If `out/qa/<id>/latest` is not a
   run for the current commit, the result is stale.

## Device modes

| Mode | Meaning |
|---|---|
| `monado` | Simulated or desktop OpenXR on Linux. This is the default local gate. |
| `quest` | Meta Quest hardware-in-the-loop. The maintainer decides when to run it. |
| `both` | Required on Monado and Quest. |
| `pending` | Not yet run. This is not a pass. |

## Evidence

Each run directory contains:

```text
manifest.json   commit, branch, dirty state, device, command, status, artifacts
result.json     final status and artifact checksums
*.log           command and engine logs
*.png           visual captures
```

A run is created with:

```sh
python3 scripts/qa_evidence.py new --gate M1 --command "./scripts/test_simulated_monado.sh" --device monado
```

and finished with:

```sh
python3 scripts/qa_evidence.py finish --run out/qa/M1/runs/<timestamp> --exit-code 0 --status PASS --device monado
```

The helper updates `out/qa/<gate>/latest` and `out/qa/INDEX.md`.

## Registry

| ID | Epic | Status | Command | Evidence | Device | Agent |
|---|---|---|---|---|---|---|
| `D1` | Docs | active | `python3 scripts/check_docs.py` | `out/qa/D1/latest` | monado | `gate-runner` |
| `H1` | Hygiene | active | `python3 scripts/check_evidence_hygiene.py` | `out/qa/H1/latest` | monado | `gate-runner` |
| `A1` | Assets | active | `python3 scripts/audit_holes.py --model out/mmod_import/decompiled/v_9mmhandgun --out out/qa/A1/latest` | `out/qa/A1/latest` | monado | `gate-runner` |
| `A2` | Assets | active | `scripts/check_mdl_roundtrip.sh assets/valve_vr/models/v_crossbow.mdl` | `out/qa/A2/latest` | monado | `gate-runner` |
| `A3` | Assets | active | `python3 scripts/check_hand_asset.py --model assets/valve_vr/models/v_hand.mdl` | `out/qa/A3/latest` | monado | `gate-runner` |
| `A4` | Assets | active | `./scripts/test_gate0_hands.sh` | `out/qa/A4/latest` | monado | `gate-runner` |
| `A5` | Assets | active | `python3 scripts/check_grip_seat.py <M1 engine log>` | `out/qa/A5/latest` | monado | `gate-runner` |
| `A6` | Assets | active | `python3 scripts/verify_grip_pose_math.py` | `out/qa/A6/latest` | monado | `gate-runner` |
| `A7` | Interaction | active | `./scripts/test_manual_reload.sh` | `out/qa/A7/latest` | monado | `gate-runner` |
| `A8` | Assets | active | `python3 scripts/check_viewmodel_names.py` | `out/qa/A8/latest` | monado | `gate-runner` |
| `M1` | Engine | active | `./scripts/test_simulated_monado.sh` | `out/qa/M1/latest` | monado | `gate-runner` |
| `R1` | Engine | active | `./scripts/run_regression_battery.sh` | `out/qa/R1/latest` | monado | `gate-runner` |
| `Q1` | Quest | pending | `./scripts/test_quest_auto.sh 25 crossfire` | `out/qa/Q1/latest` | quest | `quest-tester` |
| `W0` | Weapons | active | `./scripts/test_native_weapon_fallback.sh` | `out/qa/W0/latest` | monado | `gate-runner` |
| `W1` | Weapons | review | `blender --background --factory-startup --python scripts/calibrate_weapon_coordinates.py -- --out out/qa/W1/latest` | `out/qa/W1/latest` | monado | human |
| `W2` | Weapons | blocked | — | `out/qa/W2/latest` | monado | human |
| `V1` | Assets | review | `./scripts/compare_weapon_review.sh` | `out/qa/V1/compare_glock` | monado | human |

`A4` and any visual asset gate require a labeled comparison sheet and explicit
maintainer approval. Green automated checks do not prove appearance.

## Pass rules

- `A1` passes when the tool completes, every boundary loop is classified or
  explicitly `uncertain`, the defect table and review sheets exist, and the
  input hashes are recorded. The asset verdict is recorded separately as
  `asset_verdict`; a complete audit may still be `asset_verdict: FAIL`.
- `H1` passes when no review image, audit directory, score file or evidence
  manifest exists outside `out/qa`. Working sets may keep source SMDs, textures
  and compiled MDLs, but not generated evidence.
- `W0` passes when the native route is selected with the native file present
  and the engine falls back to legacy with the native file removed.
- `W1` is a human-reviewed calibration gate. It passed on 2026-11-01 when the
  maintainer approved the barrel-bore, trigger, rear-sight and hammer markers
  in `out/qa/W1/latest/calibration_sheet.png`. Generated images alone are not a
  pass.
- `W2` is blocked as of 2026-11-01. The source-derived attempt reproduced MMOD
  mesh defects and was rejected; its run is archived under `out/qa/W2/`. Do not
  resume paid-agent geometry work before a budget/quality decision and a clean
  or human-retopologized base mesh. A future W2 must show SIDE, MUZZLE, TOP and
  3/4 views with distinct trigger contact and pivot markers; numeric checks do
  not prove appearance.
- `M1` passes only when all 47 assertions pass and the run is not cut off by
  the engine timeout. The suite default is 90 seconds.
- `R1` passes only when all 19 assertions pass.
- `A2` passes only when bones, sequences, events, bodygroups and attachments
  survive the mdldec -> pxstudiomdl roundtrip.
- `Q1` passes only with a non-black engine eye dump, OpenXR startup lines, and
  no native crash. `adb exec-out screencap` is black in VR and is not valid
  evidence.
- `V1` is a non-blocking human review artifact. It produces labelled turntable
  and animation GIFs; it never gates automation and is not counted as a pass
  or fail.
