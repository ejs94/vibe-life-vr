# 🧩 Xash3D VR — Mod Compatibility Architecture & Mod Manager Specification

> **Permanent Architectural Reference Document for OpenCode & Future Agents**
> **Last Updated:** October 2026
> **Scope:** Defines the 3-Tier Mod Compatibility System, Mod Manager UX (Quest & PCVR), Storage Cleanup Protocols, and GitHub Catalog Integration.

---

## 🎯 1. Executive Summary & Design Principles

In the GoldSrc engine ecosystem (Half-Life 1), there is a fundamental architectural tension between:
1. **Modern Physical VR Mechanics (HL2VR / Alyx style):** Manual reloading (inserting clips, racking slides), physical world interactions, two-handed IK.
2. **Universal Mod Compatibility:** Running 20+ years of legacy mods (*They Hunger*, *Cry of Fear*, *Opposing Force*, *Counter-Strike 1.6*, etc.) whose compiled game libraries (`client.dll` / `server.dll`) are closed-source or unmaintained.

To solve this without sacrificing mod access, Xash3D VR employs **Progressive Enhancement (Graceful Degradation)** across **Three Compatibility Tiers**:
* **GOLD (Native VR):** Full SDK-level integration.
* **SILVER (Calibrated Profile):** Unmodified mods with JSON calibration profiles.
* **BRONZE (Universal Fallback):** Unmodified legacy mods running on engine-level emulation.

---

## 🏆 2. The 3 Compatibility Tiers

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Xash3D VR Engine Core                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Negotiation at mod load time
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
    ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
    │   BRONZE    │          │   SILVER    │          │    GOLD     │
    │  Universal  │          │ Calibrated  │          │   Native    │
    │  Fallback   │          │   Profile   │          │     VR      │
    └─────────────┘          └─────────────┘          └─────────────┘
      Legacy mods              Mods with                Half-Life 1
      (1998-2005)           vr_weapons.json            Base Game SDK
