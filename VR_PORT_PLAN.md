# 🗺️ Xash3D VR Port — Master Development Plan & Task Tracker

> **Official Technical Planning & Execution Document**  
> **Status:** 🟡 **Phase 01 Active — OpenXR Runtime Foundation & Dual-Platform Bring-Up**  
> **API Standard:** Pure Khronos OpenXR 1.0/1.1 (C99)  
> **Target Platforms:**  
> - **Desktop PCVR:** Linux (x86_64 / aarch64) via Monado, WiVRn, SteamVR, and ALVR  
> - **Standalone Mobile VR:** Meta Quest Standalone (Quest 1, 2, Pro, 3, 3S) & Pico via Android (arm64-v8a)  
> **Mandatory Quality Policy:** 🛡️ **Dual-Platform Verification Gate** — Each phase and stage requires empirical compilation and functional test validation on BOTH PCVR (Linux) and Standalone (Android Quest) before progression.

---

## 📌 1. Repository & Fork Overview

* **Repository:** `xash3d-fwgs-vr`
* **Branch:** `feature/openxr-vr`
* **Engine Base:** Modern Xash3D FWGS (v0.21)
* **Design Philosophy:** Clean C99 modular OpenXR runtime, decoupled from proprietary vendor wrappers (zero VrApi legacy, zero JNI in engine core), 100% compatible with the official Flying With Gauss (FWGS) ecosystem.

### Centralized Repository Documentation Tree

```
xash3d-fwgs-vr/
├── engine/platform/openxr/         ← Native Khronos OpenXR 1.0/1.1 Subsystem (C99)
│   ├── xr_core.c / .h              ← Lifecycle, instance, session, reference spaces, unified cvars
│   ├── xr_graphics.c               ← Multi-platform graphics bindings (Linux X11/GLX & Android EGL)
│   ├── xr_swapchain.c / .h         ← Stereo swapchains, frame loop, hardware pacing, optical frustum
│   └── xr_input.c / .h             ← Interaction profiles (Quest Touch/Index), 6DoF tracking, gestures
├── ref/gl_vr/                      ← Native Stereo Virtual Reality Renderer
│   ├── gl_rmain.c                  ← Stereo pass, asymmetric eye frustum, 3D laser sight
│   └── gl_studio.c                 ← 6DoF weapon viewmodel decoupling onto controller aim pose
├── 3rdparty/mainui/                ← Official FWGS MainUI C++ Implementation
│   ├── menus/VR.cpp                ← Dedicated in-headset VR Options configuration menu (CMenuVR)
│   ├── menus/Configuration.cpp     ← Entry point hook ("VR Options" button)
│   └── BaseMenu.h                  ← UI_VR_Menu export and interface
├── android/                        ← Meta Quest Standalone Android Project
│   ├── app/src/main/AndroidManifest.xml ← Quest Standalone VR metadata, 6DoF intent categories
│   └── build.gradle.kts            ← NDK arm64-v8a toolchain
├── scripts/
│   ├── build_quest_apk.sh          ← Automated Meta Quest Standalone packaging script
│   ├── build_flat_apk.sh           ← Dedicated non-VR Android Flat packaging script
│   └── run_wivrn.sh                ← One-click Linux PCVR launcher (WiVRn / Monado)
├── README.md                       ← Project overview and central documentation index
├── ROADMAP.md                      ← High-level release and stage roadmap (Phases 01–08)
├── WHY_THIS_PROJECT_EXISTS.md      ← Architectural manifesto & Lambda1VR comparison
├── VR_PORT_PLAN.md                 ← This master development plan & task tracker
├── VR_TECHNICAL_ARCHITECTURE.md    ← Deep-dive engineering & hardware pipeline reference
└── AGENTS.md                       ← AI agent and developer contribution guidelines
```

---

## 🚀 2. Phased Development Roadmap & Dual-Platform Verification

### 🟢 Phase 01: OpenXR Runtime Foundation & Dual-Platform Bring-Up (COMPLETED & VERIFIED)
* **Goal:** Establish a verified OpenXR baseline that boots, handles session states, and presents stereo swapchains on both Linux PCVR and Meta Quest Standalone.
* **Status:** 🟢 **Completed & Verified** (Dual-Platform Gate Passed)
* **Key Deliverables:**
  - Clean build foundation with opt-in build flags (`--enable-openxr`, `--enable-gl-vr`).
  - Android OpenXR loader bootstrap via `xrInitializeLoaderKHR` (`XrLoaderInitInfoAndroidKHR`).
  - Instance creation (`xrCreateInstance`) with `XR_KHR_opengl_enable` (Linux) and `XR_KHR_opengl_es_enable` (Android).
  - Graphics context binding: `XrGraphicsBindingOpenGLXlibKHR` (Linux X11/GLX) and `XrGraphicsBindingOpenGLESAndroidKHR` (Android EGL).
  - Session lifecycle management (`xrCreateSession`, `xrBeginSession`, `xrEndSession`, `XR_REFERENCE_SPACE_TYPE_LOCAL`).
  - Frame loop & stereo swapchains: `xrWaitFrame` -> `xrBeginFrame` -> `xrAcquireSwapchainImage` -> `xrReleaseSwapchainImage` -> `xrEndFrame`.
