# Testing

All commands run from the repository root. The default local target is the
simulated Monado runtime; Quest hardware is optional and is requested by the
maintainer per stage.

## Build

Desktop Linux PCVR:

```sh
./waf configure --enable-openxr --enable-gl-vr
./waf build
./waf install --destdir=./out
```

Meta Quest standalone:

```sh
./scripts/build_quest_apk.sh
adb install -r out/xash3d-vr-quest.apk
./scripts/deploy_quest_assets.sh valve /sdcard/xash
```

`build_quest_apk.sh` rebuilds the arm64-v8a native libraries before packaging.
A stale APK is the most common false negative in hardware testing.

## Monado unit suite (`M1`)

```sh
./scripts/test_simulated_monado.sh
```

The suite runs 44 assertions and writes to `out/qa/M1/runs/<timestamp>/`. The
default engine timeout is 90 seconds. If the unarmed-hand phase is cut off,
raise it explicitly:

```sh
TIMEOUT_SECS=120 ./scripts/test_simulated_monado.sh
```

A pass requires all 44 assertions and the two unarmed captures
`unit_23_unarmed_rest.png` and `unit_24_unarmed_moved.png`.

## Regression battery (`R1`)

```sh
./scripts/run_regression_battery.sh
```

The battery runs 19 assertions across the engine, renderer, OpenXR input,
launcher and APK. It writes to `out/qa/R1/runs/<timestamp>/`.

## Asset gates

```sh
python3 scripts/audit_holes.py \
    --model out/mmod_import/decompiled/v_9mmhandgun \
    --out out/qa/A1/latest

python3 scripts/audit_viewmodel_assets.py \
    --decompiled-dir out/mmod_import/decompiled \
    --out out/qa/A1/latest/asset_audit

scripts/check_mdl_roundtrip.sh assets/valve_vr/models/v_crossbow.mdl

python3 scripts/check_hand_asset.py \
    --model assets/valve_vr/models/v_hand.mdl

python3 scripts/check_viewmodel_names.py

python3 scripts/verify_grip_pose_math.py
```

`check_mdl_roundtrip.sh` is the pilot gate for any mesh edit: it must reproduce
the original bones, sequences, events, bodygroups and attachments before the
mesh is modified.

## Grip seating

Grip seating is measured from the `M1` engine log:

```sh
python3 scripts/check_grip_seat.py out/qa/M1/latest/monado_unittest_engine.log
```

The expected worst-case seat error is at most `0.001` world units. The
crossbow foregrip is a separate socket; do not merge it with the right-hand
grip.

## Visual comparison

```sh
scripts/render_weapon_hand_check.sh out/qa/A4/latest/compare
scripts/render_hand_check.sh assets/valve_vr/models/v_hand.mdl out/qa/A4/latest/hand
```

Visual evidence is a labeled comparison sheet from a fixed camera. A green
automated gate does not prove appearance. The maintainer approves or rejects
the sheet before an asset is deployed.

## Canonical Blender weapon harness

Use this for A/B modeling and human review. It imports the main body in raw
decompile model space, removes the authored helper box, loads BMP textures, and
renders fixed views plus a turntable:

```sh
blender --background --factory-startup \
    --python scripts/blender_weapon_review.py -- \
    --qc out/ab/entry_a/patched/v_9mmhandgun.qc \
    --out out/qa/AB/neutral/entry_a_patched \
    --label entry_a_patched \
    --body glock_reference
```

The harness writes `muzzle.png`, `rear.png`, `right.png`, `left.png`,
`top.png`, `bottom.png`, `quarter.png`, `turntable_frames/`, and
`render_manifest.json`. `muzzle.png` is the close-up front view. It is review
tooling, not a model editor.

## Weapon visual review (non-blocking)

This is a human review aid, not a gate. It does not decide PASS/FAIL and does
not block automation.

```sh
./scripts/compare_weapon_review.sh
```

The wrapper captures the original and patched Glock, then writes labelled
comparison artifacts to `out/qa/V1/compare_glock/`:

- `turntable_compare.gif` — 36 azimuth frames at 15° elevation.
- `elevation_compare.gif` — front three-quarter from below to above.
- `reload_compare.gif` — staged reload at azimuth 0.
- `contact_sheet_compare.png` — three key views.

For a single model:

```sh
./scripts/capture_weapon_review.sh \
    out/viewmodel_work/glock_repair/v_9mmhandgun.mdl glock_repair
```

The capture uses the engine world-space review camera
(`vr_test_camera 5`) and hides the baked hands. The orbit controls are
`vr_test_camera_azimuth` and `vr_test_camera_elevation`. The script captures
idle, fire and reload at three azimuths and writes GIFs to the review run.

The model is copied temporarily to `out/valve/models` and
`out/valve_vr/models` and restored on exit. Nothing is deployed.

## Manual reload

```sh
./scripts/test_manual_reload.sh
```

This runs the Glock staged reload vertical slice and writes its engine log and
captures to the evidence directory it prints.

## Quest hardware-in-the-loop (`Q1`)

Quest validation is a maintainer decision. When requested:

```sh
adb install -r out/xash3d-vr-quest.apk
./scripts/deploy_quest_assets.sh valve /sdcard/xash
./scripts/test_quest_auto.sh 25 crossfire
```

Facts that prevent false negatives:

- `adb exec-out screencap` is black in VR. Use `quest screenshot` or the
  engine's `vr_eye0.png`.
- `adb input tap` is a no-op inside a native VR app. Use `quest elements` and
  `quest tap` for 2D panels, and `vr_test_*` cvars for the engine.
- The Quest 3S panel is `3664x1920`; the engine eye dump may be smaller.
- If the foreground activity is
  `com.oculus.os.vrusb/.WifiDebuggingAlertActivity`, dismiss it and force-stop
  `quest.side.vr`.
- Run `quest mount off` after off-head work.

## Evidence policy

- Every gate uses `out/qa/<gate-id>/`.
- `out/qa/<gate-id>/latest` points to the newest run.
- `out/qa/INDEX.md` is generated by `scripts/qa_evidence.py`.
- `H1` enforces that images, audit folders, score files and evidence manifests
  stay under `out/qa`; working sets keep source meshes, textures and compiled
  MDLs only.
- `out/evidence` was retired on 2026-10-31. Do not cite it.
- Generated evidence, build caches and APKs are not committed.
- A result is stale if the manifest commit does not match the commit under
  test.

## What counts as a pass

A pass needs the command exit code, the expected assertions, and the required
artifacts. A screenshot of the Monado compositor window is not engine evidence.
A black `screencap_os.png` is expected in VR. A Quest pass needs a non-black
engine eye dump and no native crash.
