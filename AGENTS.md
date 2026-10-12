# 🤖 AI Agent & Developer Guidelines (`AGENTS.md`)

> **Authoritative Engineering Rules, Architecture Policies, and Contribution Standards**  
> **Repository:** `xash3d-fwgs-vr`  
> **API Standard:** Pure Khronos OpenXR 1.0/1.1 (C99)  
> **Upstream Alignment:** Strict compatibility with [FWGS/xash3d-fwgs](https://github.com/FWGS/xash3d-fwgs)

---

## 🎯 1. Mission & Purpose

This document explicitly defines the mandatory rules of engagement, architectural patterns, coding styles, and commit conventions that **MUST** be strictly followed by any AI agent or human engineer working on the `xash3d-fwgs-vr` codebase.

The primary objective is to maintain clean, modular, upstream-compatible code suitable for submission to official FWGS repositories while delivering first-class Virtual Reality parity for classic Half-Life on both **Desktop PCVR** and **Meta Quest Standalone**.

---

## ⚖️ 2. Absolute Directives & User Constraints

Any agent operating in this repository must rigorously adhere to the following non-negotiable rules:

### 1. 100% English Official Documentation & Logs
- All official project documentation files, architecture specifications, progress trackers, code comments, log messages (`Con_Printf`), and git commit messages **MUST** be written in **English**.
- No Portuguese or non-English text is permitted in official project files.

### 2. Meta Quest Standalone Platform Decoupling
- Always target the **Meta Quest Standalone** platform family (Quest 1, 2, Pro, 3, 3S) generically via Android (`arm64-v8a`).
- **NEVER** couple code, Gradle scripts, build automation, manifests, or documentation specifically to "Quest 3S" or any single headset model.

### 3. Strictly Menu-Driven Game Saving (No Gestural Quick-Save)
- Saving and loading the game **MUST** remain strictly managed through in-game menus (Menu $\rightarrow$ Save / Load).
- **NEVER** implement quick-save or quick-load physical gestures (such as behind the back or shoulder reaches). Accidental quick-saves in combat lead to catastrophic gameplay frustration.

### 4. Zero Proprietary Vendor Bloat (Pure OpenXR C99)
- Do not import proprietary Oculus/Meta VrApi legacy code or wrap OpenXR calls in Java Native Interface (JNI).
- The engine core must remain pure standard C99 using the canonical Khronos OpenXR loader (`-lopenxr_loader`).

### 5. Prohibited Absolute Local Paths
- **NEVER** include local user absolute filesystem paths (such as `/home/username/...` or user account directories) in git commits, commit messages, code comments, scripts, or documentation.
- All file references in committed documentation and code **MUST** be relative to the repository root (e.g., [`engine/platform/openxr/xr_core.c`](engine/platform/openxr/xr_core.c)) or use generic environment variables (`$HOME`, `$ANDROID_SDK_ROOT`).

### 6. Single Source of Truth for Documentation (Root Directory)
- All official project documentation lives together centralized at the root of the repository, readily accessible at the top level: [`README.md`](README.md), [`ROADMAP.md`](ROADMAP.md), [`WHY_THIS_PROJECT_EXISTS.md`](WHY_THIS_PROJECT_EXISTS.md), [`VR_PORT_PLAN.md`](VR_PORT_PLAN.md), [`VR_TECHNICAL_ARCHITECTURE.md`](VR_TECHNICAL_ARCHITECTURE.md), and [`AGENTS.md`](AGENTS.md).

### 7. Tri-Platform Quality Gate (Mandatory Testing Policy)
- **No phase, epic, or stage may be marked as complete without empirical build and functional verification across ALL THREE target platforms:**
  1. **Desktop PCVR:** Linux x86_64 via Monado, WiVRn, SteamVR, or ALVR (`./waf build` + `./scripts/run_wivrn.sh`).
  2. **Meta Quest Standalone:** Android arm64-v8a via Gradle packaging (`./scripts/build_quest_apk.sh`) and ADB device testing (`./scripts/test_quest_auto.sh`).
  3. **Android Flat (2D) Mobile:** Android Studio Emulator (`./scripts/build_flat_apk.sh` + `./scripts/test_emulator_flat.sh`).
- Never claim a feature is complete merely because C code compiles without syntax errors. All three platforms must be empirically validated before advancing to subsequent milestones.

### 8. Crossplay & Vanilla Server Fallback Architecture
- **Multiplayer & Mod Interoperability**: VR clients (PCVR / Quest) and standard Flat clients (Android / Desktop) must be able to play together seamlessly.
- **Vanilla Server Fallback**: On vanilla Half-Life / GoldSrc servers without VR addons, VR clients map dominant hand weapon aiming directly to `usercmd_t->viewangles`. No packet alteration; 100% network backward compatibility.
- **VR-Enhanced Servers**: Server-side addons negotiate VR capabilities via engine-enforced userinfo (`*cl_vr`, `*cl_vr_caps`, `*cl_vr_device` defined in [`vr_protocol.h`](engine/common/vr_protocol.h)) enabling decoupled weapon muzzle rays and 6DoF hand pose replication without breaking Flat clients.
- **Android Touch & Upstream Mod Preservation**: VR modifications must never degrade or alter standard mobile touch HUD widgets, GoldSrc mod parsing, or upstream FWGS mainline compatibility.

---

## 🏛️ 3. Architectural Design Principles

### 1. Zero Bloat & Opt-In Build Flags
- All VR features must remain **strictly opt-in** and disabled by default in standard non-VR builds.
- Configure via Waf options (`--enable-openxr`, `--enable-gl-vr`). The engine **MUST** continue to compile cleanly across all supported operating systems when the OpenXR SDK is not installed.

### 2. Subsystem Isolation (`engine/platform/openxr/`)
- All OpenXR runtime management belongs in [`engine/platform/openxr/`](engine/platform/openxr), guarded by `#if XASH_OPENXR`:
  * [`xr_core.c`](engine/platform/openxr/xr_core.c): Instance/session lifecycle, reference spaces, unified `convar_t` registrations.
  * [`xr_graphics.c`](engine/platform/openxr/xr_graphics.c): Graphics context extraction (Linux X11/GLX and Android EGL).
  * [`xr_swapchain.c`](engine/platform/openxr/xr_swapchain.c): Paced frame loop, swapchains, asymmetric optical Frustum (`XR_GetEyeFrustum`), and floating 3D quad layer.
  * [`xr_input.c`](engine/platform/openxr/xr_input.c): Action sets, interaction profiles, thumbstick deadzones, and 6DoF hand spaces.
- Always provide clean empty stubs when OpenXR is compiled out, preventing `#ifdef` sprawl across the engine core.

### 3. Modular Ref API Stereo Renderer (`ref/gl_vr/`)
- Stereo scene presentation is encapsulated in [`ref/gl_vr/`](ref/gl_vr), compiling as an independent shared library (`libref_gl_vr.so`).
- Gaze decoupling and weapon viewmodel binding onto controller aim poses are handled in [`gl_studio.c`](ref/gl_vr/gl_studio.c).
- Independent off-hand physical flashlight is handled in [`engine/client/cl_tent.c`](engine/client/cl_tent.c).

### 4. Native FWGS MainUI C++ Integration (`3rdparty/mainui/`)
- Graphical in-headset settings are integrated into `3rdparty/mainui/` compiling into `libmenu.so`.
- The VR options screen is implemented in [`3rdparty/mainui/menus/VR.cpp`](3rdparty/mainui/menus/VR.cpp) (`CMenuVR`), exposing comfort, turn angles, laser sights, flashlight modes, handedness, weapon pitch, world scale, and height calibration.

---

## 🏷️ 4. Commit Tagging Convention (Strict FWGS Standard)

Every git commit **MUST** follow the official FWGS tagging format defined in `CONTRIBUTING.md`:

```text
tag: short description
tag: subtag: short description
```

### ✅ Valid Examples:
* `platform: openxr: implement canonical hardware frame loop`
* `ref: gl_vr: add real-time 3D weapon laser sight`
* `input: openxr: map motion controller action sets to usercmd`
* `menu: vr: implement in-headset VR options menu`
* `docs: update master index and architecture specifications`

### ❌ Invalid Examples (NEVER use):
* ❌ `feat: add VR support`
* ❌ `fixed bug in rendering`
* ❌ `WIP OpenXR`
* ❌ `Update files`

---

## 📝 5. Code Style & Formatting Guidelines

Xash3D FWGS follows the classic Quake / HLSDK coding style:

### 1. Indentation
* Use **TABS ONLY** for indentation. Spaces for indentation are strictly forbidden.

### 2. Curly Braces `{ }`
* **Every opening and closing brace must have its own separate line:**
  ```c
  // CORRECT:
  if( condition )
  {
  	do_something();
  }

  // INCORRECT:
  if (condition) {
      do_something();
  }
  ```

### 3. Parenthesis Spacing
* Place spaces inside simple parentheses: `if( condition )`, `func( arg1, arg2 )`.
* Do NOT place spaces between nested parentheses: `if(( a && b ))`.

### 4. Magic Numbers
* Prohibited. Always use declared `enum` values or `#define` constants.

### 5. Xash3D CRT Utilities
* Prefer engine CRT abstractions over raw standard C library calls:
  * `Q_snprintf()` instead of `snprintf()`
  * `Q_strncpy()` instead of `strncpy()`
  * `Q_malloc()` / `Mem_Alloc()` for memory allocation
  * Math utilities from `xash3d_mathlib.h`

---

## 📁 6. Central Documentation Structure

All official project documentation resides centralized at the repository root:

| Document | Purpose |
| :--- | :--- |
| [`README.md`](README.md) | **Master Project Hub** and executive overview. |
| [`WHY_THIS_PROJECT_EXISTS.md`](WHY_THIS_PROJECT_EXISTS.md) | Foundational manifesto comparing Xash3D VR vs. Lambda1VR and outlining FWGS alignment. |
| [`ROADMAP.md`](ROADMAP.md) | Official 12-stage roadmap and milestone deliverable tracker. |
| [`VR_PORT_PLAN.md`](VR_PORT_PLAN.md) | Phased technical development plan and task execution matrix. |
| [`VR_TECHNICAL_ARCHITECTURE.md`](VR_TECHNICAL_ARCHITECTURE.md) | Low-level engineering specification, rendering call chain, and hardware loop details. |
| [`AGENTS.md`](AGENTS.md) | Authoritative AI agent and developer guidelines (this document). |

---

## 🚀 7. Meta Quest Agent Workflow & Testing Directives

When operating on standalone Meta Quest builds or performing automated device qualification, all AI agents **MUST** comply with the following directives (see full specification in [`.agents/WORKFLOW.md`](.agents/WORKFLOW.md)):

### 1. Isolated Agent Tooling Directory (`.agents/`)
* All transient AI agent scripts, test loops, and MCP configurations **MUST** reside within the [`.agents/`](.agents) directory.
* Never place ephemeral LLM tooling or experimental test harnesses directly into root `scripts/` or engine source folders.

### 2. Execute the Inspected Device Loop (`.agents/scripts/quest_device_loop.sh`)
* Never perform unverified or blind `adb install` commands.
* Always execute the standardized verification loop:
  ```bash
  ./.agents/scripts/quest_device_loop.sh loop [optional_apk_path]
  ```
* Ensure that the device serial, package identity (`su.xash.engine`), SHA-256 digest, and runtime permissions (`RECORD_AUDIO`, storage) are explicitly verified before launching the activity.

### 3. Adhere to the Two-Lane Build Contract
* **Warm Iteration Lane:** For active code modifications and quick tests, reuse compiler objects and intermediate outputs. Never trigger a full clean build (`make clean` / `./waf distclean`) for trivial source edits.
* **Release Candidate Lane:** Only invoke clean candidate assembly when packaging milestone releases or creating reproducible candidate evidence.

### 4. Respect the OpenXR Tracking Boundary
* The 6DoF tracking stream is bound exclusively to the foreground application process. Never attempt to read or mock OpenXR tracking data via external Android shell helpers (`UID 2000`).
* All tracking interactions must occur natively through standard OpenXR API handles (`xrLocateSpace`) or transparent OpenXR API Layers (such as Meta XR Operator).


