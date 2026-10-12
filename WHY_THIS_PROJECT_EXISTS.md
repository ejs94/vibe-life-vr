# 🌌 Xash3D VR: Motivation & Architecture Goals
> **Building on Team Beef's Foundations: A Clean OpenXR Port for the Modern Xash3D FWGS Engine**

---

## 🎯 1. Vision & Purpose

The **Xash3D VR** project is deeply inspired by the groundbreaking work of **Team Beef** (*Dr. Beef, BaggyG, Bummser*), whose *Lambda1VR* port proved that classic Half-Life (1998) could deliver an extraordinary Virtual Reality experience on standalone hardware. Their work established the gameplay benchmarks and VR interaction standards that define how Half-Life feels in VR today.

While *Lambda1VR* was originally built for the first Oculus Quest in 2019 using the legacy *VrApi* and engine modifications tailored specifically to that era, modern VR runtimes and the Xash3D FWGS engine have both evolved substantially:

1. **Khronos OpenXR Standard:** Modern headsets (Meta Quest, Pico) and desktop PCVR runtimes (Monado, WiVRn, SteamVR) now standardize on the official Khronos OpenXR 1.0/1.1 specification.
2. **Current Xash3D FWGS Compatibility:** Keeping the engine codebase clean and closely aligned with upstream [FWGS/xash3d-fwgs](https://github.com/FWGS/xash3d-fwgs) ensures maximum compatibility with existing GoldSrc mods, multiplayer crossplay, and modern rendering backends.
3. **Unified Tri-Platform Target:** Providing a single C99 codebase that runs smoothly on **Desktop PCVR**, **Meta Quest Standalone**, and preserves standard **Flat (2D)** mobile and desktop play.

### 💡 The Core Goal
To develop a clean, modern implementation **strongly inspired by Team Beef's proven VR design solutions**, while rewriting key subsystems to adhere strictly to the Khronos OpenXR specification and the latest Xash3D FWGS architecture. This achieves:
- **Maximum Mod & Expansion Compatibility:** Out-of-the-box support for *Opposing Force*, *Blue Shift*, and classic single-player total conversions.
- **Crossplay:** Seamless multiplayer interoperability between VR and Flat players across PC and standalone devices.
- **Direct Ref API Rendering:** Rendering directly through the engine's modular `ref_gl_vr` backend rather than external translation layers.

---

## 🤝 2. Technical Comparison & Architectural Approach

| Architectural Domain | Team Beef (*Lambda1VR*) | Xash3D VR (Current Implementation) | Rationale & Objective |
| :--- | :--- | :--- | :--- |
| **VR API Standard** | VrApi baseline; custom OpenXR bridge | **Khronos OpenXR 1.0/1.1 (C99)** | Canonical industry standard supported across Quest, Pico, and PCVR runtimes |
| **Platform Target** | Android (Oculus Quest) | **Desktop PCVR & Quest Standalone** | Shared codebase running on Linux (Monado/WiVRn/SteamVR) and Android |
| **Engine Integration** | Dedicated Quest fork with `OVR_MODE` | **Modular `engine/platform/openxr/`** | Minimizes diff against upstream FWGS to preserve mod compatibility and crossplay |
| **Renderer Pipeline** | `gl4es` OpenGL 1.4 to GLES translation | **Native `ref_gl_vr` (GLES 3.x / OpenGL)** | Direct engine renderer for optimal frame pacing and lowest latency |
| **Android Lifecycle** | Custom native `SurfaceView` | **`XashActivity` (`SDLActivity` subclass)** | Reuses FWGS touch UI, mod launchers, and Android lifecycle with VR focus fixes |
| **Gameplay Mechanics** | 6DoF Aim, Flashlight, Two-Handing, Gestures | **Faithful recreation of Team Beef's mechanics** | Preserves the gold-standard gameplay experience pioneered by Team Beef |

---

## ✨ 3. Distinctive Technical Features & Innovations

### 🌐 3.1. Unified Multi-Platform Codebase
- **Zero JNI in the Core:** All OpenXR interactions (`xrCreateInstance`, `xrCreateSession`, `xrCreateSwapchain`, `xrSyncActions`) are written in native standard C without touching the Java VM.
- **Instant Portability:** A developer on Linux can iterate on PCVR in milliseconds using `LD_LIBRARY_PATH=. ./xash3d -ref gl_vr +map c1a0` and deploy the identical codebase to an Android APK for Meta Quest Standalone.

### 👓 3.2. True 6DoF Optical Frustum & Hardware VSync
- **Asymmetric Lens Frustum:** Replaces the static 90° planar projection with native per-eye field-of-view tangents queried via `XR_GetEyeFrustum`. This eliminates distortion across Fresnel and Pancake optical elements.
- **Hardware-Timed Frame Pacing:** Renders in strict synchronization with headset displays (`xrWaitFrame`), matching physical refresh rates (72Hz, 90Hz, or 120Hz).

### 🔫 3.3. True 6DoF Decoupled Weapons
- Weapon viewmodels are completely detached from the player's head and attached directly to the dominant controller's 6DoF aim pose in `gl_studio.c`.
- Players can blind-fire around corners, look through iron sights naturally, and aim independently of their gaze.

### 🔦 3.4. Independent Off-Hand Flashlight (Alyx Style)
- The flashlight is no longer strapped to Gordon Freeman's forehead. It is cast directly from the **non-dominant left hand** in `cl_tent.c`, allowing players to illuminate dark corners while aiming their weapon in another direction.

### 🎯 3.5. Two-Handed Weapon Stabiliser
- Bringing the off-hand within 22cm of the primary hand automatically activates two-handed aiming. The weapon barrel aligns along the vector connecting both hands, providing rock-solid stability for long-range shots with the .357 Magnum and Crossbow.

### 🚪 3.6. Natural Interaction ("Use Gesture")
- Extending either hand forward toward buttons, switches, or doors automatically triggers the `+use` command. Players can interact organically with the environment without hunting for controller face buttons.

### 🎒 3.7. Over-the-Shoulder Backpack Crowbar
- Reaching behind the shoulder with the dominant hand and pulling the trigger immediately equips the iconic Crowbar (`slot1`).
- **Anti-Frustration Philosophy:** Game saving and loading are strictly managed through the native menus (Menu -> Save/Load), preventing accidental quick-saves during intense combat.

### 🕹️ 3.8. Hardware Anti-Drift Deadzone
- Built-in engine-level radial deadzone (`0.15`) on locomotion and turn sticks, preventing unintended movement caused by potentiometer wear.

---

## 🤝 4. Seamless Compatibility with the Official FWGS Ecosystem

To ensure longevity, moddability, and deep alignment with modern GoldSrc engine standards, **Xash3D VR is architected for 100% mutual compatibility with core FWGS (Flying With Gauss) initiatives and services**:

### 🖼️ 4.1. MainUI C++ ([FWGS/mainui_cpp](https://github.com/FWGS/mainui_cpp))
- **Dedicated VR In-Game Settings Menu:** Rather than requiring players to tweak console variables via text commands, `mainui_cpp` provides the framework for an in-headset graphical VR configuration tab (comfort presets, snap turn angles, smooth turn speed, laser sight toggles, and height calibration).
- **3D Laser Pointer Virtual Cursor:** By intercepting mouse hover and click events through normalized virtual coordinates, the weapon's physical laser sight functions as a natural point-and-click pointer on the floating 3D Quad UI canvas (`XrCompositionLayerQuad`).
- **High-DPI TrueType Font Rendering:** Replaces legacy 1998 bitmap fonts with vector-rendered text (powered by *FreeType* and *stb_truetype*), delivering razor-sharp text legibility on high-resolution VR displays.

### 📟 4.2. Xash3D MainTUI ([numas13/xash3d-maintui](https://github.com/numas13/xash3d-maintui))
- **Headless VR Co-op & Multiplayer Dedicated Servers:** Powered by Rust and *Ratatui*, this text-based terminal interface allows hosting and managing Half-Life VR co-op and deathmatch sessions from a headless Linux server with zero GPU overhead.
- **Live Terminal Telemetry for Developers:** Provides a companion diagnostic dashboard on a secondary monitor displaying live per-eye framerates, controller tracking states, and network stream latency.

### ⚙️ 4.3. HLSDK-Portable ([FWGS/hlsdk-portable](https://github.com/FWGS/hlsdk-portable))
- **Muzzle-Centric Ballistics & Raycasting:** Bridges controller aim poses directly into server-side gameplay libraries (`client.so` and `server.so`), ensuring bullets, Tau Cannon beams, and RPG rockets physically spawn from the weapon's barrel rather than the camera center.
- **Native GoldSrc Expansion & Mod Support:** Guarantees out-of-the-box compatibility with classic expansions and single-player total conversions (*Half-Life: Opposing Force*, *Half-Life: Blue Shift*, *They Hunger*, and *Afraid of Monsters*).

### 💣 4.4. CS16Client ([Velaron/cs16-client](https://github.com/Velaron/cs16-client))
- **Future VR Tactical Shooter Pipeline:** Because CS16Client is built directly upon the FWGS engine architecture, our OpenXR core acts as a turnkey foundation to bring classic Counter-Strike 1.6 into full Virtual Reality with physical weapon handling.

### 🌐 4.5. FWGS Master Server Infrastructure ([xash.su](https://xash.su/#services))
- **Unified Global Server Browser:** Full compatibility with the official FWGS master server directory, enabling cross-play multiplayer matches connecting PCVR players, Meta Quest Standalone users, and traditional desktop PC gamers.

---

## 🗺️ 5. Feature Matrix & Evolving Roadmap

The project is structured into verified phases, where each milestone requires empirical test validation on both Desktop PCVR and Meta Quest Standalone:

- [ ] **Phase 01 (ACTIVE): OpenXR Core Foundation & Dual-Platform Bring-Up** (OpenXR loader init, graphics bindings, session lifecycle, swapchains, paced frame loop)
- [ ] **Phase 02: Stereo Rendering, Asymmetric Frustum & 6DoF Head Tracking** (`ref_gl_vr`, lens geometry, head pose)
- [ ] **Phase 03: Universal Action Sets, Controller Poses & Locomotion** (Quest Touch & Valve Index, analog sticks, buttons)
- [ ] **Phase 04: 6DoF Weapon Decoupling & Off-Hand Flashlight** (Gaze decoupling, independent flashlight, 2-hand stabilizer)
- [ ] **Phase 05: In-Headset Spatial UI, Laser Pointer & VR Options Menu** (Floating quad HUD, virtual mouse cursor, MainUI VR menu)
- [ ] **Phase 06: Server-Side Ballistics, Momentum Physics & Haptics** (HLSDK-Portable muzzle raycasting, physical throw velocity, multi-channel haptics)
- [ ] **Phase 07: Immersive Presence, 3D Spatial Audio & World Mechanics** (Articulated HEV hands, OpenAL HRTF, room-scale crouching, ladders)
- [ ] **Phase 08: Official Expansions & Total Conversions Support** (Opposing Force, Blue Shift, classic GoldSrc mods)

---

## 📜 6. Document Revision History

- **2026-10-11:** Realigned project roadmap back to Phase 01 (OpenXR Runtime Foundation & Dual-Platform Bring-Up). Codified mandatory Dual-Platform Verification Gate requiring empirical testing on both Linux PCVR and Meta Quest Standalone for all deliverables.
- **2026-10-10:** Integrated comprehensive roadmap for 100% compatibility with official FWGS ecosystem tools: MainUI C++, Xash3D MainTUI, HLSDK-Portable, and CS16Client.
- **2026-10-10:** Initial release of the Foundational Manifesto. Consolidated architectural differences, design philosophy, and technical innovations comparing Xash3D VR to Lambda1VR.
