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
| `A1` | Assets | retired | — | — | monado | `gate-runner` |
| `A2` | Assets | active | `scripts/check_mdl_roundtrip.sh assets/valve_vr/models/v_crossbow.mdl` | `out/qa/A2/latest` | monado | `gate-runner` |
| `A3` | Assets | active | `python3 scripts/check_hand_asset.py --model assets/valve_vr/models/v_hand.mdl` | `out/qa/A3/latest` | monado | `gate-runner` |
| `A4` | Assets | active | `./scripts/test_gate0_hands.sh` | `out/qa/A4/latest` | monado | `gate-runner` |
| `A5` | Assets | active | `python3 scripts/check_grip_seat.py <M1 engine log>` | `out/qa/A5/latest` | monado | `gate-runner` |
| `A6` | Assets | active | `python3 scripts/verify_grip_pose_math.py` | `out/qa/A6/latest` | monado | `gate-runner` |
| `A7` | Interaction | active | `./scripts/test_manual_reload.sh` | `out/qa/A7/latest` | monado | `gate-runner` |
| `A8` | Assets | active | `python3 scripts/check_viewmodel_names.py` | `out/qa/A8/latest` | monado | `gate-runner` |
| `A9` | Assets | review | `python3 scripts/check_weapon_bore.py` | `out/qa/A9/latest` | monado | `gate-runner` |
| `B1` | Assets | retired | — | — | monado | `gate-runner` |
| `S1` | Assets | active | `python3 scripts/check_hand_curl_axis.py --model assets/valve_vr/models/v_hand.mdl` | `out/qa/S1/latest` | monado | `gate-runner` |
| `P1` | Assets | active | `python3 scripts/check_viewmodel_names.py` | `out/qa/P1/latest` | monado | `gate-runner` |
| `P2` | Assets | active | `python3 scripts/measure_bore_basis.py --dir assets/valve_vr/models/native --json out/qa/P2/bore_ground_truth.json` | `out/qa/P2/latest` | monado | `gate-runner` |
| `P3` | Assets | active | `python3 scripts/generate_mod_profile.py --ground-truth out/qa/P2/bore_ground_truth.json --gamedir valve --models-dir assets/valve_vr/models/native --out out/qa/P3/valve_vr_weapons.json` | `out/qa/P3/latest` | monado | `gate-runner` |
| `S2` | Assets | active | `python3 scripts/check_hand_skeleton_map.py --model assets/valve_vr/models/v_hand.mdl` | `out/qa/S2/latest` | monado | `gate-runner` |
| `M1` | Engine | active | `./scripts/test_simulated_monado.sh` | `out/qa/M1/latest` | monado | `gate-runner` |
| `R1` | Engine | active | `./scripts/run_regression_battery.sh` | `out/qa/R1/latest` | monado | `gate-runner` |
| `R2` | Engine | active | `./scripts/test_roll_alignment.sh` | `out/qa/R2/latest` | monado | `gate-runner` |
| `T1` | Tests | active | `python3 scripts/check_assertion_integrity.py --script scripts/test_simulated_monado.sh --log out/qa/M1/latest/monado_unittest_engine.log --captures out/qa/M1/latest` | `out/qa/T1/latest` | monado | `gate-runner` |
| `Q1` | Quest | pending | `./scripts/test_quest_auto.sh 25 crossfire` | `out/qa/Q1/latest` | quest | `quest-tester` |
| `W0` | Weapons | active | `./scripts/test_native_weapon_fallback.sh` | `out/qa/W0/latest` | monado | `gate-runner` |
| `W1` | Weapons | review | `blender --background --factory-startup --python scripts/calibrate_weapon_coordinates.py -- --out out/qa/W1/latest` | `out/qa/W1/latest` | monado | human |
| `V1` | Assets | review | `./scripts/compare_weapon_review.sh` | `out/qa/V1/latest` | monado | human |
| `V3` | Engine | active | `python3 scripts/check_weapon_alignment.py --log out/qa/M1/latest/monado_unittest_engine.log` | `out/qa/V3/latest` | monado | `gate-runner` |

`A4` and any visual asset gate require a labeled comparison sheet and explicit
maintainer approval. Green automated checks do not prove appearance.

## Pass rules

- `A1` is retired 2026-11-09. It audited the abandoned MMOD Glock decompile;
  its source working set and evidence were removed in the cleanup. Do not run
  it or cite its old result.
- `H1` passes when no review image, audit directory, score file or evidence
  manifest exists outside `out/qa`. Working sets may keep source SMDs, textures
  and compiled MDLs, but not generated evidence.
- `W0` passes when the native route is selected with the native file present
  and the engine falls back to legacy with the native file removed.
