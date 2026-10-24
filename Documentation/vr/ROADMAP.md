# 🗺️ Xash3D VR — Roadmap & Technical Issue Tracker

> Master tracking document for development phases, empirical verification gates, and historical root cause analyses.

---

### 🏷️ Status Conventions & Remediation Policy
* 🟢 **Completed:** Empirically validated in dual-platform tests with zero known blockers or visual regressions.
* 🟠 **Maintenance / Remediation:** A bug, visual glitch, or physics defect was identified in a phase. The phase is actively reopened for maintenance until re-verified.
* 🟡 **Active:** Initial feature engineering and baseline bring-up in active progress.
* ⚪ **Planned:** Scheduled milestone awaiting activation.

## 🚀 1. Master Development Roadmap

| Phase | Description | Status | Empirical Validation Gate |
| :---: | :--- | :---: | :--- |
| **01** | **OpenXR Baseline & Dual-Platform Bring-Up** | 🟢 **Completed** | Clean OpenXR instance negotiation, GLX/EGL graphics context sharing, and dual swapchain creation verified on PCVR and Quest. |
| **02** | **Stereo Rendering, Asymmetric Frustum & 6DoF** | 🟢 **Completed** | Full stereo 3D rendering with correct culling in `crossfire` and `c1a0`. Black screen resolved via `gl4es_registerExternalTexture`. Eye buffer dump: `Mean RGB > 60-117`. |
| **03** | **Universal Action Sets, Touch Poses & Locomotion** | 🟢 **Completed** | Analog stick locomotion, snap/smooth turn, action buttons (fire, alt-fire, jump, crouch, use, reload, flashlight, menu), two-handed stabilizer, weapon cycling, left-handed mode. Physical roomscale ducking (`vr_physical_crouch`) and VR ladder movement decoupled from head pitch. |
| **04** | **6DoF Weapon Decoupling & Viewmodel Presence** | 🟢 **Completed** | Weapon viewmodels locked to dominant controller aim pose; head-mounted flashlight following view direction + HL2:VR temple gesture click toggle (`cl_tent.c`, `xr_input.c`). Culling of detached offscreen reload props (`Box02`, `Speedload Master`, `shell`) and flat bobbing suppression. |
| **05** | **In-Headset Spatial UI, Laser Pointer & VR Options** | 🟢 **Completed** | Beat Saber-style dual alternating laser pointers for menus (`XR_UpdatePointerCursor`), floating quad layer interaction, and dedicated in-headset VR options screen (`CMenuVR`) fully compiled and verified. |
| **06** | **Server-Side Ballistics, Momentum Physics & Haptics** | 🟢 **Completed** | Physical muzzle ballistics via `pev->vuser1` across all arsenal weapons (`GetGunPosition`), RPG rocket spawn alignment, physical grenade/snark toss momentum via 6DoF velocity (`pev->vuser3`), tripmine 6DoF alignment (`vuser2`), bypass of flat autoaim deflection, and 50% tighter spread under two-handed hold (`vuser4`). |
| **07** | **Immersive Hand Presence & 3D Spatial Audio** | 🟢 **Completed** | 3D HRTF spatial audio & 6DoF listener tracking, dynamic procedural finger curling (trigger, grip, capacitive thumb), standalone hand entity presence (`s_offhandEnt`, `v_hand.mdl`), and full bone rig compatibility (`Bip01 Finger0..4` and `Bone27..45`). |
| **08** | **Mod Suite & Declarative Calibration Manifests** | 🟢 **Completed** | Declarative Weapon Calibration Manifest (`vr_weapons.json` Silver Tier runtime C parser in `xr_profile.c`), per-weapon grip offsets, barrel pitch adjustments, two-handed gating, live `vr_reload_weapon_profiles` hot-reload, and 24/24 automated Monado assertions PASS. |
| **09** | **Visual Polish, Full Body Motion (VRIK) & Immersion** | 🟡 **Active** | Physical Quest 3 on-device validation, 3D Hand Tracking Points & Weapon Center of Mass (COM) Lever Gizmos (`vr_debug_hand`), 3D wireframe hitboxes, real-time HUD telemetry (`Con_NPrintf`), procedural Full-Body Inverse Kinematics (VRIK) experimentation (torso, arms, legs, and spine tracking), weapon collision, holsters, and immersion polish. |

---

