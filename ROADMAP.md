# 🗺️ Xash3D VR: Official Project Roadmap & Tracking

> **Current Status:** 🟡 **Phase 03 Active — Universal Action Sets, Controller Poses & Locomotion**  
> **API Standard:** Pure Khronos OpenXR 1.0/1.1 (C99)  
> **Target Platforms:**  
> - **Desktop PCVR:** Linux (x86_64 / aarch64) via Monado, WiVRn, SteamVR, and ALVR  
> - **Standalone Mobile VR:** Meta Quest Standalone (Quest 1, 2, Pro, 3, 3S) & Pico via Android (arm64-v8a)  
> - **Android Flat (2D) Mobile:** Android Studio Emulator (`Medium_Phone_API_37.0`, x86_64 & arm64-v8a)  
> **Quality Gate Policy:** 🛡️ **Mandatory Tri-Platform Verification** — Every stage MUST provide explicit compilation and functional test validation on Desktop PCVR, Quest Standalone, and Android Flat Emulator before being marked complete.

---

## 📊 Milestone Overview & Status Matrix

| Phase | Milestone / Epic | Status | Key Deliverables | PCVR Verification | Quest Standalone | Android Flat Emulator |
| :---: | :--- | :---: | :--- | :--- | :--- | :--- |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **01** | **OpenXR Runtime Foundation & Dual-Platform Bring-Up** | 🟢 **Completed** | Unified build system (Waf + Gradle), OpenXR loader init (`xrInitializeLoaderKHR` on Android), instance/system discovery, graphics bindings (GLX / EGL), session lifecycle, swapchains, and canonical frame loop (`xrWaitFrame` -> `xrEndFrame`). | `./waf build` + `./scripts/run_wivrn.sh`; verify OpenXR session starts and submits clear stereo frames. | `./scripts/build_quest_apk.sh` + ADB install; verify OpenXR Android loader inits and renders to headset via logcat. | `./scripts/test_emulator_flat.sh menu`; verified flat 2D menu. |
| **02** | **Stereo Rendering, Asymmetric Frustum & 6DoF Head Tracking** | 🟢 **Completed** | Native `ref_gl_vr` stereo presentation, asymmetric optical frustum calculation (`XR_GetEyeFrustum`), 6DoF head pose translation and rotation injected into `cl_view.c` and `R_SetupGL`. | Smooth 6DoF head movement in maps (`crossfire`, `c1a0`) on Monado/WiVRn; desktop companion mirror (`pcvr_eye0_phase02.png`). | Native 72/90 FPS stereo rendering on Quest Standalone; zero jitter in 6DoF tracking space; verified via automated test gate. | Clean 2D mobile rendering without regressions on Android emulator (`emulator_flat_phase02.png`). |
| **03** | **Universal Action Sets, Controller Poses & Locomotion** | 🟡 **Active** | Khronos action sets (`xrCreateActionSet`), interaction profiles for Meta Quest Touch & Valve Index, 6DoF hand spaces, smooth/snap turning, thumbstick locomotion in `usercmd_t`, radial deadzones (`0.15`). | Locomotion, turning, jumping, crouching, and interaction verified using controllers on PCVR. | Identical locomotion and button interactions verified with Touch controllers on Quest Standalone. | Fallback touch/gamepad input preserved on Android Flat Emulator. |
| **04** | **6DoF Weapon Decoupling & Off-Hand Flashlight** | ⚪ Planned | Weapon viewmodel detached from camera gaze onto dominant hand pose in `gl_studio.c`; independent off-hand flashlight in `cl_tent.c`; two-handed stabilization (< 22cm); Reach-to-Use gesture. | Weapon points wherever hand points independently of gaze on PCVR; off-hand flashlight aims separately. | Full weapon decoupling and independent flashlight verified on Quest Standalone. |
| **05** | **In-Headset Spatial UI, Laser Pointer & VR Options Menu** | ⚪ Planned | Floating 3D quad layer (`XrCompositionLayerQuad`) for HUD and menus; 3D laser pointer virtual mouse cursor; FWGS `mainui_cpp` integration with dedicated `CMenuVR` options screen. | Main menu and HUD visible in 3D space; settings configured via laser pointer on PCVR. | UI floating canvas, laser pointer clicks, and VR settings adjustments verified on Quest Standalone. |
| **06** | **Server-Side Ballistics, Momentum Physics & Haptics** | ⚪ Planned | `hlsdk-portable` server-side muzzle raycasting (`pev->vuser1`), projectile trajectory aligned with barrel, grenade throwing momentum (`pev->vuser3`), OpenXR action haptic impulses. | Bullets and rockets emerge from physical weapon barrel on PCVR; haptic recoil pulses felt on controllers. | Identical physical ballistics, throwing velocity, and haptic feedback verified on Quest Standalone. |
| **07** | **Immersive Presence, 3D Spatial Audio & World Mechanics** | ⚪ Planned | Articulated HEV suit virtual hands, OpenAL Soft HRTF 3D binaural spatial audio, room-scale physical crouching via HMD delta, interactive ladder climbing. | Directional 3D audio cues and physical crouching under obstacles tested on PCVR. | Spatial audio and room-scale collision tested on Quest Standalone. |
| **08** | **Official Expansions & Total Conversions Support** | ⚪ Planned | Native VR weapon rigs and entity handling for *Half-Life: Opposing Force*, *Half-Life: Blue Shift*, and classic GoldSrc total conversions (*They Hunger*, *Cry of Fear*). | Expansions load cleanly and execute with full VR controls on PCVR. | Expansions packaged and functional on Quest Standalone. |

