# Rimrook thumb rest re-pose

The standalone Rimrook hand shipped with an extended thumb. The runtime now
curls the thumb around its own local Z axis, but at curl 0 the rest pose still
read as extended.

## Reproducible build

```sh
python3 scripts/repose_rimrook_thumb_smd.py --base 12 --distal 6
python3 scripts/check_hand_asset.py --model out/twohand_thumb_rest/v_hand.mdl
```

The script:

- reads `out/twohand/hand_r.smd` and `hand_l.smd`;
- rotates only `Bip01 R/L Finger0` and `Bip01 R/L Finger01` around their local Z
  rest axis (right negative, left positive);
- leaves every vertex and every other finger untouched;
- writes a new SMD pair, QC and compiled test MDL under
  `out/twohand_thumb_rest/`.

The test MDL is not deployed. The runtime `v_hand.mdl` was restored after the
captures.

## Runtime axis

`vr_thumb_curl_axis 1` uses the thumb-specific local Z axis for the standalone
hands. The legacy local Y axis is no longer the default; it lifted the thumb
away from the palm at full curl.

## Evidence

- `out/evidence/gate0c_thumb/monado_20261024_204953/` — original rest.
- `out/evidence/gate0c_thumb_rest/monado_20261024_221700/` — re-posed rest.
- `out/evidence/gate0c_thumb_rest/legend_thumb_rest_crops.png` — labeled
  comparison at curl 0 / 0.5 / 1.
- `out/evidence/gate0c/thumb_pose_mmod.json` — MMOD baked thumb angles used as
  the full-curl reference.
