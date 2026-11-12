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
  `[xr_input.c](../../engine/platform/openxr/xr_input.c)` from a nested document.
  The second form is an example, not a link from this file.
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
- `Documentation/vr/` - canonical documentation: `STATUS.md`, `ROADMAP.md`,
  `GATES.md`, `TESTING.md`, `ASSETS.md`, `WEAPONS.md`, `UPSTREAM.md`,
  `DECISIONS.md`, `MODEL_BENCHMARKS.md`, `PLAN.md`, and `reference/`. Upstream
  documentation outside `Documentation/vr/` is read-only.

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

The single gate registry is [`Documentation/vr/GATES.md`](Documentation/vr/GATES.md).
Read it before running or reviewing a gate. The common local gates are:

```sh
./scripts/test_simulated_monado.sh      # M1: 49-assertion Monado suite (plus the T1 integrity gate)
./scripts/run_regression_battery.sh     # R1: 19-assertion regression battery
python3 scripts/check_docs.py           # D1: docs, links and path rules
python3 scripts/check_evidence_hygiene.py  # H1: evidence stays under out/qa
python3 scripts/progress_report.py      # current gate and task completion marker
python3 scripts/verify_grip_pose_math.py
python3 scripts/check_hand_asset.py --model assets/valve_vr/models/v_hand.mdl
python3 scripts/check_viewmodel_names.py          # overlay names vs HLSDK requests
python3 scripts/audit_viewmodel_assets.py \
    --decompiled-dir out/mmod_import/decompiled \
    --out out/qa/V1/asset_diagnostics
scripts/check_mdl_roundtrip.sh assets/valve_vr/models/v_crossbow.mdl
./scripts/test_manual_reload.sh          # Glock staged reload vertical slice
./scripts/test_quest_auto.sh 25 crossfire  # Q1 only when the maintainer requests it
```

- Evidence is written under `out/qa/<gate-id>/`. `out/qa/INDEX.md` lists the
  newest result per gate and `out/qa/<gate-id>/latest` points at the newest run.
  Do not cite the retired `out/evidence` root.
- Do not commit `out/`, `build/`, `android/app/.cxx/`, `graphify-out/`, or
  generated native libraries.
- `test_simulated_monado.sh` auto-detects `build-sim`, honors
  `MONADO_BUILD_DIR`, and defaults to a 120-second engine timeout.
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
- Shipped profiles carry no Euler compensation (`pitch_adjust` = 0 for all 16).
  The legacy Euler path remains only as a fallback for third-party mods
  without bore anchors; do not reintroduce per-weapon pitch tuning to hide a
  bad bore anchor.
- The crossbow `grip` bone is the front/foregrip. The main grip comes from the
  right-hand bone; keep both sockets distinct.
- The anchor uses the viewmodel grip bone aligned to the palm (grip pose);
  `grip_offset` is only a fallback for models without a grip bone/attachment.
- Do not change the authoritative firing line. `vuser2` is hand + aim
  calibration only.
- Screenshot and visual tests must stay valid when proximity pull-back or wall
  culling changes the on-screen weapon size.
- When changing pose math, prove the right-handed result is unchanged
  (`scripts/verify_grip_pose_math.py`) and report renderer/viewmodel deltas.

## 8. Assets and Licensing

- Licensing is not a blocker: this is a non-commercial community mod. Do not
  spend time verifying licenses. For every third-party asset, keep the download
  source URL and author credit in `assets/valve_vr/CREDITS.md`; the maintainer
  will confirm with each author before release. Do not ship a weapon or model
  that is 100% one modder's work without credit; assets derived from or lightly
  modified from Valve content only need a "based on" credit.
- The goal is a glove that works (follows the grip pose, closes naturally on the
  weapon grip, looks acceptable). Color and style do not matter; any glove
  asset may be used or replaced.
- The MMOD reanimation pack is bundled under `assets/valve_vr/models/`; keep its
  author credit, download source URL, archive checksum and per-weapon audit
  current in `CREDITS.md`. Blue Shift or Gearbox variants follow the same credit
  rules; add them to the audit when adopted.