## 🔍 2. Resolved Technical Issues Knowledge Base

### Issue #1: Main Menu 2D (`mainui`) Black Screen / Invisible at Startup
* **Root Cause:** In static builds, `GL_FRAMEBUFFER_OBJECT_EXT` was not properly enabled in the GL4ES translation wrapper, preventing `tr.targets.screen.fbo` offscreen render target from allocating.
* **Resolution:** Enabled `GL_FRAMEBUFFER_OBJECT_EXT` and `GL_FRAMEBUFFER_BLIT_EXT` in `gl_opengl.c`. Added dynamic blit of `tr.targets.screen` directly to the OpenXR Eye 0 swapchain in `R_RenderXRMenu()`.

### Issue #2: Menu/HUD Quad Layer Anchored to Physical Room Floor
* **Root Cause:** Quad layers were referencing `STAGE` reference space directly. When room calibration or floor height differed from eye level, the floating canvas rendered stuck in the ground.
* **Resolution:** Created `g_xrViewSpace` (`XR_REFERENCE_SPACE_TYPE_VIEW`). Floating HUD and menus are anchored in head-relative space at `z = -1.5m`, remaining comfortably centered regardless of player height or posture.

### Issue #3: Quest 3 Black Screen on 3D World Scene (Critical Root Cause)
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
* **Symptoms:** When running the APK in-headset on the Meta Quest 3, 2D in-game menus (mainui, pause menu, options) were visible on the floating quad, but VR controller pointer clicks and cursor interaction did not interact with or activate UI buttons.
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

### Issue #10: Meta Horizon OS 2D Android Launcher UI Layout & Font Scaling Glitches
* **Symptoms:** When launching the APK from the Meta Horizon OS library in 2D panel mode, the launcher interface showed visual distortion (Toolbar collapsed to 0 height, game card action buttons colliding or wrapped awkwardly on narrow/scaled floating windows).
* **Root Causes:**
  1. `activity_main.xml`: `Toolbar` had `layout_height="match_parent"` inside a `wrap_content` `AppBarLayout`, causing undefined measurement passes in Android's `LayoutManager` under Horizon OS floating panel resizes.
  2. `card_game.xml`: Game card had a fixed height of `160dp` with both the title badge and the button bar constrained to `bottom_toBottomOf="parent"`, causing horizontal contention and clipping when action buttons had wide text ("TEST GAME", "PLAY IN VR").
* **Resolution:**
  - In `activity_main.xml`, set `Toolbar` height and `minHeight` to `?attr/actionBarSize`.
  - In `card_game.xml`, changed height to `wrap_content` with `minHeight="170dp"`. Split the layout into two independent vertical zones: the game title badge is anchored at top-start (`top_toTopOf="parent"`), and the action buttons are anchored at bottom-end (`bottom_toBottomOf="parent"`).
  - Added full VR preference toggles in `vr_preferences.xml` and wired them to engine startup command-line arguments in `Game.kt`.
* **Status:** 🟢 **Resolved** (Horizon OS responsive launcher UI verified).

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

### Issue #13: Dedicated In-Headset VR Options Configuration Menu (`CMenuVR`)
* **Symptoms:** Modifying VR settings (snap turn angles, two-handed grip, haptics, flashlight mode, world scale, laser sight) required either modifying Android preferences before launch or typing raw console commands in-game.
* **Architecture & Resolution:**
  - Created a dedicated C++ UI class `CMenuVR` (`3rdparty/mainui/menus/VR.cpp`) derived from `CMenuFramework` using `CMenuTabView`.
  - Grouped settings into four ergonomic category tabs:
    - **Tab 1 (Locomotion & Comfort):** `vr_smoothturn` (smooth/snap toggle), `vr_snap_angle` (SpinControl from 15° to 90°), `vr_walkdirection` (head vs controller walk orientation), `vr_physical_crouch` (roomscale squat ducking), and `vr_menu_distance` / `vr_menu_scale`.
    - **Tab 2 (Weapons & Combat):** `vr_lasersight` (3D weapon laser), `vr_headtorch` (HL2:VR style head flashlight), `vr_twohanded` (two-handed stabilization with soft clamp), `vr_lefthanded` (left-handed dominant hand), `vr_proximity_scope` (natural optical zoom), `vr_melee_swing` (physical Crowbar swing), and `vr_weapon_pitchadjust` (-30° to +30°).
    - **Tab 3 (Presence & Audio):** `vr_finger_curling` (procedural finger flex), `vr_offhand_render` (secondary hand presence), `vr_gesture_use` (touch-to-use), `vr_haptics_enabled` (tactile recoil), `vr_pointer_hud` (menu laser pointer), `vr_audio_hrtf` (3D binaural HRTF audio), and `vr_worldscale` / `vr_height_adjust`.
    - **Tab 4 (VR Debug):** `vr_debug_impacts` (3D bullet impact markers and tracers), simulated 6DoF head/hands/curl controls for headless testing, interactive sample recording/clearing buttons (`vr_record_impact`, `vr_clear_impacts`), calibration reset, and real-time hardware telemetry display.
  - Integrated into main options menu (`CMenuOptions` via `UI_VR_Menu` in `Configuration.cpp`), declared in `BaseMenu.h`, and registered console command `menu_vr`.
  - Verified clean native compilation into `out/libmenu.so` and standalone Meta Quest packaging in `out/xash3d-vr-quest.apk`.
