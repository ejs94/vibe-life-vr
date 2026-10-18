# 🛠️ Xash3D VR — Modder Integration Architecture & Asset Guide

> **"You have to investigate how to let modders integrate VR into their work, because otherwise it's just yet-another-halflife/cs-vr-port — useless for modders."**  
> — *a1ba (Xash3D FWGS Creator & Maintainer)*

---

## 🎯 1. Executive Summary & Vision

The primary mission of **Xash3D VR** is not merely to be a single-game port of Half-Life 1, but to provide a **universal, robust, extensible VR platform for the entire GoldSrc modding ecosystem**.

A creator developing a total conversion (like *Cry of Fear*, *They Hunger*, *Paranoia*, *Poke646*, *Afraid of Monsters*, *Gunman Chronicles*, or an original standalone title) should be able to deliver a first-class 6DoF Virtual Reality experience **without ever needing to fork or recompile the engine binaries**.

This guide details the complete modder integration architecture:
1. The `<gamedir>_vr` Virtual File System (VFS) Overlay.
2. The 6DoF Model Standard & QC Attachment Conventions.
3. Declarative Weapon Calibration (`vr_weapons.json`).
4. Mod Tier Classifications & Upgrade Paths.
5. Headless Automated Testing Pipeline for Modders.

---

## 📁 2. The `<gamedir>_vr` File System Overlay

### How It Works
Xash3D FWGS features an idiomatic content mount system. In addition to high-definition content (`<gamedir>_hd`) and localization (`<gamedir>_<lang>`), Xash3D VR introduces **`FS_MOUNT_VR`**:

```
               PRIORITY ORDER (Highest to Lowest)
┌─────────────────────────────────────────────────────────────┐
│  1. <gamedir>_vr/     (VR Models, Textures, Shaders, JSON)  │  <-- Highest Priority
├─────────────────────────────────────────────────────────────┤
│  2. <gamedir>_hd/     (High-Definition Textures/Models)     │
├─────────────────────────────────────────────────────────────┤
│  3. <gamedir>_addon/  (Community Addons / Custom Patches)   │
├─────────────────────────────────────────────────────────────┤
│  4. <gamedir>/        (Base Game Directory / Mod Assets)    │  <-- Base Fallback
└─────────────────────────────────────────────────────────────┘
```

### Benefits for Modders
* **Non-Destructive:** Modders never overwrite vanilla or flat-screen assets.
* **Dual-Mode Playability:** A single mod installation can run in flat-screen desktop mode (using `<gamedir>/`) or in 6DoF VR mode (automatically mounting `<gamedir>_vr/` on top).
* **Easy Distribution:** A VR patch for any mod is simply distributed as a `<modname>_vr` folder or zip archive containing only the modified VR models and configs.

---

## 🔫 3. The 6DoF VR Model Specification

Flat 1998 models cut off faces outside the CRT field of view and feature detached floating arm stubs. To make a model "VR-Ready", modders follow these standards:

### 3.1. Attachment Conventions (QC Script Standard)
When compiling viewmodels with `studiomdl`, define the following standardized attachment indices:

| Attachment | Name | Function in Xash3D VR |
| :---: | :--- | :--- |
| **`$attachment 0`** | **Muzzle** | Tip of the gun barrel. Used by `gl_rmain.c` for 3D laser sight emission and by `sv_pmove.c` for server-side hitscan and projectile origin (`pev->vuser1`). |
| **`$attachment 1`** | **Secondary Grip** | Foregrip / handguard. Used by `xr_input.c` for physical two-handed stabilization snapping and proximity calculations. |
| **`$attachment 2`** | **Brass Ejector** | Spent shell casing ejection port in 3D roomspace. |
| **`$attachment 3`** | **Magwell / Cylinder** | Magazine insertion point and collision sphere for manual reloading. |

#### Example QC Syntax:
```qc
$modelname "v_custom_rifle.mdl"
$attachment 0 "barrel"   0.00 18.00 2.20
$attachment 1 "handguard" 0.00  7.50 -1.50
$attachment 2 "receiver"  1.20  3.00  1.80
$attachment 3 "magwell"   0.00 -1.00 -5.00
```

