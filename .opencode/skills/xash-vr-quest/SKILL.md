---
name: Xash3D VR on Quest
description: Build, deploy, launch, and verify the Xash3D VR port on a connected Meta Quest (hardware-in-the-loop). Use when testing the Quest APK, deploying v_hand.mdl or vr_weapons.json, capturing the engine eye buffer, driving vr_test_* hooks, or reading Quest logcat and crash reports for this repository.
---

# Xash3D VR on Quest (hardware-in-the-loop)

Run every command below from the repository root (`xash3d-fwgs-vr/`).

Device I/O (screenshot, UI taps, VR launch, video, off-head mount) lives in the
generic `quest` skill: `.opencode/skills/quest/SKILL.md` and
`.opencode/skills/quest/scripts/quest`. This skill is the project loop around
that CLI.

## Preconditions

```sh
.opencode/skills/quest/scripts/quest doctor   # "ok": true, model Quest 3S/3/2
.opencode/skills/quest/scripts/quest state    # lockScreen must be false
```

If `lockScreen` is true, unlock with `quest elements` + `quest tap --text
"<profile>"`, or run `quest mount on` and tap the profile tile. Off-head
launches fail with "window placement timeout" while the lock screen is up.

The package is `su.xash.engine.vr.test`, the VR activity is
`su.xash.engine.XashActivity`, and the engine reads its game data from
`/sdcard/xash`.

## The full gate, one command

```sh
scripts/test_quest_auto.sh 25 crossfire
```

It wakes the headset, force-stops competing VR apps, installs
`out/xash3d-vr-quest.apk`, grants storage/audio/Bluetooth
permissions, clears logcat, launches the map, records logcat for 25 s, pulls
`/sdcard/xash/vr_eye0.ppm` if the engine produced it, and exits 0 only when all
OpenXR checks pass.

Evidence: `out/evidence/quest_<YYYYmmdd_HHMMSS>/`

- `logcat_quest.log` - full device log for the run.
- `vr_eye0.ppm` / `vr_eye0.png` - the engine's left-eye swapchain. This is the
  visual truth; check that it is not solid black.
- `screencap_os.png` - Android's `screencap`. **Expected to be black in VR.**
  Do not use it to judge rendering; use `vr_eye0.png` or `quest screenshot`.

It greps for these pass lines:

- `xrInitializeLoaderKHR initialized successfully`
- `xrCreateInstance` (and not `xrCreateInstance failed`)
- `OpenGL ES Meta Quest Standalone Graphics Binding initialized successfully`
- `XrSession created`
- `Stereo swapchains created`
- `xrBeginSession started successfully` or `R_SetupXREyeFbos`
- no `Fatal signal` / `DEBUG   : crash`

## Build and deploy (when the APK or assets changed)

```sh
scripts/build_quest_apk.sh          # -> out/xash3d-vr-quest.apk
scripts/deploy_quest_assets.sh valve /sdcard/xash
```

`deploy_quest_assets.sh` pushes `v_hand.mdl` and `vr_weapons.json` into
`/sdcard/xash/valve/models/` and verifies the hand model's sha256. The APK
bundles `valve_vr`, but the engine launches the base `valve` gamedir, so the
APK alone does not update the hand model or weapon profiles.

A stale APK is the most common false negative in this loop. Rebuild after any
engine, renderer, or `vr_weapons.json` change before drawing conclusions from a
headset capture.

## Manual loop (specific cfg, probes, calibration)

1. Write a cfg and push it:

   ```sh
   cat > out/hil.cfg <<'EOF'
   vr_test_hands 1
   vr_grip_probe 1
   vr_foregrip 1
   vr_dumpeye hil_eye0.ppm
   EOF
   .opencode/skills/quest/scripts/quest push out/hil.cfg /sdcard/xash/valve/hil.cfg
   ```

2. Install and grant, if the APK changed:

   ```sh
   .opencode/skills/quest/scripts/quest install out/xash3d-vr-quest.apk
   .opencode/skills/quest/scripts/quest storage-grant su.xash.engine.vr.test
   ```

3. Launch with the engine extras plus the cfg:

   ```sh
   .opencode/skills/quest/scripts/quest sh "am start -a android.intent.action.MAIN \
     -c com.oculus.intent.category.VR \
     -n su.xash.engine.vr.test/su.xash.engine.XashActivity \
     --es gamedir valve --es basedir /sdcard/xash \
     --es argv '-dev 2 +map crossfire +exec hil.cfg'"
   ```

4. Wait for a log line instead of sleeping:

   ```sh
   .opencode/skills/quest/scripts/quest logs Xash --grep "DUMPED OpenXR Eye|R_SetupXREyeFbos" --lines 4000
   ```

5. Capture and stop:

   ```sh
   .opencode/skills/quest/scripts/quest screenshot out/evidence/hil_view.jpg --width 1024
   .opencode/skills/quest/scripts/quest pull /sdcard/xash/hil_eye0.ppm out/evidence/hil_eye0.ppm
   .opencode/skills/quest/scripts/quest stop su.xash.engine.vr.test
   ```