* **PCVR Verification Test:**
  - Build via `./waf configure --enable-openxr --enable-gl-vr && ./waf build && ./waf install --destdir=./out`.
  - Launch with WiVRn/Monado via `./scripts/run_wivrn.sh` or automated test `./scripts/test_pcvr_wivrn.sh`.
  - Pass Criteria: Headset detects session, enters `FOCUSED` state, and presents stereo frames without crashing; desktop mirror window functions. **(PASSED - 2198x2302 stereo swapchains rendered)**
* **Android Standalone Verification Test:**
  - Package APK via `./scripts/build_quest_apk.sh` (using `JAVA_HOME=/opt/android-studio/jbr`).
  - Install and run via ADB on Meta Quest: `adb install -r out/xash3d-vr-quest.apk && adb shell am start -n su.xash.engine/.MainActivity`.
  - Pass Criteria: OpenXR Android loader initializes without `XR_ERROR_INITIALIZATION_FAILED`, session starts, and stereo frames render to Quest panels. **(PASSED - Native 90 FPS / 90 Hz verified via VrApi)**

---

### 🟡 Phase 02: Stereo Rendering, Asymmetric Frustum & 6DoF Head Tracking
* **Goal:** Deliver stereoscopic perspective and optical lens correction for both eyes.
* **Status:** 🟡 **Active** (Unblocked by Phase 01 Verification)
* **Key Deliverables:**
  - Connect `ref_gl_vr` stereo render pass to OpenXR eye swapchain framebuffers.
  - Query FOV tangents via `xrLocateViews` and inject per-eye asymmetric lens Frustum into `R_SetupProjectionMatrix`.
  - Convert OpenXR tracking Quaternions to Euler angles in `cl_view.c`.
  - Apply 3D physical head translation to `worldviewMatrix` in `R_SetupGL`.
  - Spatial floating 2D quad canvas (`XrCompositionLayerQuad`) for HUD and menus.
* **PCVR Verification Test:**
  - Load Half-Life maps (`c1a0`, `crossfire`). Confirm 6DoF head tracking with 1:1 real-world physical movement, zero optical distortion, and floating HUD.
* **Android Standalone Verification Test:**
  - Run on Quest standalone. Confirm smooth 6DoF head tracking, correct stereo depth, and stable framerate.

---

### ⚪ Phase 03: Universal Action Sets, Controller Poses & Locomotion
* **Goal:** Full motion controller input for Meta Quest Touch and Valve Index.
* **Status:** ⚪ Planned
* **Key Deliverables:**
  - Action set creation (`xrCreateActionSet`) and interaction profiles for Meta Quest Touch (Quest 1/2/Pro/3/3S) and Valve Index.
  - Analog stick locomotion and turn mechanics in `usercmd_t`.
  - Snap turning vs smooth turning modes (`vr_smoothturn`, `vr_snap_angle`).
  - Radial thumbstick deadzone (`0.15`).
  - Digital action buttons (`IN_ATTACK`, `IN_ATTACK2`, `IN_JUMP`, `IN_DUCK`, `IN_USE`, `IN_RELOAD`).
* **PCVR Verification Test:**
  - Full movement, jumping, ducking, and turning tested with controllers on Linux PCVR.
* **Android Standalone Verification Test:**
  - Full movement and controller interactions verified on Quest Standalone.

---

### ⚪ Phase 04: 6DoF Weapon Decoupling & Off-Hand Flashlight
* **Goal:** True physical weapon aiming and realistic flashlight illumination.
* **Status:** ⚪ Planned
* **Key Deliverables:**
  - Weapon viewmodel decoupling from gaze in `gl_studio.c`, locked to dominant controller aim pose.
  - Independent physical off-hand flashlight in `cl_tent.c`.
  - Two-handed weapon stabilizer when hands are in close proximity (< 22cm).
  - Reach-to-Use gesture (`+use`) and Crowbar shoulder draw (`slot1`).
* **PCVR Verification Test:**
  - Aim weapon in any direction independently of gaze on PCVR; cast flashlight separately from non-dominant hand.
