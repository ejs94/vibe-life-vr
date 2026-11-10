# Weapons

This page is the contract for the VR-native weapon path. The legacy path remains
available and must not be broken.

## Status

| Stage | Result |
|---|---|
| W0 native route + legacy fallback | PASS |
| W1 coordinate calibration | **PASS — human approved 2026-11-01** |
| Native Glock mesh | **SHIPPED — Half-Life: VR (SD) Glock adopted as the native base** |
| Native arsenal | **15/15 copied and routed**; `v_satchel_radio` verified statically |
| Aim direction | **FIXED 2026-11-10** — firing line reads the aim pose; two-hand HIL check pending |
| HEV glove on both hands | **SHIPPED** — `v_hand.mdl` rebuilt from the HL:VR HEV glove |

W0 proves the engine can select a native model and fall back to legacy when the
native file is absent. W1 passed after the maintainer approved the calibrated
markers: red is the barrel bore, blue is the trigger contact, green is the rear
sight, and yellow is the hammer.

Native weapon production was frozen on 2026-11-01 after the source-derived
blockout reproduced MMOD mesh defects. It was reopened on 2026-11-06 and
resolved the same day by adopting a complete third-party asset instead of
sculpting one; see [`STATUS.md`](STATUS.md#native-base-adopted-2026-11-06).

## Shipped base: Half-Life: VR (SD)

The native Glock is `assets/valve_vr/models/native/v_9mmhandgun.mdl`, taken
unmodified from Half-Life: VR's `art/models/SD/v_9mmhandgun.mdl`. It is a
complete GoldSrc MDL with three bodies (gun, magazine, Gordon/HEV glove hands),
the silencer bodygroup, four anchor attachments and ten sequences.

| Property | Value |
|---|---|
| Bodies | `glock_reference`, `clip_reference`, `v_9mmhandgun_v_glock_hands_reference` |
| Attachments | 0 `muzzle_pos`, 1 `muzzle_pos2`, 2 `hud_pos`, 3 `hud_pos2` |
| Sequences | `idle1..3`, `shoot`, `shoot_empty`, `reload`, `reload_noshot`, `draw`, `holster`, `add_silencer` |
| Hands | Gordon gloves (`gordon_glove.bmp`, `gordon_sleeve.bmp`) |
| Provenance | Half-Life: VR Mod, Max Makes Mods; see `assets/valve_vr/CREDITS.md` |

The sequence table matches the legacy MMOD Glock name-for-name and in the same
order, so the indices the game DLL sends keep their meaning. Attachment 2 and 3
are HUD anchors on this MDL, therefore `ejection_attachment` and
`magwell_attachment` are `-1` in the profile instead of 2 and 3.

Verified in-engine on 2026-11-06:

```text
[VR_WEAPON_ROUTE] legacy=models/v_9mmhandgun.mdl native=models/native/v_9mmhandgun.mdl route=native
[VM_DBG_CHANGE] viewmodel changed to: 'models/native/v_9mmhandgun.mdl'
```

### Bases measured and rejected

Both alternatives come from the same MMOD lineage and were measured with the
project's `A1` audit at the same settings:

| Asset | Triangles (body) | Boundary edges | Non-manifold | Winding | `A1` score |
|---|---:|---:|---:|---:|---:|
| MMOD decompile | 294 | 63 | 3 | 4 | 9.67/35 |
| Blue Shift VR derivative | 473 | 57 | 9 | 0 | 30.00/35 |
| Half-Life: VR SD (shipped) | 485 | — | — | — | adopted unmodified |

The Blue Shift VR derivative is cleaner than the MMOD decompile but ships
scientist hands, which do not match this mod. All sculpted trigger, guard and
magazine-release work was abandoned on 2026-11-09 and its evidence removed;
no cosmetic variant is adopted.

## Grip alignment for native models

The imported Half-Life: VR viewmodels are authored around that mod's own hand
bone, and their flat-screen idle pose tilts the whole model about 46 degrees
down. The translation anchor seated the grip on the palm but kept the tilt, so
the barrel did not follow the hand.

Fix: the renderer rotates the **native** viewmodel around the palm after seating
it, so the barrel (`muzzle_pos - grip bone`) points along the controller grip
pose (`ref/gl_vr/gl_studio.c`, `R_VR_RotateViewmodelToPalm`). It is gated by
`vr_anchor_rotation` (default 1) and skipped for weapons whose profile has no
muzzle (`muzzle_attachment -1`: melee and toss). The model is re-seated after
the rotation.

Measured after the fix, with no per-weapon data:

| Check | Result |
|---|---|
| barrel vs hand, 9 gun models | 0.0 deg |
| shot start vs muzzle | 0.05-0.07 units |
| shot vs barrel | 0.01-0.18 deg (shotgun spread excluded) |

The earlier per-weapon `grip_rot` values were removed; they compensated one
pose and drifted at others. The hand-angle conversion was also checked: the
legacy Euler conversion maps OpenXR pitch/yaw/roll to the GoldSrc axes
correctly, so it was not the cause (see `M1` assertion 48 and
`scripts/check_hand_conversion.py`).

### Left-handed hold

`vr_lefthanded 1` now mirrors the whole viewmodel through the same renderer
path as `cl_righthand`, so the baked right hand becomes a left hand, and the
barrel rotation runs against the left grip pose.

## Aim direction (measured, rejected)

Aim direction is still the hand pose plus the per-weapon `pitch_adjust`. Two
model-derived alternatives were measured on 2026-11-06 and rejected:

| Candidate axis | Angle from the hand forward |
|---|---:|
| `muzzle_pos2 - muzzle_pos` | 66.5 deg |
| muzzle world position minus the weapon pose origin | 42.0 deg |

Neither is a barrel axis in the hand frame, so using them would have thrown the
shot away from where the player is aiming. The measurement was taken with
`vr_test_hand_pitch -5 -10` on `models/native/v_9mmhandgun.mdl` and a `+attack`
event, which is the only path that calls `XR_GetPrimaryHandMuzzleTransform`.

The 42-degree pose delta also means the native models do not yet sit in the palm
the way the legacy offsets expect: the profile `grip_offset` values were tuned
for the MMOD meshes. Re-check the model-derived aim **after** the per-weapon grip
pose is verified against a capture; the axis is only meaningful once the weapon
visually points where the hand points.

The code change was reverted. Do not reintroduce it without that capture.

### Aim pose contract (2026-11-09)

The viewmodel and the `viewmodel` entity are oriented by `XR_GetPrimaryAimPose()`
(the ray the player points with). `XR_GetPrimaryGripTransform()` supplies only
the palm position. The muzzle, the laser and the authoritative firing line also
read the aim pose, so the visible barrel and the shot agree. Do not feed the
grip orientation back into `XR_GetWeaponPose`; `M1` assertion 49 deliberately
tilts the simulated grip pose away from the aim pose and fails if the renderer
does.

Aim-related cvars:

| Cvar | Default | Meaning |
|---|---|---|
| `vr_lasersight` | `1` | Draw the 3D laser from the aim pose. |
| `vr_crosshair` | `0` | Draw the flat-screen 2D crosshair in VR. Off because it is a head-locked screen sprite that shows in both eyes and follows the head. |
| `vr_test_grip_delta_pitch` | `0` | Harness only: tilt the simulated grip pose away from the aim pose. Keep `0` in shipped configs. |

## Content families

```json
{
  "content_family": "native",
  "rig_contract": "socketed",
  "interaction_contract": "physical_parts",
  "fallback": "legacy"
}
```

| Field | Values |
|---|---|
| `content_family` | `native` / `legacy` |
| `rig_contract` | `socketed` / `legacy_skinned` |
| `interaction_contract` | `physical_parts` / `scripted` |
| `fallback` | `legacy` |

`contract_revision` is a separate integer when a contract changes.

## Native route (W0)

Cvar:

```text
vr_native_weapons 0|1
```

When enabled, the client tries:

```text
models/native/<legacy-basename>.mdl
```

If the model is missing or invalid, it uses the legacy model and logs:

```text
[VR_WEAPON_ROUTE] legacy=... native=... route=native|fallback|legacy
```

The shipped default lives in `assets/valve_vr/vr_defaults.cfg`
(`vr_native_weapons 1`), which `autoexec.cfg` loads with `exec vr_defaults.cfg`.
The cvar itself is not archived, so `config.cfg` cannot silently override it.
Both install paths write that line: `scripts/setup_out_gamedir.sh` for the
desktop build and `scripts/deploy_quest_assets.sh` for Quest.

Rules for a native asset:

- The file name must equal the legacy basename exactly. Android and Linux are
  case-sensitive, so `v_9mmar.mdl` does not satisfy a request for
  `models/v_9mmAR.mdl`.
- Attachments must be `muzzle_pos`, `muzzle_pos2`, `hud_pos`, `hud_pos2` in that
  order, because the profile and the aim code index them by number.
- The sequence table must keep the legacy role at each index, because the game
  DLL sends indices, not names. A rename such as `reload` to `reload_vanilla`
  is safe; reordering is not.
- `ejection_attachment` and `magwell_attachment` stay `-1` when attachments 2
  and 3 are HUD anchors.

`python3 scripts/check_native_weapon_assets.py` verifies all of the above
statically. It is a contract check, not a gate.

## Coordinate spaces

| Space | X | Y | Z |
|---|---|---|---|
| GoldSrc world | forward | left | up |
| SMD viewmodel (this decompile) | width | vertical | length |
| Blender | right | forward | up |

Scale: `0.025 m/unit` (40 units/m). SMD Euler order: `Rz * Ry * Rx`.

The raw SMD body is **not** the rendered engine orientation. Do not assume that
a raw coordinate corresponds to the same visual axis. The W1 calibration is the
authority: coloured markers must land on the muzzle, trigger guard and slide
top before any modeling starts.

## Harness rule

- Never label a camera `front` or `top` from a raw axis alone.
- Use landmark markers and orthographic views.
- If the muzzle marker is not on the barrel bore, W1 fails.
- If the trigger marker is not on the trigger blade, W1 fails.
- W1 is approved. Cosmetic mesh work is not authorised; see
  [`STATUS.md`](STATUS.md) for the current blockers.

## Rig and animation

- The shipped asset is `legacy_skinned`, not `socketed`: the parts follow the
  baked rig and no interaction sockets exist yet.
- Weapon bones on the Glock: 34, including `Bip01 R Hand`, `muzzle_pos`,
  `muzzle_pos2`, `hud_pos`, `hud_pos2`, `Box02` and `BoxGun`.
- Sequences come from the asset: idle, fire, fire_empty, reload, reload_noshot,
  draw, holster and silencer attach. The VR renderer freezes idle/draw/holster
  where the flat-screen motion would fight 6DoF (`ref/gl_vr/gl_studio.c`), and
  the physical reload drives the staged interaction.
- Do not add bones to a viewmodel. Append attachments at the end of the table.
- The six interaction sockets (primary grip, offhand grip, magwell, ejection,
  slide rack, trigger contact) remain a later task. They are not a prerequisite
  for the shot-vector or hand-skeleton work.

## Order

1. W0 runtime/fallback — passed.
2. W1 coordinate calibration — passed and human-approved.
3. Native arsenal adoption — Glock shipped; the remaining viewmodels are next.
4. Aim direction from `muzzle_pos2`, then per-weapon pose verification.
5. HEV glove for both hands.
6. Interaction and reload reuse.
7. Expansions and mods.