### 3.2. Geometry & Mesh Rules
1. **Closed 360° Geometry:** Model the right side, underside, and back of the gun. The player will examine the weapon from every angle.
2. **Arm/Sleeve Suppression:** If the model includes an arm, assign the arm mesh texture name containing `sleeve`, `forearm`, `cuff`, or `player_arm`. The engine's `vr_hide_arms` CVar will automatically cull the rigid flat arm while preserving the gun in VR.
3. **Budget:** Recommended 1,500 – 6,000 triangles per viewmodel for smooth 90/120 Hz on mobile headsets (Meta Quest 3/3S).

---

## 📄 4. Declarative Weapon Calibration (`vr_weapons.json`)

Modders can calibrate weapon offsets, laser positions, pitch angles, and haptics **without writing a single line of C/C++ code**.

Place `vr_weapons.json` inside your `<gamedir>_vr/models/` folder:

```json
{
  "version": 1,
  "weapons": {
    "v_custom_shotgun.mdl": {
      "name": "Custom 12-Gauge Pump Shotgun",
      "type": "hitscan",
      "muzzle_attachment": 0,
      "grip_attachment": 1,
      "pitch_adjust": -4.0,
      "two_handed": true,
      "two_hand_min_dist": 0.12,
      "two_hand_max_dist": 0.55,
      "spread_reduction_two_handed": 0.50,
      "haptics": {
        "fire_amplitude": 1.0,
        "fire_duration_ms": 110,
        "pump_amplitude": 0.6,
        "pump_duration_ms": 50
      }
    }
  }
}
```

---

## 🏆 5. Mod Compatibility Tiers

| Tier | Name | Modder Work Required | How It Runs in Xash3D VR |
| :---: | :--- | :--- | :--- |
| 🥇 **Gold** | **Native VR Total Conversion** | Custom `<mod>_vr/` folder, VR-rigged models with attachments, and optional custom client/server DLLs using the Xash3D VR SDK. | **100% Native 6DoF Immersion:** Physical laser sights, two-handed grip stabilization, haptics, gesture flashlight, and manual reload. |
| 🥈 **Silver** | **Calibrated Profile** | Drop in existing closed-source mod DLLs + a `<mod>_vr/models/vr_weapons.json` calibration file. | **Automatic 6DoF Decoupling:** Engine automatically maps `pev->vuser1` for ballistics, applies pitch adjustments, and locks viewmodels to controllers. |
| 🥉 **Bronze** | **Universal Fallback** | Zero work required. Pure vanilla legacy mod. | **Virtual Cinema / Decoupled Fallback:** Runs in floating virtual 3D room with decoupled head gaze and controller aiming. |

---

## 🧪 6. Testing Custom Mod Weapons Headless

Modders do not need to put on a headset every time they compile a model. We provide automated test harnesses using simulated OpenXR drivers:

```bash
# 1. Test custom mod viewmodel alignment and laser sight emission
./xash3d -dev 1 -ref gl_vr -game mymod +vr_test_hands 1 +map test_map

# 2. Capture a high-res stereo eye buffer dump to verify the model in 3D
vr_dumpeye mymod_weapon_test.ppm
```

---

## 📦 7. Reference Implementation Assets

A complete reference pack is available in the repository under [`assets/valve_vr/`](../../assets/valve_vr/):
* [`gameinfo.txt`](../../assets/valve_vr/gameinfo.txt) — Game overlay declaration.
* [`models/vr_weapons.json`](../../assets/valve_vr/models/vr_weapons.json) — Complete manifest for all 16 Half-Life weapons.
* [`templates/weapon_template.qc`](../../assets/valve_vr/templates/weapon_template.qc) — Reusable QC script with attachment points.
* [`templates/VR_RIG_GUIDE.md`](../../assets/valve_vr/templates/VR_RIG_GUIDE.md) — 3D modeling and rigging guide.
