# 🗺️ Xash3D VR — Roadmap & Technical Issue Tracker

> Master tracking document for development phases, empirical verification gates, and historical root cause analyses.

---

## 🚀 1. Master Development Roadmap

| Phase | Description | Status | Empirical Validation Gate |
| :---: | :--- | :---: | :--- |
| **01** | **OpenXR Baseline & Dual-Platform Bring-Up** | 🟢 **Completed** | Clean OpenXR instance negotiation, GLX/EGL graphics context sharing, and dual swapchain creation verified on PCVR and Quest. |
| **02** | **Stereo Rendering, Asymmetric Frustum & 6DoF** | 🟢 **Completed** | Full stereo 3D rendering with correct culling in `crossfire` and `c1a0`. Black screen resolved via `gl4es_registerExternalTexture`. Eye buffer dump: `Mean RGB > 60-117`. |
| **03** | **Universal Action Sets, Touch Poses & Locomotion** | 🟢 **Completed** | Analog stick locomotion, snap/smooth turn, action buttons (fire, alt-fire, jump, crouch, use, reload, flashlight, menu), two-handed stabilizer, weapon cycling, left-handed mode. |
| **04** | **6DoF Weapon Decoupling & Off-Hand Flashlight** | 🟡 **Active** | Weapon viewmodels locked to dominant controller aim pose; physical flashlight casting dynamically from off-hand controller (`cl_tent.c`). |
| **05** | **In-Headset Spatial UI, Laser Pointer & VR Options** | 🟡 **Active** | 3D laser pointer for menus (`XR_UpdatePointerCursor`) & floating quad layer interaction verified in simulation; dedicated VR options screen (`CMenuVR`) pending. |
| **06** | **Server-Side Ballistics, Momentum Physics & Haptics** | ⚪ Planned | Bullets, rockets, and Tau beams spawned from physical muzzle (`pev->vuser1`); physical grenade throwing momentum (`pev->vuser3`); full haptic library integration. |
| **07** | **Immersive Hand Presence & 3D Spatial Audio** | ⚪ Planned | Articulated hand models with animated fingers and 3D HRTF spatialized audio via OpenAL Soft. |
| **08** | **Expansions (Opposing Force, Blue Shift) & Mod Suite** | ⚪ Planned | Complete support for Gearbox expansions, weapon packs, and GoldSrc singleplayer/multiplayer mods. |

---

## 🔍 2. Resolved Technical Issues Knowledge Base

### Issue #1: Main Menu 2D (`mainui`) Black Screen / Invisible at Startup
* **Root Cause:** In static builds, `GL_FRAMEBUFFER_OBJECT_EXT` was not properly enabled in the GL4ES translation wrapper, preventing `tr.targets.screen.fbo` offscreen render target from allocating.
* **Resolution:** Enabled `GL_FRAMEBUFFER_OBJECT_EXT` and `GL_FRAMEBUFFER_BLIT_EXT` in `gl_opengl.c`. Added dynamic blit of `tr.targets.screen` directly to the OpenXR Eye 0 swapchain in `R_RenderXRMenu()`.

### Issue #2: Menu/HUD Quad Layer Anchored to Physical Room Floor
* **Root Cause:** Quad layers were referencing `STAGE` reference space directly. When room calibration or floor height differed from eye level, the floating canvas rendered stuck in the ground.
* **Resolution:** Created `g_xrViewSpace` (`XR_REFERENCE_SPACE_TYPE_VIEW`). Floating HUD and menus are anchored in head-relative space at `z = -1.5m`, remaining comfortably centered regardless of player height or posture.

### Issue #3: Quest 3S Black Screen on 3D World Scene (Critical Root Cause)
* **Root Cause:**
  1. `gl4es` was unaware of swapchain texture IDs allocated by OpenXR via Android `AHardwareBuffer` (since they were not created via `glGenTextures`). In response, GL4ES created empty dummy textures in the FBO, drawing the scene to a ghost texture while the real OpenXR swapchain remained 100% black in the TimeWarp compositor.
  2. The frustum planes in `ref/gl_vr/gl_frustum.c` had inverted normals, causing `R_RecursiveWorldNode()` to cull 100% of world geometry.
  3. Alpha channel mask on Qualcomm Adreno TBDR triggered a fast-clear that zeroed RGB values upon frame completion.
