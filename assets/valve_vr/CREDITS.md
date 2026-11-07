# Third-Party Asset Credits

The VR asset overlay bundles the following community work. Keep this file in
sync whenever a bundled asset changes.

## models/v_hand.mdl — HEV glove, two hands

* **Source:** Half-Life: VR Mod by Max Makes Mods,
  `art/models/v_hand_hevsuit.mdl` (single right hand, `gordon_glove.bmp`,
  `gordon_glove_Chrome.bmp`, `gordon_sleeve.bmp`).
* **Source URL:** <https://github.com/maxmakesmods/Half-Life-VR>
* **Reference copy in this workspace:**
  `xash3d-vr-ports/Half-Life-VR/art/models/v_hand_hevsuit.mdl`
* **Bundled as:** `models/v_hand.mdl`.
* **Changes made by this project:** the biped torso was dropped, a palm
  landmark bone was added, the third thumb joint was merged into the second,
  the hand was scaled to the canonical 6.4558-unit reach, and the left hand was
  mirrored from the right. Geometry and textures are otherwise unchanged.
  Rebuilt by `scripts/build_hev_twohand_mdl.py`.
* **Why:** it is the HEV glove that matches the gloves baked into the adopted
  Half-Life: VR weapon viewmodels, and it exists for both hands.
* The previous in-project block glove (built from the Rimrook pair by
  `scripts/build_twohand_mdl.py`) is retired as `v_hand.mdl`; keep that script
  only for reference. No third-party mesh other than the Half-Life: VR glove is
  shipped as `v_hand.mdl`.

## Half-Life MMOD — Reanimated Pack

* **Pack:** Half-Life MMOD — Reanimated Pack, V1.9
* **Author / animations / re-model:** `[_-=MTB=-_]`
* **Original authors:** GuNsHiP Mark II (creator of Half-Life: MMod) and Valve
  (original Half-Life models)
* **Source:** <https://gamebanana.com/mods/574664>
* **Source archive:** `vanilla-reanimation-pack_mmod-design__c587f.rar`
  (SHA-256 `bdecc2c6aba79e78e4590f48354bf6a38192e390dc66dafe10da22a58a0ea5b6`)
* **Permission:** the author explicitly allowed this project to use the assets
  with credit (recorded by the project owner). Preserve this credit block and
  the source URL in every redistribution.
* **Bundled scope:** only the 15 `valve_addon/models/v_*.mdl` viewmodels listed
  below. The `bshift_addon`, `gearbox_addon`, world models and sounds are not
  bundled. The alternate `accurate_v_shotgun_reload/v_shotgun.mdl` is not used;
  it differs from the selected shotgun only by removing two pump sound events.
  The untouched `v_9mmar.mdl` remains in the source archive and in
  `out/mmod_import/valve_addon/models/` for provenance; it is not deployed.
  The runtime file is the HLSDK-compatible `models/v_9mmAR.mdl`.
* **Changes made:** the MDLs are used as compiled by the pack author. The VR
  overlay hides the baked HEV hands with `vr_hide_arms 2`, supplies the
  standalone `models/v_hand.mdl` instead, and calibrates grip/muzzle sockets in
  [`models/vr_weapons.json`](models/vr_weapons.json). Grip offsets are derived
  from the runtime `[VR_GRIP_BONE]` telemetry by
  [`scripts/calibrate_weapon_grips.py`](../../scripts/calibrate_weapon_grips.py);
  the reusable capture pass is
  [`scripts/grip_calibrate.cfg`](../../scripts/grip_calibrate.cfg). Do not edit
  the binary MDLs by hand; rebuild from source with
  `scripts/build_pxstudiomdl.sh`.

### MMOD viewmodel audit

The audit reconstructs each model's static `$body` meshes from the decompiled
QC, renders 16 orbit views (azimuth 0–315°, elevation 0/+35/−35°), and reports
welded boundary and non-manifold edge counts. Open barrel mouths, magwells and
detachable magazines are expected; missing receiver, stock or chassis faces are
not. Regenerate the sheets with:

```sh
scripts/mdldec.sh <model.mdl> out/mmod_decompiled/<model>
python3 scripts/render_mdl_360.py --qc out/mmod_decompiled/<model>/<model>.qc \
    --out out/evidence/mmod_360_audit --name <model>
```