* **Status:** 🟢 **Resolved** (In-headset VR 4-tab options menu active and validated).

### Issue #14: Server-Side 6DoF Weapon Muzzle Ballistics & Hitscan Alignment (`dlls/player.cpp`, `dlls/rpg.cpp`, `engine/server/sv_pmove.c`)
* **Symptoms:** Hitscan traces (Glock, MP5, Shotgun, Python) and projectile spawns (RPG, Crossbow bolts, Gauss beams, Hornet Gun) originated from the player's eye level (`pev->origin + pev->view_ofs`) rather than the physical 3D muzzle of the weapon held in 6DoF hand space.
* **Root Cause:**
  - GoldSrc weapons universally call `m_pPlayer->GetGunPosition()`, which historically returned `pev->origin + pev->view_ofs`.
* **Resolution:**
  - In `engine/server/sv_pmove.c`, `clent->v.vuser1` is populated with the dominant controller's muzzle offset via `XR_GetPrimaryHandMuzzleTransform()`.
  - In `3rdparty/hlsdk-portable/dlls/player.cpp`, updated `CBasePlayer::GetGunPosition()`: if `pev->vuser1 != g_vecZero`, return `pev->origin + pev->vuser1`.
  - In `rpg.cpp`, rocket spawn uses `GetGunPosition() + gpGlobals->v_forward * 12.0f` when in VR, eliminating the 1998 flat shoulder offset.
  - Aligned all bullet traces, beams, and rockets with the visible 3D weapon barrel and laser sight.
* **Status:** 🟢 **Resolved** (Muzzle ballistics verified).

### Issue #15: Physical Hand Grenade Tossing Momentum via 6DoF Hand Velocity (`handgrenade.cpp`, `xr_input.c`, `sv_pmove.c`)
* **Symptoms:** Hand grenades thrown with `weapon_handgrenade` deployed with a fixed velocity vector based solely on gaze pitch, ignoring the physical swing speed and angle of the player's arm.
* **Resolution:**
  - In `engine/platform/openxr/xr_input.c`, `XR_GetRightHandVelocity` and `XR_GetLeftHandVelocity` transform OpenXR linear velocity by rotating by `s_playerTurnYaw`, ensuring roomspace momentum correctly projects into game world space.
  - In `engine/server/sv_pmove.c`, populated `clent->v.vuser3` with the dominant hand's world velocity (`XR_GetPrimaryHandVelocity( handVel ) * scale`).
  - In `3rdparty/hlsdk-portable/dlls/handgrenade.cpp`, spawns the grenade at hand level (`pev->origin + pev->vuser1 + gpGlobals->v_forward * 6.0f`) and injects arm swing momentum into `vecThrow` (`vecThrow += m_pPlayer->pev->vuser3 * 1.25f`) when throwing velocity exceeds 40 units/sec.
* **Status:** 🟢 **Resolved** (Physical momentum grenade tossing active).

