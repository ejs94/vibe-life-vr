# Third-Party Asset Credits

The VR asset overlay bundles the following community work. Keep this file in
sync whenever a bundled asset changes.

## models/v_hand.mdl — "HEV Arms That Don't Suck"

* **Author:** Rimrook
* **Extra credit:** DiamondD (sleeve texture)
* **License:** Public Domain. The original release states
  "TERMS OF USAGE: i don't care", which grants unrestricted use, modification
  and redistribution.
* **Source archive:** `hev_arms_by_rimrook.zip`
  (MD5 `3f0a47d9a8cf8613389f11cf21d107a8`)
* **Changes made:** the source hand pair is kept as **both hands in one
  `models/v_hand.mdl`**, arranged as two bodygroups (`rhand` / `lhand`, each with
  a `blank` variant) so the engine can select the anatomical hand per
  controller without runtime mirroring. Both chains use the Valve convention
  (`Bip01 R/L Hand`, `Bip01 R/L Finger0..42`); the model is rescaled to the
  native GoldSrc hand size, recentered on the palm (controller grip), and each
  hand gets a mirrored pitch so the palms face inward and the thumbs point up
  (a natural controller-grip pose). See
  [`scripts/build_twohand_mdl.py`](../../scripts/build_twohand_mdl.py) for the
  exact, reproducible transformation and
  [`scripts/build_pxstudiomdl.sh`](../../scripts/build_pxstudiomdl.sh) for the
  native compiler build, plus section 2.8.2 of
  [`Documentation/vr/ENGINEERING_NOTEBOOK.md`](../../Documentation/vr/ENGINEERING_NOTEBOOK.md)
  for the rationale.

### Inner glove liner (2026-10-22)

* Added a duplicate, inward-offset shell for every glove/sleeve triangle with
  the dark `glove_inner.bmp` material, so the inside of the glove reads black
  through the wrist opening. The hand entities render two-sided (`GL_Cull
  GL_NONE`) so the liner is visible from inside.
* Reproducible with
  [`scripts/add_hand_inner_liner.py`](../../scripts/add_hand_inner_liner.py).

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
| `v_9mmar.mdl` | 698 | 231 | PASS — receiver, magazine and stock present |
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
well. The pass verdict comes from the orbit sheets plus the in-engine check.
