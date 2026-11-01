# Weapons

This page is the contract for the VR-native weapon path. The legacy path remains
available and must not be broken.

## Status

| Stage | Result |
|---|---|
| W0 native route + legacy fallback | PASS |
| W1 coordinate calibration | **PASS — human approved 2026-11-01** |
| Native Glock mesh | not started |
| Native Magnum mesh | not started |
| Gordon hand | not started |

W0 proves the engine can select a native model and fall back to legacy when the
native file is absent. W1 passed after the maintainer approved the calibrated
markers: red is the barrel bore, blue is the trigger, green is the rear sight,
and yellow is the hammer. The approved frame is now the reference for W2.

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

The W0 test copies an existing MDL to the native path, verifies `route=native`,
removes it, and verifies `route=fallback`. No asset is deployed.

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
- W1 is approved; native mesh, UV, skin and animation work may start.

## Rig and animation (planned, not implemented)

- `socketed` rig: weapon parts and sockets, hands separate.
- Existing hand contract remains 35 bones.
- Weapon-part bones: slide, trigger, hammer, magazine, slide lock, safety.
- Sockets: muzzle, primary grip, offhand grip, magwell, ejection.
- Constraints/IK are authored in Blender and baked into sequences.
- Runtime GoldSrc has no constraints.
- State machine: idle, fire, fire_empty, reload, slide_lock, slide_release, mag_eject, mag_insert.

## Order

1. W0 runtime/fallback — passed.
2. W1 coordinate calibration — passed and human-approved.
3. Native Glock mesh/rig/animation (W2 in progress).
4. Native Magnum replication with no per-weapon code.
5. Gordon hand.
6. Expansions and mods.