### Issue #17: 3D Binaural HRTF Spatial Audio & 6DoF Listener Tracking (`s_main.c`, `xr_swapchain.c`, `CMenuVR`)
* **Symptoms:** Audio listener was tied to flat-screen 1998 torso/camera in `cl_view.c`, ignoring physical roomscale head translation and head orientation. Traditional GoldSrc panning only tested `dot = DotProduct(snd.right, source_vec)`, causing severe front-back ambiguity (a sound straight ahead sounded identical to a sound straight behind).
* **Resolution:**
  - Implemented `XR_GetHeadCenterTransform()` in `xr_swapchain.c` to compute the 6DoF midpoint between left and right physical eyes, rotated by locomotion turning yaw and scaled to GoldSrc world units.
  - In `s_main.c` (`S_UpdateFrame()`), dynamically binds `snd.origin` and listener vectors `snd.forward`, `snd.right`, `snd.up` to the true head pose in real time.
  - In `S_SpatializeChannel()`, implemented human pinna directional acoustic shadowing (`dot_front < 0` attenuates rear sounds by up to 22%) and elevation diffraction cues (`dot_up`).
  - Added archived CVar `vr_audio_hrtf` (default 1) and wired toggle into in-headset `CMenuVR` menu.
  - Fixed simulation silence by bypassing `snd_mute_losefocus` when `XR_IsActive()`, and hardened listener basis derivation with `XR_GetHeadCenterTransformWithBasis()` in `xr_swapchain.c`.
  - Validated with automated test gate 1.11 in `run_regression_battery.sh` (14/14 PASS).
* **Status:** 🟢 **Resolved** (3D HRTF spatial audio & 6DoF head listener active).

### Issue #18: Viewmodel Floating Reload Props in VR (Glock Box02, .357 Speedload Master, Shotgun Shells)
* **Root Cause:** In flat-screen 1998 Half-Life, animators hid secondary reload meshes (like the spare Glock clip, speedloader, or loose shotgun shells) by animating their root bones to $Z < -15$ units below the 2D viewport. In 6DoF VR, looking down revealed them hovering in mid-air below the player's hand.
* **Resolution:** Implemented dual-layer suppression in both `ref/gl_vr/gl_studio.c` and `3rdparty/hlsdk-portable/cl_dll/StudioModelRenderer.cpp`. Collapses detached offscreen root bones to zero matrix and skips spare reload submodels (`clip_reference`, `python_speedload`, `shell`) when not actively executing a reload sequence.
* **Status:** 🟢 **Resolved** (No floating reload props in VR viewmodels).

### Issue #19: Flat Autoaim Snap & Recoil Pitch Deflecting Bullets Away from 6DoF Weapon Barrel
* **Root Cause:** Flat-screen `CBasePlayer::GetAutoaimVector` deflected bullets toward nearby enemies and added screen `punchangle`, bending the bullet trajectory away from where the physical gun barrel and laser sight were aimed.
* **Resolution:** In `player.cpp`, bypassed autoaim deflection when in VR (`pev->vuser1 != g_vecZero` or `vuser4.y > 0.0f`), returning the exact 6DoF forward aim vector of `pev->vuser2`. In `combat.cpp`, added two-handed stabilization (`pevAttacker->vuser4.x > 0.0f`) reducing bullet spread by 50%.
* **Status:** 🟢 **Resolved** (Physical 6DoF ballistics & two-handed stabilization active).

### Issue #20: Air Duct Trapping & Inverted VR Ladder Climbing
* **Root Cause:** Physical roomscale squatting dropped the head camera without shrinking the player hull, causing players to get stuck entering air ducts in Black Mesa (`c1a2`). On ladders, climbing direction was tied to head pitch, reversing climb when looking down, and pressing jump launched players backwards into the abyss.
* **Resolution:**
  - Implemented `XR_GetRoomscaleHeadDrop()` in `xr_swapchain.c` and `vr_physical_crouch` in `xr_input.c` (automatically engages `IN_DUCK` when head drops $\ge 28\text{cm}$ below calibrated height).
  - In `pm_shared.c`, decoupled ladder climbing from head pitch (stick forward always climbs UP) and smoothed ladder dismount jump to boost safely onto ledges.
* **Status:** 🟢 **Resolved** (Physical roomscale ducking & smooth VR ladders active).

