# MMOD baked hand as a standalone asset

The baked viewmodel hand and the standalone Rimrook hand have different meshes.
Copying only the baked finger rotations does not reproduce the grip: the MMOD
hand's grip shape is authored in the mesh, while its finger rest rotations are
nearly straight. The reliable way to keep the animation-matched hand is to
extract the baked MMOD mesh and texture as a standalone model.

## Build

```sh
python3 scripts/build_mmod_standalone_hand.py \
    --input out/mmod_import/decompiled/v_crossbow_check/HEV_hands_reference.smd \
    --output out/mmod_standalone

python3 scripts/check_hand_asset.py \
    --model out/mmod_standalone/v_hand.mdl --grip
```

The extractor:

- keeps the weapon-space orientation and puts the wrist at the origin, so the
  standalone entity can use the exact baked `Bip01 R/L Hand` transform;
- splits the right and left triangles into the `rhand` / `lhand` bodygroups;
- merges `UpperArm` weights into `Forearm` and the third thumb segment into
  `Finger01`, producing the 35-bone contract;
- copies `HEV_hands.bmp`, `HEV_chrome.bmp` and `HEV_forearm_Chrome.bmp`.

`check_hand_asset.py --grip` skips the canonical `+X` fingers / `+Z` thumb
orientation checks because this asset is intentionally in weapon space. It
still validates the 35 bones, bodygroups and palm-to-fingertip reach.

## Runtime

For a grip-space extracted hand:

```cfg
vr_hide_arms 2
vr_hands_always_visible 1
vr_hand_grip_lock 2
vr_hand_pose_source 0
vr_finger_curling 0
```

- `vr_hand_grip_lock 2` copies the baked wrist position and orientation.
- `vr_hand_pose_source 0` keeps the extracted grip mesh as authored.
- `vr_hand_pose_source 1` copies the baked finger animation; use it when the
  standalone mesh matches the baked mesh and fire/reload animation must follow.
- `vr_hand_anim_blend` controls the baked/6DoF finger blend.

For a test-only unique model path, set `vr_primary_hand_model` to
`models/v_hand_mmod.mdl`; this avoids ambiguity with the normal `v_hand.mdl`.

## Per-weapon extraction

The hand mesh differs slightly between weapons (the crossbow thumb pose is
different and the bone count is higher). Run the extractor on each weapon's
`HEV_hands_reference.smd` instead of reshaping a shared hand. This is
data-driven: the same script handles `Bip01`, `Xbow biped` and legacy `BoneNN`
viewmodels through the semantic resolver.

## Portability check

```sh
python3 scripts/check_hand_bone_portability.py
```

It scans `valve`, `gearbox`, `bshift` and the `assets/valve_vr/models` overlay.
The overlay models all provide right/left hands and finger chains. Some
expansion originals have hands without finger bones; those need the baked hand
only or the controller-driven fallback.

## Evidence

- `out/evidence/gate2_mmod/legend_mmod_standalone.png`
- `out/evidence/gate2_mmod/monado_20261024_235557/`
- `out/evidence/gate2_mmod_unique/monado_20261024_235819/`
- `out/evidence/gate2/hand_bone_portability.json`

The extracted model is a test artifact under `out/`; it is not deployed.
