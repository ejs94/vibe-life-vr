# Agent Instructions & Project Rules

Vibe-Life VR is a Half-Life VR project powered by Xash3D FWGS. The project
combines the native Xash3D FWGS engine, the `ref_gl_vr` OpenXR renderer, the
Half-Life SDK game code, and the Quest/PCVR packaging in this repository.

## 1. Universal Language Rules

- Code comments and docstrings MUST always be written in English.
- User-facing documentation may stay in Portuguese when the surrounding file is
  Portuguese. Match the language of the file you are editing.

## 2. Strictly Relative Paths Rule

- **NEVER use absolute paths** (for example `/home/...`, `C:\...`, or
  `file:///home/...`) in documentation, markdown files, code comments, scripts,
  command examples, or configuration files.
- **ALWAYS use relative paths** relative to the repository root or the document
  location.
- Markdown links must use relative syntax without `file://`, for example
  `[xr_input.c](engine/platform/openxr/xr_input.c)` from the repository root or
  `[xr_input.c](../../engine/platform/openxr/xr_input.c)` from nested docs.
- Terminal commands must use relative paths, for example
  `adb install -r out/xash3d-vr-quest.apk`.
- Device paths such as `/sdcard/xash` are remote Android paths, not host paths;
  they are allowed.

## 3. Working Directory

Run project commands from the repository root (`vibe-life-vr/`). If a session
starts at the workspace root, `cd vibe-life-vr` first or use it as the shell
working directory.

Prefix any shell command that mutates `$PATH` (for example an inline
`export PATH=...`) so it cannot leak into later commands. Prefer a subshell or
`env`.

## 4. Project Map

- `engine/platform/openxr/` - OpenXR instance, session, input, weapon profiles,
  swapchains, and eye buffers.
- `ref/gl_vr/` - dedicated VR renderer, studio model transforms, hands, weapon
  viewmodel, and debug gizmos.
- `engine/client/` and `engine/server/` - engine/game integration, prediction,
  and authoritative ballistics.
- `assets/valve_vr/` - VR overlay assets: `models/v_hand.mdl`,
  `models/vr_weapons.json`, and `CREDITS.md` (the single source for asset
  provenance, permissions and the MMOD audit).
- `android/` - Horizon OS launcher, Gradle packaging, and the standalone APK.
- `scripts/` - build, deploy, HIL, regression, and hand/asset pipelines.
- `Documentation/vr/` - architecture, roadmap, mod compatibility, upstream sync,
  and the engineering notebook.

## 5. Build

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

`build_quest_apk.sh` runs the Gradle `externalNativeBuild` step, so it rebuilds
the arm64-v8a native libraries before packaging. A stale APK is the most common
false negative in HIL work; rebuild after engine, renderer, or
`vr_weapons.json` changes before judging a headset capture.

## 6. Tests and Evidence

Run the relevant gates before claiming success:

```sh
./scripts/test_simulated_monado.sh      # Monado OpenXR unit suite
./scripts/run_regression_battery.sh     # 18-gate regression battery
python3 scripts/verify_grip_pose_math.py
python3 scripts/check_hand_asset.py
python3 scripts/calibrate_weapon_grips.py <engine.log>  # preview from a probe log
./scripts/test_quest_auto.sh 25 crossfire
```

- Evidence is written under `out/evidence/`. Do not commit `out/`, `build/`,
  `android/app/.cxx/`, `graphify-out/`, or generated native libraries.
- `test_simulated_monado.sh` auto-detects `build-sim` and honors
  `MONADO_BUILD_DIR`.
- `check_grip_seat.py` and `check_grip_pose.py` take an engine log containing
  `[VR_GRIP_BONE]` and `[VR_GRIP]` lines.
- A Quest pass requires a non-black `vr_eye0.png` (or `quest screenshot`), the
  OpenXR initialization lines, and no native crash. `screencap_os.png` is
  expected to be black in VR.

## 7. VR Pose Invariants

- `XR_GetWeaponPose()` is the single source of truth for the renderer, the
  viewmodel, and the muzzle fallback. Do not duplicate the pose math.
- `grip_offset` is a per-weapon model-space socket and is **not** mirrored for
  left-handed players. Only the global `vr_weapon_offset_right` is mirrored.