---

## 🎯 Detailed Phase Breakdown

### 🟢 Phase 01: OpenXR Runtime Foundation & Dual-Platform Bring-Up (COMPLETED & VERIFIED)

The primary goal of Phase 01 was to establish a rock-solid, verifiable OpenXR baseline that boots, initializes sessions, and renders valid stereo frames on both target platforms before any gameplay or weapon code is integrated. Both target platforms (Meta Quest Standalone at native 90 FPS and Linux PCVR via WiVRn) have passed empirical verification.

#### Sub-Stages & Deliverables:
- **Stage 1.1: Dual-Platform Build & Packaging Pipeline**
  - PCVR: Waf build system configured with `--enable-openxr` and `--enable-gl-vr`, dynamically linking canonical Khronos OpenXR loader (`-lopenxr_loader`).
  - Android: Gradle NDK toolchain compiling native engine for `arm64-v8a`, packaging valid APK (`su.xash.engine`) with OpenXR intent categories and Meta Quest Standalone manifest metadata.
  - Test PCVR: Clean `./waf build` + `./waf install --destdir=./out` produces executable `out/xash3d` and libraries `libxash.so`, `libref_gl_vr.so`.
  - Test Android: Clean `./gradlew assembleDebug` produces valid APK; `./scripts/build_quest_apk.sh` completes successfully.

- **Stage 1.2: OpenXR Platform Loader & Instance Initialization**
  - Android Loader Bootstrap: Call `xrInitializeLoaderKHR` with `XrLoaderInitInfoAndroidKHR` (passing `JavaVM` and application context) prior to any OpenXR calls.
  - Instance Negotiation: Query available instance extensions; enable `XR_KHR_opengl_enable` on desktop Linux and `XR_KHR_opengl_es_enable` on Android.
  - System Discovery: Query HMD system ID via `xrGetSystem` (`XR_FORM_FACTOR_HEAD_MOUNTED_DISPLAY`).
  - Test PCVR: Execute `./scripts/run_wivrn.sh`; verify log output confirms `xrCreateInstance` and `xrGetSystem` succeed with valid HMD system ID.
  - Test Android: Install APK via ADB, launch activity, inspect `adb logcat`; verify OpenXR Android loader initializes and detects Quest HMD without crashing.

- **Stage 1.3: Graphics Context Extraction & OpenXR Graphics Binding**
  - Linux X11/GLX: Intercept window and context from SDL2/SDL3; populate `XrGraphicsBindingOpenGLXlibKHR` (`xDisplay`, `glxContext`, `glxDrawable`). Query `xrGetOpenGLGraphicsRequirementsKHR`.
  - Android EGL: Intercept active EGL display, context, and surface from SDL/Android; populate `XrGraphicsBindingOpenGLESAndroidKHR`. Query `xrGetOpenGLESGraphicsRequirementsKHR`.
  - Test PCVR: Graphics binding accepted by active runtime (WiVRn / Monado / SteamVR) without OpenGL error codes.
  - Test Android: Graphics binding accepted by Meta Quest runtime without EGL configuration mismatch.

