# Eyes and hands on a Quest

Why the obvious adb commands "work" and show you nothing, and what to run
instead. Verified on a Quest 3S (`Quest_3S`, Android 14, panel `3664x1920`).

## The one fact

A Quest does not put the VR scene on the Android display. The VR compositor
samples the app's eye swapchains directly. Android still has a display, still
composites 2D panels and system dialogs, and `screencap` still returns a valid
PNG of it - usually black, because nobody is looking at that surface.

Everything below follows from that:

| Need | Wrong tool | What you get | Right tool |
|---|---|---|---|
| Screenshot | `adb exec-out screencap -p` | black PNG | `quest screenshot out.jpg` |
| Video | `adb shell screenrecord` | black MP4 | `quest-vr-record start out.mkv` |
| Tap a system dialog | coordinates from a screenshot | nothing | `quest elements` then `quest tap --text` |
| Tap inside a native VR app | `adb shell input tap` | exit 0, no effect | the app's own debug hook |
| Launch a VR app | `monkey -c LAUNCHER` | the flat 2D activity | `quest vr-launch <pkg>` |

## Eyes

### The Meta capture service

`quest screenshot` starts `com.oculus.metacam/.capture.CaptureService` with
`TAKE_SCREENSHOT`, waits for a new row in MediaStore, and reads it back with
`content read --user <wearer>`. The result is the wearer's view as a JPEG,
including the VR scene, 2D panels, and system dialogs.

- The service ignores a plain `am start` to the metacam activity; it is a
  service, not an activity.
- Captures land in the **wearer's** Android user, often user 10, which the adb
  shell cannot read directly. Always pass `--user`.
- `--width` / `--height` are forwarded as `screenshot_width` /
  `screenshot_height` extras. A 1024-wide capture is enough to inspect layout.
- If no file appears within ~15 s, the headset is probably asleep or on the
  profile lock screen. Check `quest state` before debugging the app.

### The app's own eye buffer

Xash3D VR can dump eye 0 from inside the engine:

```text
vr_dumpeye [filename]
```

On Android the file is written to `/sdcard/xash/<filename>` (default
`vr_eye0.ppm`) on the next eye-0 render:
`ref/gl_vr/gl_rmain.c:1761` and the confirmation line at
`ref/gl_vr/gl_rmain.c:1787`. The command is registered in
`ref/gl_vr/gl_opengl.c:1294`.

This is the app's raw swapchain image, not the compositor's view. Use it when
you need exact pixels or the render resolution. Pull it with:

```sh
.opencode/skills/quest/scripts/quest pull /sdcard/xash/vr_eye0.ppm out/evidence/
```

`vr_eye0.ppm` is a binary PPM; `ffmpeg` or Pillow converts it to PNG.

### Video

`adb shell screenrecord` captures an Android surface the VR compositor bypasses.
`quest-vr-record` uses `scrcpy`, which reads the panel framebuffer; the headset
encoder does the work and no window opens on the desktop. Default framing is a
level 16:9 crop of the left eye, computed from `wm size`:

- Quest 3S panel `3664x1920` -> each eye `1832x1920` -> left crop `1832x1030`
  centred vertically.
- `both` records the full side-by-side panel downscaled to 1920 wide.
- `--raw` keeps the full eye (`1832x1920`).
- Pass `--angle N` only if the capture is tilted. The Quest 3S eye buffer is
  already level.

## Hands

### 2D panels, dialogs, and the lock screen

These **are** Android windows. `uiautomator dump --windows` sees them, including
multiple windows at once. Resolve the selector on every tap so a layout change
cannot leave a stale coordinate:

```sh
quest elements
quest tap --text "Cancel" --exact
quest wait-for --text "Cancel" --gone --timeout 5
```

`adb shell input tap x y` also works for these windows, but the coordinates in
the dump are in the panel's view space. Text resolution is safer.

### Native VR apps

`adb shell input tap` returns success and does nothing inside a native VR app:
there is no Android view tree and no touch surface. The only reliable input is
a debug-only hook in the app:

- a file in the app's external files directory that the test build polls each
  frame, with lines such as `a=1`, `trigger=1`, or a pinned hand pose;
- adb can write that directory without root;
- log one line when a menu opens or a stage loads, then wait on that line with
  `quest logs --grep` instead of sleeping.

For this repository the hook already exists as cvars, so the Quest loop can
drive the engine without touching the controllers. See the `xash-vr-quest`
skill for the exact run.

## Off-head operation

Meta Quest Scriptable Testing (MQST) is a content provider that lets the OS
believe the headset is worn and keep autosleep off:

```sh
quest mount status            # read-only, no PIN
quest mount on --pin 1234     # or export QUEST_MQST_PIN
quest mount off --pin 1234
```

The provider is `content://com.oculus.rc` with `SET_PROPERTY` extras for
`set_proximity_close`, `disable_autosleep`, `disable_dialogs`, and
`disable_guardian`. `GET_PROPERTY` needs no PIN. The PIN is the store PIN of
the Meta account on **Android user 0**, not necessarily the person wearing the
headset.

Ground truth is `dumpsys vrpowermanager`: `State: HEADSET_MOUNTED`,
`Virtual proximity state: CLOSE`, `isAutosleepDisabled: true`. `quest mount
status` prints both the provider reply and that dump.

Real-world failure mode: off-head, the profile lock screen stays up. Every
launch then reports "window placement timeout" and the resumed activity is
`com.oculus.vrshell/.FocusPlaceholderActivity`. Check `quest state` first;
unlock with `quest elements` and `quest tap --text "<profile>"`.

## Launching a VR app

`monkey -p <pkg> -c android.intent.category.LAUNCHER 1` starts the 2D launcher
activity. For the VR activity, find the component that declares
`com.oculus.intent.category.VR` and start it explicitly:

```sh
quest vr-launch com.example.game
```

The equivalent raw command (this repository, with its engine extras) is in
`scripts/test_quest_auto.sh:95`:

```sh
am start -a android.intent.action.MAIN -c com.oculus.intent.category.VR \
  -n su.xash.engine.vr.test/su.xash.engine.XashActivity \
  --es gamedir valve --es argv '-dev 2 +map crossfire' --es basedir /sdcard/xash
```

## Files and permissions

- `adb install -g` grants runtime permissions, not "all files access".
  `quest storage-grant <pkg>` sets `MANAGE_EXTERNAL_STORAGE` for the current
  user and force-stops the app so it takes effect.
- The engine reads its gamedir from `/sdcard/xash`. Push `v_hand.mdl` and
  `vr_weapons.json` into `/sdcard/xash/valve/models/` with
  `scripts/deploy_quest_assets.sh`.
- `adb push` can write those paths without root.

## Quest 3S verified notes

- `wm size`: `3664x1920`; `scrcpy --list-displays`: display 0 is `3664x1920`.
- `quest screenshot --width 1024` returned a real JPEG of the VR scene, not a
  black surface.
- `quest-vr-record left` produced a level `1832x1030` H.264 stream at
  16 Mbit/s. `both` produced `1920x1006`.
- The Wi-Fi debugging dialog
  (`com.oculus.os.vrusb/.WifiDebuggingAlertActivity`) can steal the foreground
  and block VR window placement. Dismiss it with `quest tap --text "Cancelar"`
  / `"Cancel"`, or force-stop the app that keeps requesting it
  (`adb shell am force-stop quest.side.vr`).
- `KEYCODE_WAKEUP` is a no-op on Horizon OS. `KEYCODE_POWER` toggles; check
  wakefulness before sending it (`quest wake` does).

## Sources

- The Meta capture service, MediaStore read-back, and the scrcpy recording
  approach are adapted from the agent-playtest-skills `quest` skill.
- Engine facts: `ref/gl_vr/gl_rmain.c`,
  `ref/gl_vr/gl_opengl.c`, and
  `engine/platform/openxr/xr_core.c`.
- HIL loop: `scripts/test_quest_auto.sh`.