- `grip_rot` is optional. When absent, the legacy Euler
  `pitch_adjust`/`yaw_adjust`/`roll_adjust` path must remain numerically
  identical.
- The crossbow `grip` bone is the front/foregrip. The main grip comes from the
  right-hand bone; keep both sockets distinct.
- Do not change the authoritative firing line. `vuser2` is hand + aim
  calibration only.
- Screenshot and visual tests must stay valid when proximity pull-back or wall
  culling changes the on-screen weapon size.
- When changing pose math, prove the right-handed result is unchanged
  (`scripts/verify_grip_pose_math.py`) and report renderer/viewmodel deltas.

## 8. Assets and Licensing

- Bundle only assets whose license permits modification and redistribution.
- The glove is black by design; do not "fix" it to a skin tone.
- The MMOD reanimation pack is bundled under `assets/valve_vr/models/` with
  attribution and the author's permission. Keep its credits, source URL,
  archive checksum and per-weapon audit current in `CREDITS.md`; do not add
  the Blue Shift or Gearbox variants without a separate approval.
- `v_hand.mdl` is the standalone two-hand model. Rebuild and validate it with
  the scripts in `scripts/` (for example `build_twohand_mdl.py`,
  `check_hand_asset.py`) instead of hand-editing binary assets.
- Deploy the overlay models (`assets/valve_vr/models/*.mdl`, including
  `v_hand.mdl`) and `vr_weapons.json` to `/sdcard/xash/valve/models/` for HIL.
  The engine launches the base `valve` gamedir even though the APK also bundles
  `valve_vr`.

## 9. Quest HIL Facts

- Use the `xash-vr-quest` skill for the project loop and the `quest` skill for
  generic device I/O.
- `adb exec-out screencap` is black in VR. Use `quest screenshot` or the
  engine's `vr_eye0.png`.
- `adb input tap` is a no-op inside a native VR app. Use `quest elements` and
  `quest tap` for 2D panels, and `vr_test_*` cvars for the engine.
- A Quest 3S panel is `3664x1920`; each eye is `1832x1920`. The engine eye dump
  may be smaller because the swapchain resolution is lower.
- If the foreground activity is
  `com.oculus.os.vrusb/.WifiDebuggingAlertActivity`, dismiss it and force-stop
  `quest.side.vr`; it steals focus and breaks VR window placement.
- `quest mount on|off` needs `QUEST_MQST_PIN` on Android user 0. Always run
  `quest mount off` after off-head work.

## 10. Code Style

- Match the surrounding C99/Kotlin style; do not reformat unrelated code.
- Keep comments in English and focused on why, not what.
- Prefer small, testable helpers over growing the already-large input and
  renderer functions.
- Do not add a new cvar or weapon field without documenting it in
  `Documentation/vr/` and, when relevant, `assets/valve_vr/CREDITS.md`.
- `3rdparty/mainui` is a submodule. Commit its changes separately and update
  the parent pointer; do not mix submodule changes into an unrelated commit.

## 11. Commits

- Use the existing style: `area: subarea: lowercase description`, for example
  `engine: ref: openxr: add grip sockets and foregrip poses`.
- Keep commits logical. Do not commit generated artifacts, evidence, or local
  build caches.
- Report tests actually run and their result. Do not infer a pass from an
  earlier run after changing code.
- Separate facts from inference and cite `file:line` when reporting behavior.

## 12. OpenCode Workflow

- Configuration: `opencode.json` (MCP servers, references, permissions).
- Agents: `.opencode/agents/` (`@reviewer`, `@quest-tester`).
- Commands: `.opencode/commands/` (`/build-quest`, `/deploy-quest`,
  `/quest-test`, `/monado-test`, `/regression`, `/grip-check`).
- Skills: `.opencode/skills/quest` (generic Quest I/O) and
  `.opencode/skills/xash-vr-quest` (project HIL loop).
- MCP servers: `repowise` for symbol impact, `graphify` for the AST graph, and
  `blender` for the hand/asset pipeline. The clangd MCP server is not installed;
  do not add it until `../mcp-tools/clangd-mcp-server/dist/index.js` exists.
- Prefer the project skills and commands over ad-hoc command sequences. Use the
  `reviewer` subagent for read-only review and `quest-tester` for HIL work.