- `W1` is a human-reviewed calibration gate. It passed on 2026-11-01 when the
  maintainer approved the barrel-bore, trigger, rear-sight and hammer markers
  in `out/qa/W1/latest/calibration_sheet.png`. Generated images alone are not a
  pass.
- `W2` is retired 2026-11-09. The cosmetic guard/trigger modelling work and its
  evidence were removed; the shipped native Glock is adopted unmodified. The
  live blockers (shot vector and hand skeleton) and their acceptance criteria
  are recorded in [`STATUS.md`](STATUS.md). Do not recreate a W2 gate.
- `M1` passes only when all 49 assertions pass and the run is not cut off by
  the engine timeout. The suite default is 120 seconds.
- `R1` passes only when all 19 assertions pass.
- `R2` passes only when the authored barrel/aim alignment holds (angle <= 8
  degrees, `in_front=1`) at wrist roll 0, 45, 90 and 180 for the Glock. This
  catches the Euler-trap error the playbook measured at 10.70/19.85/28.21
  degrees; `M1` forces hand angles to zero and cannot see it.
- `A2` passes only when bones, sequences, events, bodygroups and attachments
  survive the mdldec -> pxstudiomdl roundtrip.
- `A9` is a read-only diagnostic that compares `muzzle_pos -> muzzle_pos2` with
  the weapon body's long hitbox axis for every native barrel weapon. That pair
  is a lateral muzzle-flash quad, not the bore, so a non-zero angle is expected.
  `A9` is an asset diagnostic recorded as FINDING; it never gates automation.
- `B1` is retired 2026-11-11. Its asset-level bore override was wrong
  (model-space axis injected into world-space bone math). The bore is now the
  runtime grip->muzzle vector; see D-027. Do not recreate B1.
- `S1` passes only when the measured finger curl axis is the bone's local Z
  (`|dot| >= 0.9`) for both the proximal and middle phalanx. `--legacy-y`
  must exit 1 (negative control). It fails if `v_hand.mdl` is recompiled
  with a different axis convention.
- `S2` passes only when the name/index map has unique indices, maps `Root` and
  `Wrist`, and maps at least two phalanges per finger. The OpenVR 31-bone enum
  is a semantic GUIDE only; the Quest 3 runtime input contract is OpenXR. No
  OpenVR runtime dependency may be added.
- `Q1` passes only with a non-black engine eye dump, OpenXR startup lines, and
  no native crash. `adb exec-out screencap` is black in VR and is not valid
  evidence.
- `V3` is the maintainer's simulator acceptance gate. It passes only when every measurable weapon reports `angle <= 8` degrees between the AUTHORED two-point barrel basis (attachment 0 `muzzle_pos` -> attachment 2 `hud_pos`) and the firing/laser direction, every muzzle is `in_front=1`, at least 6 weapons are measurable, and no row is `UNKNOWN`. Weapons with `muzzle_attachment -1` (melee/toss/placeable) are `N/A` and excluded. `--ground-truth` cross-checks the offline bone-position measurement from `P2`; `--allow-unknown` is for Bronze-tier mods only. `R2` additionally requires the alignment to hold at wrist roll 0/45/90/180. Never mark `V3` PASS from an older run, and do not request Quest 3 HIL while `V3` or `R2` is red.
- `V1` is a non-blocking human review artifact. It produces labelled turntable
  and animation GIFs; it never gates automation and is not counted as a pass
  or fail.

- `P2` measures the authored two-point barrel basis from the MDL skeleton
  bone positions only. Mesh vertices from `mdldec` are in a DIFFERENT
  coordinate space and must not be used for PCA. LOW-confidence bases are
  reported as `UNKNOWN` by `V3`, never as a pass.

- `P1` is the mod-intake inventory gate. Pass `--overlay-dir <gamedir>/models`
  (and `--no-native-subdir` when the mod has no `native/` folder) to
  inventory another Xash3D mod against the HLSDK-requested viewmodel
  names. A case mismatch means the bundled model is silently ignored on
  case-sensitive filesystems. Intake findings belong in the mod's row of
  `STATUS.md` `## Mod port status`; they do not change the `valve` gates.

- `P3` passes only when the generated v2 profile has unique weapon keys,
  canonical HLSDK case, `pitch_adjust` 0 for every entry,
  `bore_basis_attachment` 2 for measurable weapons, and at least one entry. It
  generates DATA for a Silver-tier gamedir; it never edits MDLs or DLLs.
  LOW-confidence bases must be reported, never promoted to a pass. NOTE:
  `bore_basis_attachment` is declarative metadata for the next stage; the
  engine currently uses the fixed 0->2 bone-name contract, so a per-mod index
  override is not wired yet.
