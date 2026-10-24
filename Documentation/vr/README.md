# 🥽 Vibe-Life VR — Technical Architecture & Port Guide

> **A Half-Life VR project powered by Xash3D FWGS**  
> **Standard:** Canonical Khronos OpenXR 1.0 / 1.1 (Pure C99)  
> **Rendering:** Native Stereo `ref_gl_vr` (GLES 2.0/3.0 & Desktop OpenGL)  
> **Platforms:** Meta Quest Standalone (Quest 1/2/Pro/3/3S / Horizon OS) & Desktop PCVR (Linux Monado / WiVRn / SteamVR)

---

## 1. Vision & Purpose

**Xash3D VR** is the native OpenXR Virtual Reality port for the **Xash3D FWGS** engine, enabling full 6DoF roomscale play of classic **Half-Life (1998)**, expansions (*Opposing Force*, *Blue Shift*), and GoldSrc modifications.

The project is deeply inspired by the pioneering work of **Team Beef** (*Dr. Beef, BaggyG, Bummser*), whose *Lambda1VR* port proved the power of Half-Life on standalone VR headsets. While *Lambda1VR* targeted the original 2019 Oculus Quest using legacy *VrApi*, Xash3D VR is re-architected from the ground up around:
1. **The Khronos OpenXR Standard:** Pure C99 OpenXR implementation without vendor lock-in or proprietary wrappers.
2. **Upstream Xash3D FWGS Purity:** Keeps engine core changes minimal, ensuring seamless GoldSrc mod compatibility, clean code standards, and multiplayer crossplay between VR and Flat players.
3. **Unified Multi-Platform Codebase:** Single codebase running on Desktop PCVR and Android Standalone headsets.

---

## 2. Technical Architecture Overview

```
vibe-life-vr/
├── engine/platform/openxr/         ← Pure C99 OpenXR platform subsystem
│   ├── xr_core.c / .h              ← Lifecycle, instance, sessions, reference spaces, CVars
│   ├── xr_graphics.c               ← Multi-platform graphics bindings (Linux GLX & Android EGL)
│   ├── xr_swapchain.c / .h         ← Stereo swapchains, pacing, hardware VSync, frustum
│   └── xr_input.c / .h             ← Universal Action Sets, 6DoF tracking, gestures, haptics
├── ref/gl_vr/                      ← Dedicated stereo renderer library (libref_gl_vr.so)
│   ├── gl_rmain.c                  ← Dual viewpass loop, FBO attachment, laser sight
│   ├── gl_studio.c                 ← Decoupled 6DoF weapon viewmodels (aim-pose aligned)
│   ├── gl_frustum.c                ← Asymmetric lens frustum culling
│   └── gl_fbo.c                    ← Dedicated per-eye OpenXR swapchain FBO management
└── android/                        ← Meta Horizon OS modern widescreen launcher (Kotlin)
```

### 2.1 Complete Frame Pipeline

```mermaid
flowchart TD
    HF["Host_Frame(time)"] --> XRPOLL["XR_PollEvents()"]
    XRPOLL --> XRSYNC["XR_SyncInputs()"]
    XRSYNC --> SCR["SCR_UpdateScreen()"]
    
    SCR --> VPR["V_PreRender()"]
    VPR --> BF["ref.dllFuncs.R_BeginFrame() -> XR_BeginFrame()"]
    
    SCR --> VRV["V_RenderView()"]
    VRV --> GLBSF["ref.dllFuncs.GL_BackendStartFrame()"]
    
    VRV --> LOOP{"for eye = 0 to 1"}
    LOOP --> CALC["clgame.dllFuncs.pfnCalcRefdef(&rp)"]
    CALC --> GLRF["ref.dllFuncs.GL_RenderFrame(&rvp)"]
    
    GLRF --> PROJ["R_SetupProjectionMatrix() -> XR_GetEyeFrustum()"]
    GLRF --> MV["R_SetupModelviewMatrix() -> XR_GetHeadOrientation()"]
    GLRF --> SETUPGL["R_SetupGL() -> 6DoF Head Position Offset"]
    GLRF --> DRAW["R_DrawWorld() + R_DrawEntitiesOnList()"]
    GLRF --> LASER["R_DrawLaserSight() -> 3D Weapon Laser Beam"]
    
    VRV --> GLBEF["ref.dllFuncs.GL_BackendEndFrame()"]
    SCR --> VP["V_PostRender() -> HUD / UI Rendered to Offscreen Target"]
    VP --> EF["ref.dllFuncs.R_EndFrame() -> GL_BlendTargetQuad()"]
    EF --> SUBMIT["xrEndFrame() (Stereo Views + Floating Quad Layer)"]
```

