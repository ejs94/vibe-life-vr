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
  [`scripts/build_twohand_mdl.py`](../scripts/build_twohand_mdl.py) for the
  exact, reproducible transformation and
  [`scripts/build_pxstudiomdl.sh`](../scripts/build_pxstudiomdl.sh) for the
  native compiler build, plus section 2.8.2 of
  [`Documentation/vr/ENGINEERING_NOTEBOOK.md`](../Documentation/vr/ENGINEERING_NOTEBOOK.md)
  for the rationale.

### Inner glove liner (2026-10-22)

* Added a duplicate, inward-offset shell for every glove/sleeve triangle with
  the dark `glove_inner.bmp` material, so the inside of the glove reads black
  through the wrist opening. The hand entities render two-sided (`GL_Cull
  GL_NONE`) so the liner is visible from inside.
* Reproducible with
  [`scripts/add_hand_inner_liner.py`](../scripts/add_hand_inner_liner.py).

## Half-Life MMOD — Reanimated Pack (referenced, not bundled)

* **Author:** the Half-Life: MMod Reanimated Pack author (permission granted to
  this project with credit).
* **Source:** <https://gamebanana.com/mods/574664>
* **Use:** reference for VR-friendly weapon animations and fixed 360 weapon
  models. No MMOD assets are bundled in this overlay; if any are integrated
  later, this section and the exact files must be updated.