- **Stage 1.4: Session Lifecycle State Machine**
  - Create session via `xrCreateSession`.
  - Implement full event loop via `xrPollEvent` handling `XR_TYPE_EVENT_DATA_SESSION_STATE_CHANGED`:
    - `XR_SESSION_STATE_READY` -> Invoke `xrBeginSession` (`XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO`).
    - `XR_SESSION_STATE_STOPPING` -> Conclude session via `xrEndSession`.
    - `XR_SESSION_STATE_LOSS_PENDING` / `EXITING` -> Clean teardown of spaces and instances.
  - Create reference space `XR_REFERENCE_SPACE_TYPE_LOCAL` with identity orientation.
  - Test PCVR: Session transitions cleanly through `READY` to active rendering state; exits gracefully on engine quit.
  - Test Android: Session transitions cleanly on Quest; app survives headset sleep/wake and return to home menu.

- **Stage 1.5: Hardware-Paced Swapchains & Headset Frame Submission**
  - Enumerate stereo eye views via `xrEnumerateViewConfigurationViews` matching HMD panel resolution.
  - Create color swapchains (`xrCreateSwapchain`) and extract texture handles (`xrEnumerateSwapchainImages`).
  - Execute canonical hardware frame loop: `xrWaitFrame` -> `xrBeginFrame` -> `xrAcquireSwapchainImage` -> `xrReleaseSwapchainImage` -> `xrEndFrame`.
  - Submit solid clear color or test pattern into eye swapchains and present to compositor.
  - Test PCVR: Headset displays clear stereo frames paced at native refresh rate (72Hz/90Hz/120Hz); companion window mirrors view.
  - Test Android: Quest headset displays clear stereo frames without black screen, stutter, or watchdog crash.

---

### 🟢 Phase 02: Stereo Rendering, Asymmetric Frustum & 6DoF Head Tracking (COMPLETED & VERIFIED)

- [x] Connect `ref_gl_vr` stereo rendering pass to OpenXR eye swapchain framebuffers.
- [x] Query per-eye asymmetric optical field-of-view tangents via `xrLocateViews`.
- [x] Calculate asymmetric lens Frustum (`XR_GetEyeFrustum`) and inject into `R_SetupProjectionMatrix`.
- [x] Convert OpenXR Quaternions into GoldSrc Euler angles (Pitch, Yaw, Roll) in `cl_view.c`.
- [x] Inject 3D physical head translation into `worldviewMatrix` in `R_SetupGL`.
- [x] **PCVR Verification Test:** Launched map `crossfire` and `c1a0`. Verified true 6DoF head movement tracking in headset, correct stereo depth without eye strain, and desktop companion mirror (`pcvr_eye0_phase02.png`).
- [x] **Android Standalone Verification Test:** Launched map on Meta Quest 3S. Verified smooth 6DoF head tracking with low latency, correct per-eye optical perspective, and rock-solid 72/90 FPS native framerate (`test_quest_auto.sh`).
- [x] **Android Flat Emulator Verification Test:** Verified clean 2D engine execution, touch HUD, and menu rendering on Android Studio emulator (`emulator_flat_phase02.png`).

---

### 🟡 Phase 03: Universal Action Sets, Controller Poses & Locomotion (ACTIVE)

- [ ] Create Khronos gameplay action set (`xrCreateActionSet`).
- [ ] Implement interaction profiles for Meta Quest Touch (Quest 1/2/Pro/3/3S) and Valve Index.
- [ ] Map analog thumbsticks to forward/side movement and smooth/snap rotation in `usercmd_t`.
- [ ] Implement radial thumbstick deadzone (`0.15`) for hardware drift compensation.
- [ ] Allocate 6DoF hand spaces for left and right motion controllers (`xrCreateActionSpace`).
- [ ] Map core actions: `IN_ATTACK`, `IN_ATTACK2`, `IN_JUMP`, `IN_DUCK`, `IN_USE`, `IN_RELOAD`.
- [ ] **PCVR Verification Test:** Move and look around in multiplayer map using motion controllers; test snap turning and button actions.
- [ ] **Android Standalone Verification Test:** Verify full locomotion, turning, and interaction on Meta Quest Touch controllers.

---

### ⚪ Phase 04: 6DoF Weapon Decoupling & Off-Hand Flashlight

- [ ] Decouple weapon viewmodels from gaze in `gl_studio.c`, attaching transform to dominant controller aim pose.
- [ ] Independent physical flashlight cast from non-dominant hand in `cl_tent.c`.
- [ ] Two-handed weapon stabilizer activated when hands are in close proximity (< 22cm).
- [ ] Natural Reach-to-Use gesture (`+use`) when hands approach interactive world entities.
- [ ] Over-the-shoulder Crowbar draw gesture (`slot1`).
- [ ] **PCVR Verification Test:** Aim weapons freely in any direction while looking away; illuminate dark areas with independent offhand flashlight.
- [ ] **Android Standalone Verification Test:** Test 6DoF weapon aiming and offhand flashlight on Quest Standalone.