The engine also auto-dumps eye 0 once, after 60 rendered frames, to
`/sdcard/xash/vr_eye0.ppm` (`ref/gl_vr/gl_rmain.c:2093-2096`).
On a slow first run that can take longer than 25 s, which is why a cfg with
`vr_dumpeye` is the deterministic recipe.

## Test hooks

All are sampled every frame; set to `1` to inject and back to `0` to release.
They are not edge-triggered.

| Cvar | Effect |
|---|---|
| `vr_test_hands 1` | Pins both hand poses in front of the eyes (any nonzero). Use off-head when controllers are on the desk. |
| `vr_test_hand_pitch` / `vr_test_hand_yaw` | Aim offsets for the pinned hands, in degrees. |
| `vr_test_click 1` / `2` | Main-hand click / off-hand click. `2` is also the head-flashlight gesture path. |
| `vr_test_btn_reload` | Main-hand reload (B). |
| `vr_test_btn_altfire` | Grip + trigger alt-fire (`attack` + main grip). |
| `vr_test_btn_jump` | Main-hand jump (A). |
| `vr_test_btn_reload_left` / `vr_test_btn_jump_left` | Left-hand variants. |
| `vr_test_btn_menu` | Menu button. |
| `vr_test_offhand_grip 1` | Full off-hand grip squeeze; drives the foregrip attach path. |
| `vr_test_stick_x` / `vr_test_stick_y` | Simulated thumbstick. |
| `vr_test_finger_curl 1` | Curls the finger axes for hand-pose work. |
| `vr_grip_probe 1` | Logs `[VR_GRIP_BONE]` for the active viewmodel. `2` logs every hand/arm landmark as `[VR_GRIP_BONES]`. |
| `vr_foregrip 0` / `1` | Disable/enable snapping the off-hand palm to the weapon foregrip socket (default 1). |
| `vr_dumpeye [file]` | Dumps eye 0 on the next render to `/sdcard/xash/<file>` (default `vr_eye0.ppm`). |

Definitions: `engine/platform/openxr/xr_core.c:310-345` and the
input merge at `engine/platform/openxr/xr_input.c:384-408`.

## Reading a failed run

1. `quest crashes su.xash.engine.vr.test` - native crashes land in the crash
   buffer, not the main log.
2. `quest logs Xash --grep "Fatal signal|AndroidRuntime|ERROR|failed" --lines 4000`
3. `quest logs --grep "xrInitializeLoaderKHR|xrCreateInstance|XrSession|Stereo swapchains" --lines 4000`
4. `quest foreground` - if the top activity is
   `com.oculus.os.vrusb/.WifiDebuggingAlertActivity`, dismiss it with
   `quest tap --text "Cancelar" --exact` and force-stop `quest.side.vr`.
5. `quest state` - asleep or locked produces "window placement timeout", not an
   app crash.
6. `quest screenshot` - confirms whether the compositor is showing the app even
   when the logs look ambiguous.

## Gotchas

- `screencap_os.png` is black by design in VR; `test_quest_auto.sh` keeps it for
  completeness. Judge the frame from `vr_eye0.png` or `quest screenshot`.
- `quest_battery.sh` maps `Quest_3S` to "Quest 3" for its banner
  (`scripts/quest_battery.sh:106`). Use
  `adb shell getprop ro.product.model` for the exact model.
- The test script deletes `/sdcard/xash/vr_eye0.ppm` at the start of each run.
  If the app renders fewer than 60 frames, there is no dump; use `vr_dumpeye`.
- `adb install -r` of the same version replaces the app; no uninstall needed.
  The engine data on `/sdcard/xash` survives reinstall.
- Wi-Fi debugging dialogs steal focus and block VR window placement. They are a
  SideQuest (`quest.side.vr`) side effect; force-stop that app if they keep
  appearing.
- Quest 3S panel is `3664x1920` (per eye `1832x1920`). Engine eye dumps from a
  Quest 3S may be `1512x1584` because the swapchain resolution is lower than the
  panel; that is expected, not a bug.

## File map

| Path | Role |
|---|---|
| `scripts/test_quest_auto.sh` | End-to-end HIL gate (install, launch, logcat, evidence). |
| `scripts/build_quest_apk.sh` | Gradle build -> `out/xash3d-vr-quest.apk`. |
| `scripts/deploy_quest_assets.sh` | Push hand model and weapon profiles to `/sdcard/xash/valve/models/`. |
| `scripts/quest_battery.sh` | Battery/thermal display, `raw`, `json`, `watch`. |
| `scripts/quest_proximity.sh` | `disable` / `enable` / `status` proximity automation. |
| `scripts/test_quest_launcher.sh` | 2D `MainActivity` launcher UI test with screenshots and XML. |
| `ref/gl_vr/gl_rmain.c` | Eye readback and the 60-frame auto dump. |
| `engine/platform/openxr/xr_core.c` | Test cvars and defaults. |
| `assets/valve_vr/models/vr_weapons.json` | Per-weapon grip/foregrip data deployed to the device. |
| `.opencode/skills/quest/scripts/quest` | Device CLI used by every command above. |