### Issue #21: 3D Bullet Impact Markers, Flight Tracers & Laser Trace Collision (`vr_debug_impacts`)
* **Symptoms:** Modders and testers lacked visual telemetry to verify whether 3D laser sights, controller aim vectors, and server-side bullet traces converged on the exact same world hit point in 6DoF space.
* **Resolution:**
  - In `ref/gl_vr/gl_rmain.c`, truncated the laser sight beam dynamically against geometry via `CL_TraceLine`, drawing an aligned 3D red surface reticle.
  - Implemented a circular buffer in `xr_core.c` storing up to 32 recent projectile impacts with 5-second persistence.
  - In `gl_rmain.c`, renders a 4-part 3D visual debug marker at each hit: lime-green crosshair (`+`), cyan concentric diamond, orange surface normal line, and translucent trajectory line from muzzle to hit position.
  - Tied to archived CVar `vr_debug_impacts` (default `1`) and integrated into Tab 4 of `CMenuVR`.
* **Status:** 🟢 **Resolved** (3D bullet impact alignment visual debug active).

---

## ⚠️ 3. Active & Pending Hardware Issues (Discovered in Quest 3 Testing)

### Issue #16 / Feature #12: Dynamic Articulated Skeletal 3D Hands & Finger Curling (Half-Life: Alyx / HL2VR Style)
* **Goal & Scope:** Replace static viewmodel-baked hands with fully independent, articulated 3D hand entities whose fingers dynamically follow the player's physical hand inputs in real time.
* **Technical Architecture & Specifications:**
  1. *Independent Skeletal Hand Entity:* Disassociate the hand mesh from the weapon `.mdl`. Implement a standalone hand entity (`clgame.handent` / `v_hand_rig.mdl`) containing a full 15–20 bone finger rig (Thumb, Index, Middle, Ring, Pinky with proximal, intermediate, and distal phalanges).
  2. *Continuous OpenXR Finger Curling Inputs:*
     - **Index Finger:** Driven by the analog trigger axis ($[0.0, 1.0]$) and capacitive touch sensor.
     - **Middle, Ring & Pinky Fingers:** Driven by the analog grip axis ($[0.0, 1.0]$) to wrap around the weapon handle or close into a fist.
     - **Thumb:** Driven by capacitive touch states on the thumbstick, A/X, and B/Y buttons.
  3. *Meta Quest Optical Hand Tracking:* Integration with OpenXR `XR_EXT_hand_tracking` to drive all 26 finger joint poses optically without physical controllers.
* **Status:** 🟡 **Active** (Phase 07 priority).

### Issue #22: Viewmodel Mesh Disappearance on RPG and Laser Tripmine
* **Symptoms:** Equipping the Laser Tripmine (`weapon_tripmine`) displays two floating hands with active finger curling, but the tripmine device itself is completely invisible. The RPG launcher (`weapon_rpg`) is also entirely invisible in 6DoF viewmodel rendering.
* **Root Cause:** In `ref/gl_vr/gl_studio.c` (`R_StudioSetupBones`), reload prop suppression collapsed any root bone (`pbones[i].parent == -1`) where `i > 0` whenever the active sequence was not "reload". In `v_tripmine.mdl` and `v_rpg.mdl`, the weapon chassis meshes are attached to separate root bones (`i > 0`), causing them to be erroneously zeroed out during idle sequences.
* **Status:** 🟢 **Resolved** (Fixed in `ref/gl_vr/gl_studio.c` line 1328: replaced `!is_reload || pos[i][2] < -15.0f` with `!is_reload && pos[i][2] < -15.0f` to prevent collapsing weapon base bodies).

### Issue #23: Ladder Climbing Freeze with VR Analog Thumbstick Locomotion
* **Symptoms:** The player cannot ascend ladders in VR and becomes stuck on the ladder rungs when pushing the thumbstick forward.
* **Root Cause:** In `3rdparty/hlsdk-portable/pm_shared/pm_shared.c` (`PM_LadderMove`), ladder climb velocity evaluation only checked digital button bits `IN_FORWARD` and `IN_BACK`. In VR, continuous thumbstick locomotion sets `cmd.forwardmove` directly (e.g. `+320.0f`), leaving `buttons & IN_FORWARD` unset. With `forward == 0 && right == 0`, `PM_LadderMove` called `VectorClear(pmove->velocity)`, pinning the player in place.
* **Status:** 🟢 **Resolved** (Fixed in `pm_shared.c`: continuous VR thumbstick inputs `pmove->cmd.forwardmove` and `sidemove` added to ladder velocity with speed clamping).