---

## 3. Subsystem Breakdown

### 3.1 OpenXR Core (`engine/platform/openxr/xr_core.c`)
- **Graphics Extensions:** Negotiates `XR_KHR_opengl_enable` on desktop Linux and `XR_KHR_opengl_es_enable` on Android.
- **Reference Spaces:**
  - `XR_REFERENCE_SPACE_TYPE_STAGE`: Preferred roomscale tracking aligned with physical floor and Guardian bounds.
  - `XR_REFERENCE_SPACE_TYPE_LOCAL`: Seamless fallback for sitting/standing play without camera drift.
  - `XR_REFERENCE_SPACE_TYPE_VIEW`: Head-relative reference space used for floating HUD and menus (`z = -1.5m`).

### 3.2 Stereo Swapchains & Optics (`xr_swapchain.c` & `gl_frustum.c`)
- **Hardware Pacing:** Driven by `xrWaitFrame()`, locking framerate directly to physical panel refresh rates (72Hz, 90Hz, 120Hz).
- **Asymmetric Projection Frustum:** Queries per-eye FOV tangents from runtime (`xrLocateViews`) and calculates asymmetric frustum boundaries:
  $$\text{left} = \tan(\text{angleLeft}) \times \text{nearZ}$$
  $$\text{right} = \tan(\text{angleRight}) \times \text{nearZ}$$
  $$\text{bottom} = \tan(\text{angleDown}) \times \text{nearZ}$$
  $$\text{top} = \tan(\text{angleUp}) \times \text{nearZ}$$
- **GL4ES External Texture Bypass:** Uses `gl4es_registerExternalTexture()` and direct hardware `libGLESv2.so` calls to prevent virtualization dummy texture allocation on Qualcomm Adreno TBDR GPUs.

### 3.3 Universal Input & Controller Mechanics (`xr_input.c`)
- **Profiles:** Canonical bindings for Meta Quest Touch (Quest 1/2/Pro/3/3S) and Valve Index Knuckles.
- **Unified VR Controller Layout:**
  - **Right Controller:**
    - Button A: Jump (`+jump`).
    - Button B: Reload (`+reload`).
    - Analog Stick: Smooth turn (`vr_smoothturn 1`) or Snap turn (`vr_smoothturn 0`, step `vr_snap_angle 45°`). Click = Crouch (`+duck`).
    - Trigger: Primary Fire (`+attack`) / Menu pointer click (`K_MOUSE1`).
    - Grip + Trigger: Alt-fire (`+attack2`, MP5 grenade launcher, Shotgun double blast).
    - Grip alone: Weapon hold.
  - **Left Controller:**
    - Buttons X/Y: Unbound (reserved for inventory/holster).
    - Analog Stick: 2D Locomotion (walk/strafe). Direction decoupled via `vr_walkdirection` (`0` = HMD gaze, `1` = controller aim). Click = Sprint (`+speed`).
    - Trigger: Use / Interact when the off-hand is extended near a usable object.
    - Grip: Off-hand stabilizer grip (`grip > 0.55`); when not two-handing, picks up nearby items/weapons (`vr_offhand_grab 1`).
  - **Universal Menu Button:** Toggles in-game menu / floating Quad UI (`K_ESCAPE`).
  - **Flashlight:** head-tap gesture only (no dedicated button).
