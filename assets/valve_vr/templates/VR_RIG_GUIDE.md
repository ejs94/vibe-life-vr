# 📐 Xash3D VR — 3D Model Rigging & Authoring Standards for Modders

This technical guide specifies how to author, adapt, or re-rig 3D weapon and player models for **Xash3D VR** in GoldSrc format (`StudioMDL v10`).

---

## 🔍 1. Key Differences Between Flat GoldSrc and 6DoF VR Models

| Feature | 1998 Flat Viewmodels | Xash3D VR 6DoF Viewmodels |
| :--- | :--- | :--- |
| **Visible Geometry** | Only front/left sides modeled; backfaces culled to save CRT rendering budget. | **Full 360° Closed Meshes:** Modeled right-side, underside, rear receiver, and barrel interior. |
| **Arms & Hands** | Rigid flat arm shell attached to weapon root, cut off at forearm. | **Decoupled or Suppressed:** Hands either animated independently or sleeves removed via texture naming (`sleeve`, `forearm`, `cuff`, `player_arm`). |
| **Muzzle Origin** | Screen center or rough eye-level forward projection. | **Physical `$attachment 0`:** Exact tip of the 3D barrel; drives laser beam and server-side hitscan traces. |
| **Secondary Grip** | Baked 2D animation only. | **Physical `$attachment 1`:** Grip zone for off-hand controller stabilization in 3D space. |
| **Magazines** | Baked into weapon mesh or hidden under floor at $Z < -15$. | **Independent submodel / bone:** Detachable magazine for physical drops and manual reloading. |

---

## 🛠️ 2. Step-by-Step Pipeline for Adapting Existing Models

### Step 1: Decompile with Crowbar
1. Open [Crowbar](https://github.com/ZeqMacaw/Crowbar) (GoldSrc mode).
2. Decompile your target `v_weapon.mdl` into `.smd` reference and animation meshes + `.qc` control file.

### Step 2: Blender / 3D DCC Modeling
1. **Cap Missing Faces:**
   - In 1998 models, inspect the right side and rear face.
   - Bridge open edge loops and add backface polygons to close all holes.
   - Keep total polygon count between **1,500 and 6,000 triangles** (optimal for Meta Quest mobile TBDR GPUs).
2. **Assign UVs & 8-Bit Palette:**
   - GoldSrc requires standard 8-bit paletted textures (256 colors maximum) or 24-bit textures depending on texture loader flags.
   - Textures must have dimensions that are multiples of 16 (e.g., 256x256, 512x512).
3. **Isolate Bones & Attachments:**
   - Place a bone at the tip of the barrel for `$attachment 0`.
   - Place a bone at the handguard/foregrip for `$attachment 1`.
   - Ensure the root bone origin aligns with the grip handle where the controller rests.

### Step 3: Configure the QC Script
Copy and adapt [weapon_template.qc](weapon_template.qc):
```qc
$attachment 0 "barrel_tip" 0.00 12.50 1.80
$attachment 1 "foregrip"   0.00  5.00 -1.00
$attachment 2 "ejection"   1.10  2.00  1.50
$attachment 3 "magwell"    0.00 -1.00 -4.00
```

### Step 4: Compile with GoldSrc StudioMDL
```bash
studiomdl -k my_weapon.qc
```
Place the compiled `v_my_weapon.mdl` into:
`<your_mod>_vr/models/v_my_weapon.mdl`

---

## 🎮 3. Declarative Fallback Calibration (`vr_weapons.json`)

If you cannot recompile `.mdl` files or want quick adjustments:
1. Place a `vr_weapons.json` in your `<mod>_vr/models/` or `<mod>/models/` directory.
2. Define the weapon name, pitch adjustment, and fallback offsets.
3. The engine automatically parses and applies these offsets at runtime!