### Issue #24: Projectile & Energy Beam Misalignment on Tau Cannon, Gluon Gun, Hornet Gun & RPG
* **Symptoms:** Certain weapons (Tau Cannon, Gluon Gun, Hornet Gun / Hivehand) are severely misaligned ("vesgas") with the 3D laser sight. Projectiles or beams emerge from the center of the player's eye rather than the physical 6DoF weapon muzzle.
* **Root Cause:** Weapon logic in `dlls/gauss.cpp`, `dlls/egon.cpp`, `dlls/hornetgun.cpp`, and `dlls/rpg.cpp` called `UTIL_MakeVectors(m_pPlayer->pev->v_angle)` (head gaze angles) rather than `m_pPlayer->pev->vuser2` (6DoF weapon barrel aim vector) and added legacy 1998 flat-screen offsets (`gpGlobals->v_right * 8.0f + gpGlobals->v_up * -12.0f`).
* **Status:** 🟢 **Resolved** (Fixed in `gauss.cpp`, `egon.cpp`, `hornetgun.cpp`, and `rpg.cpp`: full 6DoF muzzle transform `pev->vuser1` / `GetGunPosition()` and aim vector `pev->vuser2` utilized, legacy 2D screen offsets stripped).

### Issue #25: Inverted Weapon Roll Axis in 6DoF Controller Mapping
* **Symptoms:** Rotating the physical hand around the longitudinal axis (roll) causes the virtual weapon to roll in the opposite direction.
* **Root Cause:** In `XR_QuatToEuler` (`engine/platform/openxr/xr_swapchain.c`), the conversion formula from OpenXR quaternion to GoldSrc Euler angles produces an opposite sign for roll relative to the GoldSrc viewmodel coordinate frame.
* **Status:** 🟢 **Resolved** (Fixed in `engine/platform/openxr/xr_swapchain.c`: negated roll in `XR_QuatToEuler` via `out_angles[2] = -roll * (180.0f / M_PI)`).

### Issue #26: Physical Melee Swing Trigger Threshold and Unit Scale Discrepancy
* **Symptoms:** The crowbar is displaced from the physical controller, and swinging the arm rapidly fails to trigger melee attacks.
* **Root Cause:** In `XR_ProcessPhysicalMeleeSwing` (`engine/platform/openxr/xr_input.c`), velocity threshold checks `speed > 48.0f` expecting GoldSrc units, but `XR_GetPrimaryHandVelocity` returns raw OpenXR metric velocity in m/s (typically 1.0–2.5 m/s), meaning the threshold is never satisfied. Additionally, `v_crowbar.mdl` has an exaggerated pitch/grip offset in `vr_weapons.json`.
* **Status:** 🟢 **Resolved** (Fixed in `xr_input.c`: metric velocity multiplied by `worldScale` for proper GoldSrc speed thresholding; crowbar grip offset in `vr_weapons.json` calibrated).

### Issue #27: Analog Locomotion Yaw Flip & Controller Tracking Occlusion Drift
* **Symptoms:** During smooth locomotion, the player occasionally loses movement orientation and moves in the exact opposite direction of thumbstick deflection.
* **Root Cause:** In `XR_ProcessLocomotionAndTurn` (`engine/platform/openxr/xr_input.c`), `deltaYaw` derivation experiences 180° gimbal wrapping when the controller pitch reaches vertical angles. Furthermore, brief tracking losses on the Quest fallback to unrotated eye angles, producing abrupt direction inversions.
* **Status:** 🟢 **Resolved** (Fixed in `xr_input.c`: clamped controller pitch within $[-89^\circ, 89^\circ]$ to prevent sign inversion in `cos(pitch)`, and used secondary hand orientation for controller-directed locomotion).

### Issue #28: Floating 2D Menu Quad Ergonomic Distance and Recenter Desynchronization
* **Symptoms:** The floating menu quad is positioned too far away in the Quest 3 FOV, and executing recenter does not reposition the menu quad in front of the user's current gaze.
* **Root Cause:** `vr_menu_distance` defaults to 1.5m–2.2m. The `vr_recenter` command (`R_VR_Recenter_f`) resets engine head origin calibration but fails to call `XR_ResetMenuAnchor()`, leaving the OpenXR quad reference space unchanged.
* **Status:** 🟢 **Resolved** (Fixed in `xr_core.c`, `xr_swapchain.c`, `xr_input.c`, and `ref/gl_vr/gl_rmain.c`: default distance set to 1.15m and scale to 1.15m; `R_VR_Recenter_f` explicitly calls `XR_ResetMenuAnchor()`).