| Model | Tris | Boundary edges | Status |
| :--- | ---: | ---: | :--- |
| `v_357.mdl` | 880 | 300 | PASS — body, cylinder and speedloader present |
| `v_9mmAR.mdl` | 698 | 231 | PASS — receiver, magazine and stock present (source file `v_9mmar.mdl` renamed for HLSDK parity) |
| `v_9mmhandgun.mdl` | 726 | 117 | PASS — slide, frame, magazine and silencer body present |
| `v_crossbow.mdl` | 592 | 278 | PASS — limbs, rail, scope, grip and bolt present; no authored attachment |
| `v_crowbar.mdl` | 84 | 8 | PASS — shaft and hooked end present |
| `v_egon.mdl` | 1,796 | 257 | PASS — body, barrel and nozzle present |
| `v_gauss.mdl` | 868 | 210 | PASS — body and long barrel present |
| `v_grenade.mdl` | 743 | 76 | PASS — grenade body and spoon present |
| `v_hgun.mdl` | 599 | 31 | PASS — hivehand body and claws present |
| `v_rpg.mdl` | 470 | 232 | PASS — tube, warhead and grip present |
| `v_satchel.mdl` | 845 | 173 | PASS — charge, detonator and strap present |
| `v_satchel_radio.mdl` | 845 | 173 | PASS — same geometry as `v_satchel.mdl` |
| `v_shotgun.mdl` | 1,209 | 153 | PASS — receiver, barrel, pump and shell present |
| `v_squeak.mdl` | 783 | 27 | PASS — snark body and legs present |
| `v_tripmine.mdl` | 186 | 0 | PASS — mine body and laser emitter present |

Boundary counts above are geometry warnings, not failures: many GoldSrc
viewmodels are intentionally open at the muzzle, ejection port or magazine
well. The orbit sheets are a topology smoke test rendered in the reference
pose; they do not prove that the assembled idle pose is closed or textured.
The textured idle-pose audit is the next gate for this asset set.

`v_9mmar.mdl` is kept as the source name for provenance. The runtime overlay
also ships `v_9mmAR.mdl` because the HLSDK requests that exact case
(`3rdparty/hlsdk-portable/dlls/mp5.cpp`); on case-sensitive Android/Linux the
lowercase file alone would be ignored and the vanilla viewmodel would load.

## Blue Shift VR — Glock viewmodel derivative (W2 base)

* **Mod:** Half-Life: VR Mod — Blue Shift, "Blue Shift VR".
* **Author / maintainer:** Dmitry Shaburov (`DmitryShaburov`), built on
  Max Makes Mods' Half-Life: VR Mod VR code and the TWHL "Blue Shift Updated"
  SDK. Full contributor list in the mod's `README.md`.
* **Source:** <https://github.com/DmitryShaburov/Blue-Shift-VR>
* **Reference copy in this workspace:**
  `xash3d-vr-ports/Blue-Shift-VR/installer/payload/models/v_9mmhandgun.mdl`
  (decompiled working copy: `out/w2_work/bsvr_glock/`, not committed).
* **Lineage:** the mesh is a modified derivative of the MMOD Reanimated Pack
  Glock credited above, not original work by this project.
* **Used for:** the `W2` native Glock base only. The mod's Magnum and crossbow
  score below the MMOD sources on the project's own topology audit and are not
  used.
* **Changes made / planned:** the mesh is imported as authored; this project
  fixes the residual accidental loops, T-junction cracks and non-manifold edges,
  adds the six interaction sockets the physical reload needs, and replaces the
  baked scientist hands with the HEV hands. Tracked in
  [`Documentation/vr/WEAPONS.md`](../../Documentation/vr/WEAPONS.md#w2-base-blue-shift-vr-derivative).
* **Permission:** the maintainer will confirm with the author before release.
  Preserve this block and the source URL in every redistribution.

## Half-Life: VR Mod (SD) — native Glock base

* **Mod:** Half-Life: VR Mod by Max Makes Mods.
* **Source:** <https://github.com/maxmakesmods/Half-Life-VR>
* **Reference copy in this workspace:** `xash3d-vr-ports/Half-Life-VR/art/models/SD/v_9mmhandgun.mdl`
* **Shipped as:** `models/native/v_9mmhandgun.mdl` (W2 native base).
* **Lineage:** MMOD Reanimated Pack Glock, reworked by Max Makes Mods.
* **Why this one:** it ships the Gordon/HEV glove hands, four model-authored
  anchors (`muzzle_pos`, `muzzle_pos2`, `hud_pos`, `hud_pos2`) and ten animation
  sequences, which is exactly the contract the native route consumes.
* **Changes made by this project:** none to the MDL. Only the per-weapon JSON
  profile was corrected (ejection and magwell sockets disabled because
  attachments 2 and 3 are HUD anchors on this model).