- **Weapon Mechanics, Ballistics & Decoupling:**
  - Weapon viewmodel locked to dominant controller aim pose (`XR_GetPrimaryHandTransform`).
  - Server-side bullet traces and rockets emerge from physical 3D muzzle (`pev->vuser1`).
  - Two-Handed Weapon Stabilizer (`vr_twohanded`): Holding offhand grip (`grip > 0.55`, release `< 0.35`) with forward gating (5cm to 60cm), separation (12cm to 65cm), and soft asymptotic clamp (`softDev`) provides 50% tighter bullet spread (`pev->vuser4.x`).
  - Physical Grenade & Snark Momentum: Throw velocity inherits 6DoF hand swing momentum (`pev->vuser3 * 1.25f`).
  - 6DoF Tripmines: Wall/floor mounting trace follows controller orientation (`pev->vuser2`).
  - Quick Weapon Switch: Flicking turn stick Up = `invprev`, Down = `invnext` (with debounce and haptic tick).
  - Physical Gestures:
    - Head-mounted flashlight toggle via temple touch gesture (`vr_headtorch 1`).
    - Over-the-shoulder crowbar draw (`slot1`).
    - Crossbow PiP scope (`vr_scope_mode 1`): the server-side zoom (alt-fire) activates a circular picture-in-picture lens with a reticle. Optional automatic proximity engage via `vr_proximity_scope` (off by default).
    - Touch-to-use (`vr_gesture_use 1`): extend the off-hand near an object and pull the off-hand trigger to activate `+use`.
    - Physical melee swing (`vr_melee_swing 1`): rapid crowbar swing attacks enemies; the flat-screen attack animation is suppressed (`vr_melee_suppress_attack_anim 1`).
    - Ladders: stick forward climbs, stick back descends and jump boosts over the top. A short attach probe handles thin ladder panels (`vr_debug_ladder 1` logs the VR/prediction state).
    - Pause menu: the controller menu button opens the 2D menu as a room-anchored quad that faces the player at any heading; closing it resumes the game. The pointer laser is drawn into the menu canvas from the hand to the cursor.
    - True-depth weapon rendering (`vr_weapon_true_depth 1`) and wall pull-back (`vr_weapon_pullback 1`).
- **Left-Handed Mode (`vr_lefthanded 1`):** Swaps the weapon hand, triggers, grips and locomotion/turn sticks. Jump/reload keep their commands but move from Right A/B to Left X/Y (Left A/B on Index). The lateral weapon grip offset is mirrored (`vr_lefthanded_mirror_grip 1`); the hand model already contains both anatomical chains, so no asset mirroring is needed.

---

## 4. Console Variables (CVars)

All VR CVars are archived (`FCVAR_ARCHIVE`) and registered early in `Host_Init()` via `XR_RegisterCVars()`:

| CVar | Default | Values | Description |
| :--- | :---: | :---: | :--- |
| **Locomotion & Comfort** | | | |
| `vr_smoothturn` | `1`* | `0`, `1` | `0` = discrete snap turning, `1` = smooth turning (*Launcher defaults to `0` for comfort) |
| `vr_snap_angle` | `45` | `15`–`90` | Angle step in degrees for snap turn mode |
| `vr_walkdirection` | `0` | `0`, `1` | `0` = movement oriented by HMD gaze, `1` = oriented by controller |
| `vr_physical_crouch` | `1` | `0`, `1` | Physical roomscale crouching (triggers `IN_DUCK` when squatting $\ge 28\text{cm}$) |
| `vr_height_adjust` | `0` | `-20`–`+20` | Standing height offset calibration in GoldSrc units |
| `vr_worldscale` | `40.0` | `20.0`–`60.0` | Engine units per real-world meter (default: 40.0) |
| **Weapons & Combat** | | | |
| `vr_lasersight` | `1` | `0`, `1` | Real-time 3D red laser beam projected from weapon barrel with impact marker |
| `vr_headtorch` | `1` | `0`, `1` | `1` = head-mounted flashlight with temple gesture (HL2:VR), `0` = off-hand flashlight |
| `vr_twohanded` | `0` | `0`, `1` | Enable two-handed weapon grip stabilization with soft clamp |
| `vr_lefthanded` | `0` | `0`, `1` | `1` = primary weapon in left hand; A/B (jump/reload) move to X/Y, sticks/triggers swap |
| `vr_lefthanded_mirror_grip` | `1` | `0`, `1` | Mirror the lateral weapon grip offset when left-handed |
| `vr_weapon_pitchadjust` | `0`* | `-30`–`+30` | Fine pitch adjustment angle for physical weapon alignment (*Launcher defaults to `10`) |
| `vr_manual_reload` | `0` | `0`, `1` | Staged Glock reload: B ejects the magazine, B inserts a fresh one, B racks the slide (server HLSDK) |
| `vr_proximity_scope` | `0` | `0`, `1` | Optional automatic scope engage when the crossbow is brought close to the eye |
| `vr_scope_mode` | `1` | `0`, `1` | `1` = picture-in-picture crossbow scope; `0` = off |
| `vr_scope_zoom` | `4.0` | `2.0`–`8.0` | PiP magnification factor (source region = eye size / zoom) |
| `vr_scope_radius` | `0.42` | `0.25`–`0.48` | Scope lens radius as a fraction of the shorter eye dimension |
| `vr_scope_reticle` | `1` | `0`, `1` | Draw the lens ring and red reticle |
| `vr_debug_ladder` | `0` | `0`, `1` | Log ladder client-prediction VR state and movement command |
| `vr_melee_swing` | `1` | `0`, `1` | Physical arm swing motion to trigger Crowbar melee attacks |
| `vr_melee_suppress_attack_anim` | `1` | `0`, `1` | Freeze the flat-screen Crowbar attack swing and rely on the physical VR swing |
| `vr_offhand_grab` | `1` | `0`, `1` | Pick up items/weapons with the off-hand grip when not two-handing |
| `vr_debug_grab` | `0` | `0`, `1` | Log off-hand grab requests and server pick results |
| `vr_weapon_true_depth` | `1` | `0`, `1` | Draw the viewmodel and hands with real depth so world geometry occludes them |
| `vr_weapon_pullback` | `1` | `0`, `1` | Pull the weapon toward the player when it would intersect a wall |
| `vr_weapon_offset_forward`| `-10.0` | float | Weapon grip forward offset in GoldSrc units |
| `vr_calibration_stick` | `0` | `0`, `1` | Real-time 6DoF weapon offset & angle calibration via thumbstick (Team Beef: L/R=axis, U/D=adjust) |
| **Immersion, Audio & Presence** | | | |
| `vr_hide_arms` | `2` | `0`, `1`, `2` | `2` = strip the viewmodel glove and draw the standalone hand, `1` = keep the vanilla 3D glove, `0` = original mesh |
| `vr_audio_hrtf` | `1` | `0`, `1` | 3D binaural HRTF spatial audio with pinna shadowing and 6DoF listener tracking |
| `vr_haptics_enabled` | `1` | `0`, `1` | OpenXR haptic vibration feedback on weapon fire, damage, and UI |
| `vr_haptics_intensity` | `1.0` | `0.0`–`2.0` | Global haptic vibration amplitude multiplier |
| `vr_finger_curling` | `1` | `0`, `1` | Procedural finger curling driven by controller analog trigger/grip axes |
| `vr_finger_curl_scale` | `1.0` | `0.1`–`2.0` | Multiplier for procedural finger curling angle |
| `vr_gesture_use` | `1` | `0`, `1` | Touch-to-use: extend the off-hand near an object and pull its trigger to activate `+use` |
| `vr_offhand_render` | `1` | `0`, `1` | Render secondary 6DoF off-hand presence when not holding two-handed weapon |
| **Spatial UI & Debug** | | | |
| `vr_pointer_hud` | `1` | `0`, `1` | Beat Saber-style 3D dual alternating laser pointers for menus and UI |
| `vr_menu_distance` | `1.15` | `0.8`–`2.5` | Distance in meters of floating 2D menu quad canvas in head space (calibrated for Quest 3) |
| `vr_menu_scale` | `1.15` | `0.8`–`2.5` | Width in meters of floating 2D menu quad canvas |
| `vr_debug_impacts` | `1` | `0`, `1` | 3D visual markers (crosshairs, tracers, normals) at bullet impact points |
| `vr_debug_hand` | `0` | `0`, `1`, `2` | 6DoF tracking debug: `0`=off, `1`=3D Hand gyro rings + Weapon COM lever vectors + HUD telemetry, `2`=+3D wireframe hitboxes |

### 4.1 Console Commands

| Command | Description |
| :--- | :--- |
| `vr_telemetry` | Dumps instantaneous 6DoF spatial telemetry (Head, Hands, Weapon Center of Mass, Hitbox count) to console |
| `vr_recenter` | Recalibrates head yaw/origin to current headset position and realigns floating menu quad anchor |
| `vr_reload_weapon_profiles` | Hot-reloads declarative weapon calibration manifests (`vr_weapons.json`) without restarting |
| `vr_dumpeye [filename.ppm]` | Extracts instantaneous raw stereo framebuffer from GPU memory and dumps to disk |
| `vr_record_impact` | Registers a 3D visual debug impact marker at current trace target |
| `vr_clear_impacts` | Clears all active 3D debug impact visual markers |