### Issue #29: Crossbow Telescopic Scope Engagement & Optical Zoom Control
* **Symptoms:** No clear input or gesture exists to engage the telescopic sniper scope on the Crossbow in VR.
* **Root Cause:** Button B in HL2:VR mode continually asserts `IN_ATTACK2`, causing scope FOV bouncing in `dlls/crossbow.cpp`. The proximity scope detector (`XR_ProcessProximityScope`) requires strict 15cm eye distance and two-handed stabilization, which is difficult to achieve reliably on the Quest 3 without tactile feedback.
* **Status:** 🟢 **Resolved** (Fixed in `xr_input.c`: leading-edge single-tap debounce for toggle weapons on Button B, and enlarged proximity scope trigger distance to 24cm).

### Issue #30: Offhand Standalone Entity Disconnect and Viewmodel Mesh Separation
* **Symptoms:** Floating hands do not render independently; the secondary hand remains permanently tethered to the viewmodel mesh.
* **Root Cause:** `R_DrawOffHand` in `ref/gl_vr/gl_studio.c` only attempts to load `models/v_hand.mdl` once at startup; if missing from the mod folder, it silently disables offhand rendering. Furthermore, legacy GoldSrc weapon models with dual hands baked into a single mesh lack programmatic vertex suppression when not in two-handed grip mode.
* **Status:** 🟢 **Resolved** (Fixed in `xr_core.c`, `ref/gl_vr/gl_studio.c`, and `android/app/build.gradle.kts`: `vr_offhand_render 1` enabled by default, retry loading mechanism implemented, assets packaged directly in APK).

### Issue #31: Weapon Grip Center Decentering on Meta Quest Touch Plus Controllers
* **Symptoms:** Weapons and the crowbar appear decentered relative to the physical Touch Plus grip and ringless tracking origin.
* **Root Cause:** Weapon profiles in `assets/valve_vr/models/vr_weapons.json` were calibrated for generic OpenXR controllers and require precision tuning for the Quest 3 Touch Plus grip geometry.
* **Status:** 🟢 **Resolved** (Fixed in `assets/valve_vr/models/vr_weapons.json`: calibrated crowbar grip offset `[0.0, 0.5, -0.5]` and pitch adjust `-2.0`, packaged into APK and host distribution).

### Feature Milestone: 3D Hand Tracking Points, Weapon Center of Mass (COM) Lever Gizmos & Real-Time Telemetry
* **Objective:** Enable continuous in-game and in-headset visual inspection of 6DoF hand tracking origins, physical weapon Center of Mass (COM) moment arms, anatomical collision hitboxes, and real-time spatial coordinate streams.
* **Implementation:**
  - **3D Hand Tracking Points:** Rendered 3-axis orthogonal orbital gyro rings ($r=1.5\text{u}$), central crosshairs, and RGB coordinate axes for Primary Hand (Cyan) and Secondary Hand (Amber) with inter-hand distance guide vector in [`ref/gl_vr/gl_studio.c`](../../ref/gl_vr/gl_studio.c).
  - **Weapon Center of Mass (COM) Engine:** Implemented volumetric weighted centroid integration of all model hitboxes transformed by bone matrices ($\mathbf{COM} = \frac{\sum V_i \mathbf{w}_i}{\sum V_i}$) with Gold orbital rings, crimson gravity reticle, yellow grip-to-COM moment-arm lever vector, and lime-green COM-to-muzzle vector.
  - **Hitbox Visualization (`vr_debug_hand 2`):** 3D wireframe bounding boxes of all `mstudiobbox_t` colored by body group (`hullcolor[group % 8]`).
  - **Real-Time HUD Telemetry:** Lines 0–5 of `Con_NPrintf` streaming continuous Head, Dominant Hand, Offhand, Weapon COM coordinates/angles, and hitbox counts.
  - **Console Snapshot Command (`vr_telemetry`):** Registered in `gl_opengl.c` and declared in `gl_local.h` for instant console dumps.
  - **In-Headset VR Menu (`CMenuVR` Tab 4):** Checkbox `6DoF Hand & Weapon COM Gizmos` and button `Dump 6DoF Telemetry Snapshot`.
* **Status:** 🟢 **Resolved / Implemented** (Verified in 24/24 Monado tests and Quest APK build).