* **Resolution:**
  - Implemented `gl4es_registerExternalTexture()` in `3rdparty/gl4es/gl4es/src/gl/texture_params.c`.
  - Added direct dynamic link to Qualcomm Adreno `libGLESv2.so` via `R_InitRealGLES()` in `ref/gl_vr/gl_rmain.c`.
  - Re-derived inward frustum normals in `ref/gl_vr/gl_frustum.c`.
  - Restructured alpha protection before `XR_EndEye()` with explicit FBO unbinding and `glFlush()`.

### Issue #4: Omission of `glFlush()` before `xrReleaseSwapchainImage`
* **Root Cause:** OpenXR §10.3 requires OpenGL commands on a swapchain texture to be flushed to GPU execution before releasing the image back to the compositor.
* **Resolution:** Added `glFlush()` dynamically via `GL_GetProcAddress("glFlush")` in `XR_EndEye()` before `xrReleaseSwapchainImage()`.

### Issue #5: Premature OpenXR Frame Closing & HUD Disconnect
* **Root Cause:** `XR_EndEye` and `XR_EndFrame` were called during `R_RenderFrame()`, before `V_PostRender()` drew the 2D HUD (health, ammo, crosshair) to `tr.targets.screen`.
* **Resolution:** Moved OpenXR frame submission to `R_EndFrame()`. Added `GL_BlendTargetQuad()` to blend `tr.targets.screen` onto both eye FBOs with alpha masking before releasing swapchain textures.

### Issue #6: Desktop PCVR (Monado) GLX Visual ID Binding Failure
* **Root Cause:** `glw_state.visualid` was uninitialized in the engine, resulting in `visualid = 0` and error `xrCreateSession failed with code -38` on X11 PCVR runtimes.
* **Resolution:** Added explicit querying of `glXGetConfig(glw_state.x11_display, &fbConfig, GLX_VISUAL_ID, &visualid)` and populated `glw_state.visualid` in `ref_gl_vr`.

### Issue #7: Two-Handed Weapon Stabilizer Aim Inversion & Accidental Activation
* **Root Cause:**
  1. Hand-to-hand vector math had inverted axes when converted to GoldSrc coordinates, causing weapon aim to point backwards and upside down when hands came close.
  2. Two-handed mode triggered purely on distance (< 22cm), snapping weapon aim unexpectedly during normal hand rest or reloading.
* **Resolution:** Corrected vector conversion (`aimDir = frontHand - rearHand` in GoldSrc coordinates) and conditioned activation on the secondary controller's Grip button (`grip > 0.4`) within 12cm–55cm.

### Issue #8: Early Config CVar Warnings ("Unknown command vr_...")
* **Root Cause:** VR CVars were registered during `XR_Init()`, which executes inside `Host_Frame()`. Startup configuration files (`config.cfg`, `valve.rc`) execute earlier during `Host_Init()`.
* **Resolution:** Added `XR_RegisterCVars()` called directly in `Host_Init()` in `engine/common/host.c`.

### Issue #9: In-Headset 2D Menus / Quad HUD Laser Pointer Interaction Non-Functional
* **Symptoms:** When running the APK in-headset on the Meta Quest 3S, 2D in-game menus (mainui, pause menu, options) were visible on the floating quad, but VR controller pointer clicks and cursor interaction did not interact with or activate UI buttons.
* **Root Causes:**
  1. *Space Mismatch:* `XR_UpdatePointerCursor()` originally queried controller poses in `STAGE` roomscale space (floor at $Y=0$, head at $Y \approx 1.5m$), whereas the floating menu quad layer is positioned in head-relative `g_xrViewSpace` (head at $(0,0,0)$, quad at $Z=-1.5m$). The raycast was testing against $Y \in [-0.45, 0.45]$, which was below floor level in room coordinates and therefore `hit` was permanently `false`.
  2. *Android Touchscreen Emulation Hijack:* On Android, `Touch_WantVisibleCursor()` defaulted to `true`, causing `IN_MouseMove()` to abort and all clicks in `Touch_KeyEvent()` to redirect to touchscreen coordinates, calling `Platform_GetMousePos()` which returned $(0,0)$.
  3. *Missing Pointer Coordinates in Platform Input:* `Platform_GetMousePos()` in `in_sdl2.c` only called `SDL_GetMouseState()`, returning 0 on Quest since no physical mouse exists.
  4. *Missing FBO Allocation:* In `ref_gl_vr`, `tr.targets.screen.fbo` was only allocated if `r_scene_scale != 1.0f`.