* **Android Standalone Verification Test:**
  - Verify decoupled aiming and physical flashlight on Quest Standalone.

---

### ⚪ Phase 05: In-Headset Spatial UI, Laser Pointer & VR Options Menu
* **Goal:** Seamless point-and-click UI navigation and dedicated VR configuration screen.
* **Status:** ⚪ Planned
* **Key Deliverables:**
  - 3D laser pointer beam projected from dominant controller onto menu quad canvas.
  - Intersection converted into virtual mouse events (`UI_MouseMove`, `K_MOUSE1`).
  - FWGS `mainui_cpp` integration compiling into `libmenu.so`.
  - Dedicated "VR Options" screen (`menus/VR.cpp` / `CMenuVR`) with comfort, locomotion, laser, and calibration toggles.
  - High-DPI FreeType vector fonts for crystal-clear text legibility in VR.
* **PCVR Verification Test:**
  - Configure VR options and start games using in-headset laser pointer without mouse/keyboard on PCVR.
* **Android Standalone Verification Test:**
  - Standalone in-headset menu navigation and settings persistence verified on Quest.

---

### ⚪ Phase 06: Server-Side Ballistics, Momentum Physics & Haptics
* **Goal:** Accurate physical projectile origins and rich tactile feedback.
* **Status:** ⚪ Planned
* **Key Deliverables:**
  - Connect OpenXR controller aim pose to `hlsdk-portable` server traces (`FireBullets`, `TraceAttack`).
  - Bullets, Tau beams, and RPG rockets spawn from weapon barrel origin (`pev->vuser1`).
  - Grenade and satchel throwing velocity computed from physical hand swing momentum (`pev->vuser3`).
  - Multi-channel OpenXR action haptic impulses for weapon recoil, charging, and damage.
* **PCVR Verification Test:**
  - Bullets and rockets emerge from physical weapon barrel on PCVR; distinct haptic vibrations felt on controllers.
* **Android Standalone Verification Test:**
  - Muzzle ballistics, grenade throwing physics, and controller haptics verified on Quest Standalone.

---

### ⚪ Phase 07: Immersive Presence, 3D Spatial Audio & World Mechanics
* **Goal:** Maximum physical presence and spatial acoustic realism.
* **Status:** ⚪ Planned
* **Key Deliverables:**
  - Rigged 3D HEV suit hands attached to controller 6DoF transforms with dynamic finger curling.
  - OpenAL Soft HRTF 3D binaural spatial audio for spherical sound localization.
  - Room-scale physical crouching via HMD delta below calibrated standing height (`vr_height_adjust`).
  - Physical ladder climbing and hand-directed swimming.
* **PCVR Verification Test:**
  - 3D audio localization and room-scale crouching tested in vents and obstacle courses on PCVR.
* **Android Standalone Verification Test:**
  - HRTF spatial audio and room-scale mechanics tested on Quest Standalone.

---

### ⚪ Phase 08: Official Expansions & Total Conversions Support
* **Goal:** Out-of-the-box compatibility with the GoldSrc modding library.
* **Status:** ⚪ Planned
* **Key Deliverables:**
  - Native VR weapon rigs for *Half-Life: Opposing Force* (Pipe Wrench, Barnacle Grapple, Displacer Cannon).
  - Native VR support for *Half-Life: Blue Shift*.
  - Total conversion compatibility testing (*They Hunger*, *Cry of Fear*).
* **PCVR Verification Test:**
  - Play through opening chapters of Opposing Force and Blue Shift on PCVR.
* **Android Standalone Verification Test:**
  - Expansions verified on Quest Standalone.

---

## 🛠️ 3. Execution & Verification Commands

### 🐧 Desktop PCVR (Linux Monado / SteamVR / WiVRn)
```bash
# 1. Clean build and installation
./waf configure --build-type=release --enable-openxr --enable-gl-vr
./waf build -j$(nproc)
./waf install --destdir=./out

# 2. Run with WiVRn / Monado launcher
./scripts/run_wivrn.sh crossfire
```

### 🥽 Meta Quest Standalone (Android APK)
```bash
# 1. Set environment variables
export ANDROID_HOME=$HOME/Android/Sdk
export JAVA_HOME=/opt/android-studio/jbr
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH

# 2. Package the APK
./scripts/build_quest_apk.sh

# 3. Install and run on headset
adb install -r out/xash3d-vr-quest.apk
adb shell am start -n su.xash.engine/.MainActivity

# 4. Monitor OpenXR logs
adb logcat -s OpenXR XashVR DEBUG AndroidRuntime:E
```