```

### 🥉 BRONZE: Universal Fallback (Zero-Effort Legacy Emulation)
* **Target Audience:** Unmodified legacy mods, singleplayer map packs, closed-source conversions (*They Hunger*, *Afraid of Monsters*, *Paranoia*).
* **Technical Characteristics:**
  - Game DLLs (`client.so` and `server.so`) are completely untouched.
  - The engine redirects input through the standard `usercmd_t` structure.
  - **Aiming:** 6DoF hand aim driven by OpenXR primary hand pose.
  - **Controls:** VR layout (Right A = Jump, Right B = Reload, primary grip + trigger = Alt-Fire, off-hand trigger = Use near objects, Stick Clicks = Crouch/Sprint).
  - **Reload:** Classic button reload (pressing Right B plays the authored sequence in 3D).
  - **Viewmodel:** 2D flat-screen artifacts (viewmodel camera bobbing, screen punchangle) are suppressed by the engine renderer (`ref_gl_vr`).
  - **Interactions:** Touch-to-use gesture and temple flashlight gesture work universally.

### 🥈 SILVER: Calibrated Profile (Community JSON Metapack)
* **Target Audience:** Unmodified mods that introduce custom weapon models with non-standard grips, unusual barrel lengths, or melee weapons (*Counter-Strike 1.6*, *Opposing Force*, *Gunman Chronicles*).
* **Technical Characteristics:**
  - Game DLLs remain 100% untouched.
  - A declarative JSON configuration file (`vr_weapons.json` placed inside `<gamedir>_vr/models/`) defines weapon alignment parameters.
  - **Metadata Fields:**
    - `muzzle_offset`: Exact 3D point where muzzle flash, laser sight, and bullet traces originate.
    - `grip_angle` & `grip_offset`: Corrects wrist angle for non-standard pistol grips.
    - `twohand_point`: Specifies where the secondary off-hand grasps the front barrel/stock for stabilization.
    - `haptic_profile`: Custom vibration patterns (e.g. chainsaw, heavy wrench, dual barettas).
  - **No C++ compilation needed:** Any community player can create and share these profiles via simple text edits.

### 🥇 GOLD: Native VR (Full SDK Integration)
* **Target Audience:** The base **Half-Life 1 game** (`3rdparty/hlsdk-portable`) and select high-profile mods with open source access.
* **Technical Characteristics:**
  - Client and Server code in HLSDK directly interface with VR APIs.
  - **Physical Manual Reload:** Dedicated 6DoF collision sockets for magazines, slides, and chambering.
  - **Physical Ladders & Props:** True grab mechanics for climbing and physics manipulation.
  - **Diegetic UI:** Weapon ammo counters integrated into weapon displays or player wrist watches.

### 🛡️ 2.4. Why Custom Mod SDKs Do Not Conflict (The Isolation & Non-Intrusive Contract)

A common concern when porting a 25-year-old engine to VR is: *"If 20 different mods have their own heavily customized SDKs (Counter-Strike, Cry of Fear, Opposing Force, Natural Selection), how do we support them without massive code conflicts?"*

The system prevents all conflicts through three architectural guarantees:

1. **Strict Directory & Memory Isolation (The GoldSrc Sandbox):**
   - In GoldSrc, each mod lives in its own isolated directory (`valve/`, `cstrike/`, `gearbox/`, `hunger/`).
   - When launching the game (`-game <gamedir>`), the engine dynamically loads **only that mod's compiled binaries** (`<gamedir>/dlls/` and `<gamedir>/cl_dlls/`).
   - Different mods **never share memory, global state, or SDK symbols simultaneously**. There is zero risk of *Counter-Strike* logic interfering with *They Hunger*.

2. **Immutable Engine-to-DLL ABI (`enginefuncs_t` & `DLL_FUNCTIONS`):**
   - Every single GoldSrc mod in history communicates with the engine through the exact same C ABI struct tables.
   - For **Bronze** and **Silver** tiers, **custom mod DLLs are 100% untouched**. The engine injects VR support externally via OpenXR 6DoF input into `usercmd_t`, stereo camera projection in `ref_gl_vr`, and universal gesture hooks. A closed-source 2002 mod has no idea it is running in VR, yet works smoothly.

3. **Per-Mod Dedicated SDKs for Gold Tier (No Monolithic SDK Bloat):**
   - We **never** merge 50 mods into one single monolithic SDK codebase.
   - The base Half-Life 1 SDK (`3rdparty/hlsdk-portable`) serves exclusively as the **GOLD Tier Benchmark**.
   - If a community mod is upgraded to Gold Tier (e.g., an open-source port of *Opposing Force*), it maintains its own dedicated repository/subproject compiling into its own `gearbox/` folder. It never touches or pollutes the base game SDK.

---

## 📜 3. Mod Manifest Specification (`vr_mods.json`)

The online compatibility catalog and local mod profiles follow this schema:

```json
{
  "$schema": "https://raw.githubusercontent.com/.../vr_mods_schema.json",
  "version": 1,
  "catalog": [
    {
      "id": "valve",
      "title": "Half-Life",
      "tier": "gold",
      "status": "Native VR",
      "vibe_code": false,
      "developer": "Valve / Xash3D VR Team",
      "download_url": "",
      "size_mb": 450.0,
      "banner_url": "banners/valve.png",
      "features": [
        "6dof_weapon_aim",
        "hl2vr_controller_layout",
        "two_handed_stabilization",
        "button_reload",
        "physical_grenade_momentum",
        "head_flashlight_gesture",
        "touch_world_interaction",
        "laser_sight",
        "proximity_optical_scope",
        "haptic_feedback"
      ],
      "extended_features": [
        "backpack_crowbar_gesture"
      ]
    },
    {
      "id": "gearbox",
      "title": "Half-Life: Opposing Force",
      "tier": "silver",
      "status": "Calibrated Profile",
      "vibe_code": true,
      "developer": "Gearbox Software",
      "download_url": "https://.../gearbox_vr.zip",
      "size_mb": 780.0,
      "banner_url": "banners/gearbox.png",
      "features": [
        "6dof_weapon_aim",
        "hl2vr_controller_layout",
        "two_handed_stabilization",
        "button_reload",
        "head_flashlight_gesture",
        "laser_sight",
        "haptic_feedback"
      ],
      "extended_features": [
        "pipewrench_physical_melee_swing",
        "displacer_cannon_custom_haptics",
        "nightvision_head_gesture"
      ]
    },
    {
      "id": "hunger",
      "title": "They Hunger",
      "tier": "bronze",
      "status": "Universal Fallback",
      "vibe_code": null,
      "developer": "Black Widow Games",
      "download_url": "https://.../they_hunger.zip",
      "size_mb": 420.0,
      "banner_url": "banners/they_hunger.png",
      "features": [
        "6dof_weapon_aim",
        "hl2vr_controller_layout",
        "button_reload",
        "head_flashlight_gesture"
      ],
      "extended_features": [
        "classic_survival_horror_pacing"
      ]
    }
  ]
}
```

### 🏷️ 3.1. Manifest Schema & TypeScript Typing

```typescript
export type ModTier = "gold" | "silver" | "bronze";

export type ModStatus = 
  | "Native VR"           // Gold: SDK-level C++ VR integration
  | "Calibrated Profile"  // Silver: Original DLL with vr_weapons.json
  | "Universal Fallback"; // Bronze: Original DLL with engine emulation

