---
name: Quest
description: See and drive a Meta Quest headset over adb - screenshots of the real VR eye buffer, video, UI tree and text taps, VR app launch, logs, crashes, and off-head operation. Use for Quest/Horizon OS hardware-in-the-loop work, sideloading, and validating VR apps on a physical headset.
---

# quest: eyes and hands on a Meta Quest

`scripts/quest` is a bash CLI (needs `adb`; `python3` only for the UI tree).
`scripts/quest-vr-record` records what the headset shows through `scrcpy`.
Run them from the repository root:

```sh
.opencode/skills/quest/scripts/quest doctor
.opencode/skills/quest/scripts/quest screenshot out/quest_hil/shot.jpg --width 1024
```

Structured verbs print JSON. `logs`, `crashes`, `foreground`, `apps`, and
`sh` print raw text.

## Setup, once per headset

1. Developer Mode: create a free organisation at developers.meta.com, then
   enable it for the headset in the Meta Horizon phone app.
2. Plug in a data-capable USB-C cable and put the headset on once to accept
   "Allow USB debugging". That prompt only renders inside the headset.
3. `quest doctor` should print `"ok": true` and the selected serial.
4. For off-head work you may need the store PIN of the Meta account on Android
   **user 0** (`quest users`). Export it as `QUEST_MQST_PIN`.

## The one fact everything follows from

A Quest draws through a VR compositor that bypasses the normal Android display.
Android's tools still answer, about a surface nobody is looking at.

| Need | Wrong tool (silently useless) | Right tool |
|---|---|---|
| Screenshot | `adb exec-out screencap` (black in VR) | `quest screenshot out.jpg` (Meta capture service, the real eye buffer) |
| Video | `adb shell screenrecord` (black) | `quest-vr-record start out.mkv` / `stop` |
| Click a dialog, the lock screen, a 2D panel | coordinates guessed from a screenshot | `quest elements`, then `quest tap --text "Label"` |
| Click inside a native VR app | `adb input tap` (returns success, does nothing) | the game's own test hook (see below) |
| Launch a VR app | `monkey -c LAUNCHER` (opens the flat 2D activity) | `quest vr-launch <pkg>` |

Background and the full investigation: [resources/eyes-and-hands.md](resources/eyes-and-hands.md).

## Off-head loop (headset on the desk, nobody wearing it)

```sh
quest mount on                       # OS believes it is worn, autosleep off (needs QUEST_MQST_PIN)
quest state                          # lockScreen: true? -> next two lines
quest elements                       # find your profile tile on the lock screen
quest tap --text "<profile name>"    # unlock
quest vr-launch com.example.game     # the VR activity, not the 2D one
quest screenshot shot.jpg --width 1024
quest-vr-record start run.mkv        # ... drive the flow ...
quest-vr-record stop
quest mount off                      # always put it back
```