- `v_hand.mdl` is the standalone two-hand model. Rebuild and validate it with
  the scripts in `scripts/` (for example `build_twohand_mdl.py`,
  `check_hand_asset.py`) instead of hand-editing binary assets.
- Holed viewmodels are repaired with a radial liner: duplicate the boundary
  loop, offset it inward along the normal, and bridge it. Do not cap intentional
  openings (barrel, magwell, ejection port), and do not move the outer
  silhouette. Preserve bones, UVs, weights, sequences, events, bodygroups and
  attachments.
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
- Quest validation is the maintainer's decision for each stage, not a global
  rule. Monado is the default local gate. Record a Quest gate as `pending`
  unless the maintainer asks for it, and never infer a Quest pass from Monado.

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
- Agents: `.opencode/agents/` (`@reviewer`, `@quest-tester`, `@gate-runner`).
  `@gate-runner` is read-only and must read `Documentation/vr/GATES.md` before
  running a gate.
- Commands: `.opencode/commands/` (`/build-quest`, `/deploy-quest`,
  `/quest-test`, `/monado-test`, `/regression`, `/grip-check`, `/progress`,
  `/review-weapon`).
- Skills: `.opencode/skills/quest` (generic Quest I/O) and
  `.opencode/skills/xash-vr-quest` (project HIL loop).
- MCP servers: `repowise` for symbol impact, `graphify` for the AST graph, and
  `blender` for the hand/asset pipeline.
- Prefer the project skills and commands over ad-hoc command sequences. Use the
  `reviewer` subagent for read-only review, `quest-tester` for HIL work, and
  `gate-runner` for a single gate from `GATES.md`.

## 12.2 Gate Workflow

- One implementer per stage; validators are read-only.
- Run only the command in the gate row. Do not add an ad-hoc proxy check and
  call it the gate.
- A gate result is `PASS`, `FAIL`, `INCONCLUSIVE` or `FINDING`. A `FINDING` is a
  diagnostic, not a pass. A visual or risky gate also needs a non-PENDING
  `human_decision` (`ADVANCE`, `REWORK` or `BLOCK`) from the maintainer.
- If the same stage fails twice, stop and report instead of thrashing.
- Do not mark a gate passed from an older run. Check the manifest commit.

## 13. Hard Rules From Experience

- Hands: never generate a detailed hand from primitives; the blocky unarmed
  presence hand is the explicit exception. Never reshape a glove by displacing
  vertices. Baked weapon hands are authoritative.
- Animation ownership: the hand assigned to an animation is authoritative; do
  not reshape or replace it per animation. A fallback VR hand copies the baked
  animation and inherits its texture, and baked animation is blended with 6DoF
  input instead of copying flat-screen root motion.
- Visual approval: do not deploy an asset without a labeled comparison sheet
  (fixed test camera) approved by the maintainer. Green gates (Monado suite,
  palm_dist) do not prove appearance.
- Reference point: the palm (grip pose), not the wrist bone and not the aim pose.
  The deprecated `vr_hand_offset_*` and `vr_weapon_anchor_{forward,right,up}`
  no-ops were removed; `vr_weapon_anchor_root` remains the active anchor switch.
  Do not reintroduce compensations.
- Bones: do not add bones to viewmodels; append attachments at the end of the table.
- `vr_hide_arms 2` filters only the viewmodel entity, not the standalone hands.
- Blender: start each script from an empty scene, use named collections (`hand`,
  `weapon`, `debug`), verify scale and position numerically after any import, and
  save new versions instead of overwriting. Loose SMD/OBJ imports are not valid
  for judging fit; use engine captures.
- Overlay trap: update both `out/valve/models` and `out/valve_vr/models`, and
  confirm in the log which file was loaded.

## 14. Session Economy

- Start from `Documentation/vr/STATUS.md` and `PLAN.md` for stages; do not re-read
  the whole repository.
  Use repowise and graphify queries instead.
- One stage per session; end with a short handoff (done, pending, files touched).
- Stop and report after the same stage fails twice.
- Prefer headless Blender scripts with numeric checks over interactive
  screenshot loops.
- Keep evidence in `out/qa`; do not revive `out/evidence` or add a second
  evidence root.