/**
 * Standard VR Features standardized directly on Half-Life 1 Native VR benchmark.
 */
export type StandardVRFeature =
  | "6dof_weapon_aim"            // True 6DoF decoupled controller aiming
  | "hl2vr_controller_layout"    // HL2:VR bindings (A=Reload, B=AltFire, X=Jump, Y=Use)
  | "two_handed_stabilization"   // Secondary hand grip gives 50% tighter spread (vuser4)
  | "native_manual_reload"       // Physical magazine insertion & slide racking
  | "button_reload"              // Classic button reload playing 3D authored animation
  | "physical_grenade_momentum"  // Physical toss velocity calculated from hand inertia (vuser3)
  | "head_flashlight_gesture"    // Head temple tap gesture toggles flashlight
  | "touch_world_interaction"    // Physical hand touch to press buttons and open doors
  | "haptic_feedback"            // Dynamic haptics scaled to caliber (9mm, .357, Buckshot, etc.)
  | "laser_sight"                // 3D laser projection aligned with physical muzzle
  | "proximity_optical_scope"    // Proximity eye zoom when bringing scope near headset
  | "diegetic_hud";              // In-world wrist watch or weapon ammo counter

export interface ModManifestEntry {
  /** Unique directory identifier (e.g. 'valve', 'gearbox', 'cstrike', 'hunger') */
  id: string;

  /** Display title */
  title: string;

  /** Compatibility tier: strictly 'gold', 'silver', or 'bronze' */
  tier: ModTier;

  /** Status description: strictly 'Native VR', 'Calibrated Profile', or 'Universal Fallback' */
  status: ModStatus;

  /**
   * Optional vibe-coding flag:
   * true = Adapted or calibrated with AI-assisted / vibe coding
   * false = Hand-coded / verified manually
   * null = Unknown or legacy mod
   */
  vibe_code: boolean | null;

  developer: string;
  download_url: string;
  size_mb: number;
  banner_url: string;

  /** Standard VR features supported by this mod */
  features: StandardVRFeature[];

  /**
   * Dedicated, mod-specific custom extended features (free-form strings).
   * Used for unique weapons, mechanics, or gestures not part of the standard set.
   */
  extended_features: string[];
}
```

---

## 🔄 4. Mod Switching Architecture: Quest vs. PCVR

Because GoldSrc DLLs allocate static memory, changing mods requires restarting the engine instance (`-game <gamedir>`).

### A) Meta Quest Standalone (Horizon OS)
* **Primary Interface:** The **Android 2D Launcher** (`su.xash.engine`) in the Horizon OS library panel.
* **Why:** Android strictly regulates process lifecycles. Launching games via the 2D panel enables touch typing, background downloads, clean activity intents, and rock-solid stability.
* **In-Game Switching:** If the player selects "Change Mod" from the in-headset 3D menu while playing, the engine fires a JNI call to `XashActivity`, which cleanly closes the current session and restarts the activity with the target game directory.

### B) Desktop PCVR (Linux / Windows)
* **Primary Interface:** **In-Headset 3D VR Custom Games Menu** (`3rdparty/mainui/menus/VR.cpp`).
* **Why:** In PCVR, `execv` allows an in-place soft restart of the process with `-game <gamedir>`. The OpenXR compositor session remains alive, allowing players to point with the laser and switch mods within 2 seconds without ever removing the headset.

---

## 🧹 5. Storage Management & Clean Mods Protocols

Quest headsets (64 GB / 128 GB) have limited capacity. The Mod Manager implements three automated cleaning mechanisms:

1. **Clean Mod Uninstallation:**
   - Deletes `/sdcard/xash/<gamedir>/`.
   - **Protection Lock:** The base directory (`/sdcard/xash/valve/`) is **hard-locked** against deletion to prevent bricking the game.
   - **Save Backup:** Prompts to preserve light `.sav` files in `/sdcard/xash/backups/saves/<gamedir>/`.
2. **Download Cache Purge:**
   - Auto-deletes temporary `.zip` files downloaded from GameBanana / ModDB once uncompressed into the target folder.
3. **Multiplayer Download Purge:**
   - Scans and deletes temporary server-downloaded assets (`tempdecal.wad`, non-campaign `.bsp` files, downloaded sounds and player models) without deleting core mod content.

---

## 🌐 6. Community Catalog & Downloader Pipeline

* **GameBanana:** Direct querying via official REST API (`https://gamebanana.com/apiv11/...`).
* **ModDB:** Automated Python scraper running weekly via **GitHub Actions** (100% free hosting), compiling direct download mirrors into `vr_mods.json`.
* **Zero-Cloudflare Guarantee:** By pre-resolving mirrors via GitHub Actions into a static JSON catalog, the Quest 3 never has to scrape HTML or solve captchas.
