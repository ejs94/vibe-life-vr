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
| **05** | **In-Headset Spatial UI, Laser Pointer & VR Options** | ⚪ Planned | 3D laser pointer for menus (`XR_UpdatePointerCursor`), floating quad layer interaction, and dedicated in-game VR options screen (`CMenuVR`). |
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