---

### ⚪ Phase 05: In-Headset Spatial UI, Laser Pointer & VR Options Menu

- [ ] Floating 3D quad layer (`XrCompositionLayerQuad`) for HUD, menus, and console at 1.5m distance.
- [ ] 3D laser pointer beam projected from dominant controller onto menu quad canvas.
- [ ] Transform 3D raycast intersection into normalized 2D virtual mouse events (`UI_MouseMove`, `K_MOUSE1`).
- [ ] Integrate FWGS `mainui_cpp` source tree into `libmenu.so`.
- [ ] Build dedicated in-headset "VR Options" graphical menu (`menus/VR.cpp` / `CMenuVR`) with comfort toggles, snap angles, world scale, and height calibration.
- [ ] High-DPI FreeType vector fonts for crisp in-headset legibility.
- [ ] **PCVR Verification Test:** Navigate menus, adjust comfort options, and start games entirely in-headset via laser pointer without keyboard/mouse.
- [ ] **Android Standalone Verification Test:** Verify standalone in-headset UI interaction and setting persistence on Quest.

---

### ⚪ Phase 06: Server-Side Ballistics, Momentum Physics & Haptics

- [ ] Connect OpenXR controller aim pose into `hlsdk-portable` server-side trace routines (`FireBullets`, `TraceAttack`).
- [ ] Physically spawn bullets, Tau beams, and RPG rockets from weapon muzzle origin (`pev->vuser1`).
- [ ] Calculate grenade and satchel throwing velocity from physical hand momentum (`pev->vuser3`).
- [ ] Multi-channel OpenXR action haptic impulses (`XR_ApplyHapticFeedback`) for weapon recoil, HEV stations, and damage shocks.
- [ ] **PCVR Verification Test:** Verify bullets hit exactly where weapon barrel points; feel distinctive haptic recoil pulses.
- [ ] **Android Standalone Verification Test:** Verify muzzle ballistics, grenade throwing, and controller vibration on Quest.

---

### ⚪ Phase 07: Immersive Presence, 3D Spatial Audio & World Mechanics

- [ ] Articulated 3D HEV hazard suit hand models attached to controller 6DoF transforms with finger curling.
- [ ] OpenAL Soft HRTF 3D binaural spatial audio for spherical sound localization.
- [ ] Room-scale physical crouching via HMD height delta (`vr_height_adjust`).
- [ ] Physical ladder climbing and hand-directed swimming.
- [ ] **PCVR Verification Test:** Test 3D audio localization in vents and physical crouching under tripmines on PCVR.
- [ ] **Android Standalone Verification Test:** Test HRTF audio and physical mechanics on Quest Standalone.

---

### ⚪ Phase 08: Official Expansions & Total Conversions Support

- [ ] Native VR weapon rigs and entity handling for *Half-Life: Opposing Force*.
- [ ] Native VR support for *Half-Life: Blue Shift*.
- [ ] Mod compatibility testing for classic GoldSrc total conversions (*They Hunger*, *Cry of Fear*).
- [ ] **PCVR Verification Test:** Play through introductory chapters of Opposing Force and Blue Shift in VR.
- [ ] **Android Standalone Verification Test:** Verify standalone expansion pack packaging and execution on Quest.

---

## 🛠️ How to Build, Test & Validate

### 🐧 Desktop PCVR (Linux Monado / SteamVR / WiVRn)
```bash
# 1. Configure engine with OpenXR and VR stereo renderer
./waf configure --build-type=release --enable-openxr --enable-gl-vr

# 2. Build using all available CPU cores
./waf build -j$(nproc)

# 3. Install into local execution directory
./waf install --destdir=./out

# 4. Launch with WiVRn / Monado launcher
./scripts/run_wivrn.sh crossfire
```

### 🥽 Meta Quest Standalone (Android APK)
```bash
# 1. Set environment variables (using system Android SDK and Studio JBR)
export ANDROID_HOME=$HOME/Android/Sdk
export JAVA_HOME=/opt/android-studio/jbr
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH

# 2. Run automated packaging script
./scripts/build_quest_apk.sh

# 3. Install onto connected Meta Quest headset via ADB
adb install -r out/xash3d-vr-quest.apk

# 4. Launch and capture diagnostic logs
adb shell am start -n su.xash.engine/.MainActivity
adb logcat -s OpenXR XashVR DEBUG AndroidRuntime:E
```
