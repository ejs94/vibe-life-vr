# Gate 0 fixed comparison camera

The Gate 0 captures use a world-space comparison camera instead of the normal
first-person view. The renderer draws the viewmodel as a world entity while the
camera is active, so the camera can orbit the grip or the palm and keep the whole
weapon in frame.

## Camera cvars

| Cvar | Default | Meaning |
|---|---|---|
| `vr_test_camera` | `0` | `0` off, `1` right lateral, `2` top, `3` front, `4` left lateral. |
| `vr_test_camera_distance` | `60` | Orbit distance in world units. |
| `vr_test_camera_fov` | `60` | Vertical field of view in degrees. |
| `vr_test_camera_aim` | `0` | Forward aim offset from the target, in world units. |
| `vr_test_camera_target` | `0` | `0` viewmodel grip, `1` primary palm, `2` free offhand. |

`vr_test_camera_target 1` and `2` use the OpenXR primary/secondary grip pose
and the player turn yaw, matching the standalone hand placement. If the
simulated secondary controller does not expose a grip pose, target `2` falls
back to the free hand entity's world transform instead of the viewmodel, so the
camera still frames the offhand. With `r_drawviewmodel 0` the weapon is hidden
while the standalone hand layer still draws, which is the clean setup for thumb
close-ups.

With `vr_hide_arms 0` the viewmodel already owns both baked hands, so the hand
layer does not draw a floating duplicate. With `vr_hide_arms 2` the standalone
primary hand is deferred until after the weapon is drawn and pinned to the baked
`Bip01 R Hand` position (`vr_hand_grip_lock 1`). The offhand is always free at
the controller; the blocky hand is never used as a foregrip/support replacement.
Support exists only as the baked viewmodel offhand when the weapon has one. Use
mode `2` only as a debug view; mode `1` keeps the baked hand authoritative.

## Test bed map

`scripts/build_testbed_map.py` generates and compiles `testbed_scale` with VHLT:
a 45 m open room, a 1 m floor grid, distance posts at 1/2/5/10/20 m, height bars
at 1/2/3 m, and explicit `light` entities. The compiler writes the BSP to
`out/valve_vr/maps/testbed_scale.bsp` (the local overlay). `out/valve/maps` is a
read-only symlink into the Steam installation and must not receive generated
maps.

The map skips `hlvis`: the dense grid exceeds `MAX_PORTALS_ON_LEAF`, and an open
test room does not need culling. The engine reports `has no visibility`; this is
expected. Set `VHLT_DIR` if the tools are not in the local `JACK/halflife` tree.

`scripts/gate_testbed_hands.cfg` captures baked, free-offhand and unarmed states
in the map. It is run through the normal Monado evidence runner:
`CFG_NAME=gate_testbed_hands.cfg OUTPUT_SUBDIR=gate_testbed ./scripts/test_gate0_hands.sh`.

## Hand inspection cvars

| Cvar | Default | Meaning |
|---|---|---|
| `vr_baked_hand_curling` | `1` | Curling on the baked viewmodel hand: `0` off, `1` current, `2` index finger only. |
| `vr_thumb_curl_axis` | `1` | Standalone thumb axis: `0` legacy local Y, `1` thumb-specific local Z toward the palm. |
| `vr_hand_grip_lock` | `1` | `0` off, `1` snap the standalone palm position to the baked grip bone, `2` also copy its orientation. |
| `vr_hand_pose_source` | `0` | `0` controller/procedural, `1` copy baked viewmodel finger animation. |
| `vr_hand_anim_blend` | `1.0` | Baked finger animation blend weight for the standalone hand. |
| `vr_test_finger_curl` | `0` | Curl amount `0..1` for headless captures. `0` is off; use `vr_finger_curling 0` for a rest-pose capture. |

The crossbow baked hand is already authored around the grip. Curling it
procedurally on top of that pose does not remove the rest-pose claw; use the
comparison captures to separate the baked mesh problem from the runtime curl.

## Evidence

- `out/evidence/gate0c/` contains the fixed-camera crossbow, Glock and MP5
  panels, the hand-region crops and the labeled legend sheets.
- `out/evidence/gate0c_thumb/` contains the standalone Rimrook thumb panels at
  curl 0, 0.5 and 1, plus the legacy local-Y comparison.
- `scripts/make_gate0_legend.py` rebuilds the labeled sheets.
- `scripts/measure_thumb_pose.py` writes the Rimrook thumb samples and the MMOD
  baked thumb angles to `out/evidence/gate0c/`.

Visual approval still requires the engine legend sheets; Blender viewport
renders are diagnostic only.