---

## 5. Build & Testing Workflows

### 5.1 Desktop PCVR (Linux Monado / WiVRn / SteamVR)
```bash
# Configure and build
./waf configure --enable-openxr --enable-gl-vr
./waf build
./waf install --destdir=./out

# Run automated Monado comprehensive unit test suite (38 assertion gates, ~55s)
./scripts/test_simulated_monado.sh

# Or run custom map simulation in Monado
./scripts/test_simulated_monado.sh crossfire

# Run directly on PCVR headset
cd out && ./xash3d -dev 1 -ref gl_vr +map c1a0
```

### 5.2 Meta Quest Standalone (Android arm64)
```bash
# Build standalone APK
./scripts/build_quest_apk.sh

# Install on connected Quest
adb install -r out/xash3d-vr-quest.apk

# Check headset battery and thermals
./scripts/quest_battery.sh

# Run automated test with pixel dump validation
./scripts/test_quest_auto.sh 25 crossfire
```

### 5.3 Ferramentas MCP & Inteligência de Código (`mcp-tools`)

O fluxo de engenharia do port VR integra ferramentas do Model Context Protocol (MCP) localizadas em `../mcp-tools` para governança, auditoria de código e análise de impacto prévia a refatorações:

- **Repowise:** Análise de call graph, blast radius e rastreamento de símbolos C/C++ sem requisições LLM. Usado para prever quebras ao modificar estruturas de movimentação (`sv_pmove.c`), renderizador (`gl_rmain.c`) ou platform layers (`xr_swapchain.c`).
- **Graphify:** Mapeamento em grafo de conhecimento (AST + semântico), agrupamento em comunidades e visualização interativa do ecossistema engine/OpenXR (`graphify-out/graph.html`).
- **Desloppify:** Scanner rigoroso de código morto, acoplamento e dívida técnica C/C++ vinculado a `build/compile_commands.json`.

```bash
# Verificar status das ferramentas MCP e artefatos de grafo
./scripts/mcp_tools.sh status

# Gerar/atualizar grafo de conhecimento AST do repositório
./scripts/mcp_tools.sh graph

# Analisar código morto e símbolos inacessíveis (Repowise)
./scripts/mcp_tools.sh dead-code

# Executar scanner de higiene e dívida técnica C/C++ (Desloppify)
./scripts/mcp_tools.sh health
```

---

### 5.4 Hand asset & controller reference

```bash
# Rebuild the dark inner glove liner (requires out/twohand and pxstudiomdl)
python3 scripts/add_hand_inner_liner.py \
    --input out/twohand --output out/twohand_liner --compile \
    --pxstudiomdl out/pxstudiomdl/pxstudiomdl

# Blender reference scene with the hand and a Quest-style controller proxy
blender --background --python scripts/blender_controller_reference.py -- \
    out/twohand_liner/hand_r.smd out/controller_reference
```

The controller in that scene is a **shape proxy**, not a licensed Quest model.
Replace the proxy objects with a real controller mesh while keeping the grip
origin at `(0,0,0)` to calibrate the hand/weapon visually. Asset credits,
permissions and the MMOD per-weapon audit live in
`assets/valve_vr/CREDITS.md`.

## 6. Documentação Relacionada

- [Caderno de Engenharia & Anotações de Soluções](ENGINEERING_NOTEBOOK.md) — Soluções próprias vs adaptadas, decisões arquiteturais, telemetria headless, integração OpenXR-CTS e governança MCP.
- [Roadmap & Análise de Problemas](ROADMAP.md) — Fases 01 a 08, port tracker e histórico de depuração.
- [Arquitetura de Compatibilidade de Mods & Mod Manager](MOD_COMPATIBILITY_ARCHITECTURE.md) — Sistema de 3 Tiers (Gold, Silver, Bronze), especificações de manifest (`vr_mods.json`), Mod Manager para Quest/PCVR, e protocolos de limpeza de armazenamento.
- [Estratégia de Sincronização Upstream](UPSTREAM_SYNC_STRATEGY.md) — Política de Selective Cherry-Pick com Janela de Maturação (60-90 dias) e testes em sandbox Monado VR.