* **Resolution:**
  - Rewrote `XR_UpdatePointerCursor()` to locate the controller directly in `g_xrViewSpace` using `xrLocateSpace(handSpace, g_xrViewSpace, syncTime, &loc)`.
  - Added simulated hands fallback (`vr_test_hands 1`, `vr_test_hand_yaw`, `vr_test_hand_pitch`, `vr_test_click`) to enable fully automated CI/headless simulation testing.
  - Disabled touch cursor emulation when VR is active in `in_touch.c` (`if (XR_IsActive()) return false;`).
  - Forwarded laser pointer screen pixel coordinates in `Platform_GetMousePos()` via `XR_GetPointerCursorPos()`.
  - Forced `tr.targets.screen` FBO allocation whenever `XR_IsActive()` in `ref/gl_vr/gl_fbo.c`.
  - Extended Eye 0 buffer dumping to 2D menus in `ref/gl_vr/gl_rmain.c` via `R_VR_CheckDumpEye0()`.
  - Validated via automated Monado simulation (`simulate_menu.cfg`): controller hovered over "Hazard course", highlighted the button orange, clicked the trigger, and launched the game level `t0a0`.
* **Status:** 🟢 **Resolved** (Phase 05 UI laser pointer gate passed).

---

## ⚠️ 3. Active & Pending Hardware Issues (Discovered in Quest 3S Testing)

### Issue #10: Meta Horizon OS 2D Android Launcher UI Layout & Font Scaling Glitches
* **Symptoms:** When launching the APK from the Meta Horizon OS library in 2D panel mode, the launcher interface shows visual imperfections (font scaling broken, menu bars misaligned).
* **Root Cause & Investigation Path:** Android UI layouts in `android/app/src/main/res/layout/` and styles were optimized for standard phone screens rather than Horizon OS resizable floating 2D panel windows. Needs responsive layout constraints, font scaling, and toolbar styling adjustments.
* **Status:** 🟡 **Active / Backlogged** — Scheduled for launcher UI polish pass.

### Issue #11: Weapon Laser Sight Muzzle Emitter Displaced on Weapons Lacking Attachments or Under Two-Handed Grip
* **Symptoms:** On certain weapons (e.g. Crossbow, Hornet Gun, Crowbar, or custom models), the 3D laser sight beam did not emerge from the physical tip of the barrel. Instead, it originated from the player's hand/wrist or became displaced when two-handed grip stabilization was engaged.
* **Root Cause:**
  1. In `gl_rmain.c`, the laser sight checked `if (tr.viewent && !VectorIsNull(tr.viewent->attachment[0]))`. Models without a compiled muzzle attachment (such as `v_crossbow.mdl` and `v_hgun.mdl`) had `attachment[0]` filled with the viewmodel root origin (the hand/wrist) in `R_StudioClientEvents`.
  2. The fallback path in `gl_rmain.c` projected from the raw controller wrist without considering the viewmodel entity's orientation or barrel length.
* **Resolution:**
  - Implemented a 3-tier cascade in `gl_studio.c` and `gl_rmain.c`:
    1. If authored `attachment[0]` exists, use it.
    2. If `attachment[0]` is missing or unprojected at the root origin, automatically inspect `studiohdr_t->bbmax[0]` and project a virtual muzzle forward along the model's physical barrel axis (`origin + forward * barrel_len + up * barrel_up`).
    3. In `gl_rmain.c`, calculate fallback start from `tr.viewent->origin` with forward projection, guaranteeing that custom weapons from mods and expansions without attachments automatically emit lasers and ballistics from the barrel tip.
  - Verified across the arsenal via Monado simulation dumps (`simulate_weapons_laser.cfg`).
* **Status:** 🟢 **Resolved** (Geometric studio bounding box heuristic active).

