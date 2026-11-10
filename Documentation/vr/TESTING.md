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

The suite runs 49 assertions and writes to `out/qa/M1/runs/<timestamp>/`. The
default engine timeout is 120 seconds. If the unarmed-hand phase is cut off,
raise it explicitly:

```sh
TIMEOUT_SECS=120 ./scripts/test_simulated_monado.sh
```

A pass requires all 49 assertions and the two unarmed captures
`unit_23_unarmed_rest.png` and `unit_24_unarmed_moved.png`.

Three of the assertions exist because the suite used to pass while the headset
misbehaved:

- `check_hand_motion.py` drives the simulated controllers through a 6DoF sweep
  and compares the measured palm with `vr_worldscale * commanded offset`, the
  forward/up frame with the commanded angles, the offhand with its own offset,
  and the anchored weapon with the moving palm. It also requires the two motion
  captures to differ.
- `check_vr_coordinates.py` walks the whole log and rejects non-finite values,
  transforms collapsed to `(0,0,0)`, hands that leave the grip origin, and
  muzzle/viewmodel pairs that disagree on their world position by more than one
  gun length (the classic view-space vs world-space mixup).
- `check_aim_pose.py` reads the `AIM_GRIP_PROBE` phase, where the simulated grip
  pose is tilted 35 degrees away from the aim pose, and requires both the
  renderer and the viewmodel to stay on the aim orientation. The suite used to
  keep the grip and aim poses identical, which is why every gun could point up
  in the headset while Monado stayed green.

Phase 2 opens the single-page **VR Play** menu (`menu_vr`), captures it as
`unit_01_menu_vr.png`, and checks the `[VR_MENU] play menu ready
maps=testbed_scale,crossfire,t0a0` line. The dual-pointer tests then run over
the console instead of the menu, so a simulated trigger click cannot start a
map in the middle of the suite. The accessibility and debug tabs are gone; the
menu is only Continue, the three test maps and Quit.

## Coordinate test bed

```sh
python3 scripts/build_testbed_map.py
```

Builds `out/valve_vr/maps/testbed_scale.bsp` (requires `VHLT_DIR` or the
`~/JACK/halflife` tools). A built copy ships as
`assets/valve_vr/maps/testbed_scale.bsp`; `scripts/deploy_quest_assets.sh`
pushes it to `/sdcard/xash/valve/maps/` and the Quest launcher also copies it
out of the APK when the Testbed option is chosen. The room has a 1 m floor
grid, so a distance is readable by counting cells, plus:

- RGB axes at the origin: red `+X`, green `+Y`, blue `+Z`, two metres long;
- a 1 m reference cube behind the axes;
- 1.0 m, 1.7 m (eye height) and 2.0 m bars on the north wall;
- distance posts at 1/2/5/10/20 m and a 1.8 m height pole near the old spawn.

`scripts/gate_testbed_hands.cfg` captures the fixed-camera hand evidence in
that room. Use it when a change affects scale, grip seating or coordinates and
the numeric checks alone are not convincing.

## Shot origin evidence

```sh
./scripts/aim_shot_evidence.sh
```

Fires one shot per hitscan gun at the test-bed board and records, per weapon:

- `start -> muzzle`: distance between where the shot starts and the visible
  muzzle attachment (must be ~0, proving the bullet leaves the barrel tip and
  not the eye or the hand);
- `vs barrel`: angle between the shot and the visible barrel axis
  (`palm -> muzzle`), which must stay under 2 degrees or the shot looks crooked;
- `axis`: perpendicular offset of the shot start from the barrel line.

Output: `out/qa/V1/shots_<timestamp>/` with `shot_origin.txt`, the engine log
and one capture per weapon. The shotgun uses an 8-degree tolerance because its
first impact is a pellet, and the gauss allows 3.5 units because its tracer
starts inside the muzzle cap. Projectile and beam weapons are out of scope: they
do not report an impact on the first frame.

## Weapon visual sweep

```sh
./scripts/weapon_visual_sweep.sh
```

Loads `testbed_scale`, equips each of the 14 native viewmodels in turn and
captures right-lateral, front and left-lateral views with a fixed camera
(distance 26, FOV 50). The scale bar and the 1 m floor grid stay in frame.
Output goes to `out/qa/V1/weapons_<timestamp>/`:

- `w_<model>_right|front|left.png`, 42 captures;
- `contact_sheet.png`, one row per weapon with a label column;
- `engine.log` with the native-route lines.

`scripts/check_weapon_captures.py` rejects missing, black or empty frames, and
`scripts/make_weapon_contact_sheet.py` builds the labelled sheet. This is a
visual review helper, not a gate: a human still judges the result, but the run
proves the route was native and every cell contains a rendered weapon.

## Regression battery (`R1`)

```sh
./scripts/run_regression_battery.sh
```

The battery runs 19 assertions across the engine, renderer, OpenXR input,
launcher and APK. It writes to `out/qa/R1/runs/<timestamp>/`.

## Asset gates

`A1` was retired on 2026-11-09. The commands below are diagnostic tools whose
output is not a gate result; active gates are listed in [`GATES.md`](GATES.md).

```sh
python3 scripts/audit_holes.py \
    --model out/mmod_import/decompiled/v_9mmhandgun \
    --out out/qa/V1/asset_diagnostics

python3 scripts/audit_viewmodel_assets.py \
    --decompiled-dir out/mmod_import/decompiled \
    --out out/qa/V1/asset_diagnostics/asset_audit

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