When several unrelated launch methods fail the same way ("window placement
timeout", the resumed activity is `FocusPlaceholderActivity`), the headset is
on the profile lock screen. Check `quest state` before debugging the app.

`quest mount status` reads the Meta Quest Scriptable Testing provider without a
PIN. `mount on|off` writes need the PIN of the account on Android user 0.

## Input inside a VR game: add a test hook

There is no way to inject tracked-controller input into an arbitrary VR app
from adb. The practical answer for a game you can build is a debug-only hook:

- a small file in the app's external files dir that the test build polls each
  frame, with lines like `a=1` or `trigger=1` that it merges into controller
  input. adb can write that directory without root.
- the same file can pin a controller pose, so UI attached to a hand stays in
  front of the headset cameras while it sits on a desk.
- log one line whenever a menu opens or a stage loads, and wait on that line
  (`quest logs --grep`) instead of sleeping.

For this repository, the engine already exposes test cvars and a cfg path; see
the `xash-vr-quest` skill for the exact Quest HIL loop.

## Exact flags

| Verb | Flags |
|---|---|
| `quest [-s serial] ...` | `-s` picks a device; `QUEST_SERIAL` does the same |
| `screenshot <out.jpg>` | `--width W` `--height H` |
| `elements` | `--pkg <package>` `--all` |
| `tap` | `<x> <y>`, or `--text t` / `--id resource-id` / `--desc d`, plus `--pkg p` `--exact` `--index N` |
| `exists`, `wait-for` | same selectors; `wait-for` adds `--gone` and `--timeout S` (default 20) |
| `press <key>` | `back home enter menu volup voldown delete tab`, any `KEYCODE_*` or a number; `--source gamepad\|keyboard\|dpad\|joystick` `--long` |
| `mount on\|off\|status` | `--pin NNNN` or `QUEST_MQST_PIN` |
| `wake`, `sleep` | no flags; `wake` checks wakefulness first, `sleep` is idempotent |
| `logs [tag]` | `--grep re` `--lines N` (default 500) `--level V\|D\|I\|W\|E` |
| `crashes [pkg]` | reads the crash buffer, where native crashes land |
| `storage-grant <pkg>` | grants "all files access", which `adb install -g` does not |
| `quest-vr-record start <out.mkv> [left\|right\|both]` | `stop`, `status`; `--raw` keeps the full eye; `--angle N` rotates |

Wrong guesses: there is no `quest record` (use `quest-vr-record`);
`press wakeup` is not a key (`KEYCODE_WAKEUP` does nothing on a Quest, use
`quest wake`); `quest launch` on a VR app opens its 2D activity (use
`vr-launch`).

## Battery: sleep, wake, and stay-awake

- `quest sleep` puts the headset to sleep and `quest wake` wakes it. Both are
  idempotent: they check the current wakefulness first, so a second call does
  not toggle the headset back. `sleep` uses `KEYCODE_SLEEP` and works on the
  profile lock screen; `wake` uses `KEYCODE_POWER` and usually lands on that
  lock screen.
- `quest wake` needs a live ADB connection. After a long sleep the USB
  transport may drop; in that case press the power button. `quest wake`
  reports "no Quest attached" or "did not wake over ADB" instead of toggling
  blindly.
- `quest mount off` restores normal proximity and autosleep behavior. Use
  `quest mount on` only for off-head HIL work; it keeps the headset awake and
  drains the battery.
- `scripts/quest_proximity.sh enable` restores normal sleep timers;
  `disable` forces stay-awake. Do not leave the stay-awake path enabled after
  testing.
- For long storage, a full shutdown (`adb shell reboot -p`) saves the most
  power, but ADB disconnects; press the power button to boot again.

## Gotchas

- `quest sleep` sends `KEYCODE_SLEEP`, which works even while the profile lock
  screen is up. `quest wake` sends `KEYCODE_POWER`; `KEYCODE_WAKEUP` is a no-op
  on Horizon OS. Waking usually lands on the profile lock screen.
- ADB wake is best-effort. After a long sleep the headset can stop enumerating
  USB, so `quest wake` cannot send the key. Press the power button; that is the
  reliable wake path.
- Captures and downloads land in the wearer's Android user (often 10), which
  the adb shell cannot read; `quest screenshot` goes through MediaStore with
  `--user` for that reason.
- After a reboot, the MQST mount properties and wireless adb are both reset.
  Re-run `mount on`.
- If a control does nothing, check whether a human can use it before blaming
  input injection. A missing "all files access" grant makes some apps' buttons
  dead for everyone.
- Don't drive the headset while someone is wearing it. `quest state` reports
  the physical wear sensor.
- A stuck Wi-Fi debugging dialog (`com.oculus.os.vrusb/.WifiDebuggingAlertActivity`)
  can steal the foreground and block VR window placement. Tap "Cancelar" /
  "Cancel" with `quest tap --text`, or force-stop the app that keeps asking
  (`adb shell am force-stop quest.side.vr`).

## Quest 3S notes (hardware verified)

- Panel: `wm size` reports `3664x1920`, so each eye is `1832x1920`.
- `quest-vr-record left` crops a level 16:9 `1832x1030` window from the left
  eye. The Quest 3S eye buffer is already level; pass `--angle` only if a
  capture is tilted.
- `quest screenshot --width 1024` returns a JPEG of the wearer's view from the
  Meta capture service, not a black Android surface.

## Verification

```sh
quest doctor
quest mount status
quest screenshot out/quest_hil/shot.jpg --width 1024   # open the image
quest elements | head
quest-vr-record start out/quest_hil/run.mkv left
sleep 5
quest-vr-record stop
```

Look at the image and the video. A black frame means the headset was asleep or
locked, not that the command failed.
