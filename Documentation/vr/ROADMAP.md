# Roadmap

The roadmap lists active work only. Resolved issues remain in git history and
in the `pre-cleanup-2026-10-31` tag; they are not duplicated here.

## Workstreams

### E1. Asset repair and hand/weapon presentation (active, top priority)

Goal: make the VR viewmodels and hands presentable in the headset without
changing the authoritative animation or breaking the grip pose.

- Repair open boundary loops on holed viewmodels.
- Preserve bones, UVs, weights and bodygroups.
- Keep the baked hand authoritative when a weapon has one.
- Validate with asset audit, MDL roundtrip, 360-degree renders and the Monado
  suite.
- Pilot on the Glock, then the crossbow, then batch the remaining weapons.

Gates: `A1`, `A2`, `A3`, `A4`, `A5`, `A6`, `M1`.

### E2. Weapon interaction

Goal: physical reloading and weapon handling that feels intentional in VR.

- Glock staged manual reload v1 is implemented and tested.
- Extend the contract to the remaining magazine weapons.
- Keep the authoritative firing line unchanged; hand calibration is not a
  ballistics override.
- Document each new cvar or weapon field in `ASSETS.md` and, when relevant,
  `assets/valve_vr/CREDITS.md`.

Gates: `A7`, `M1`, `R1`.

### E3. Mod compatibility

Goal: let GoldSrc mods opt into VR without forking the engine.

- Keep the three-tier compatibility contract.
- Maintain `vr_weapons.json` profiles and fallback muzzle/grip behavior.
- Validate overlay model names against HLSDK requests.

Gates: `A8`, `R1`; reference: `reference/MOD_COMPATIBILITY.md`,
`reference/MODDER_GUIDE.md`.

### E4. VR quality and engine integration

Goal: keep the OpenXR path stable while the VR renderer grows.

- Keep `XR_GetWeaponPose()` as the single pose source.
- Keep the right-handed pose unchanged when adding left-handed behavior.
- Prefer small helpers over growing `gl_studio.c` and the input functions.
- Use repowise/graphify for impact analysis before large renderer changes.

Gates: `M1`, `R1`.

### E5. Quest packaging and hardware validation

Goal: keep the standalone APK and Horizon OS launcher healthy.

- Rebuild the APK after engine, renderer or `vr_weapons.json` changes.
- Run Quest HIL only when the maintainer requests it.
- A Quest pass requires a non-black engine eye dump, the OpenXR startup lines,
  and no native crash.

Gate: `Q1` (pending by default).

## Order of work

1. E1 asset repair.
2. E2 weapon interaction.
3. E3 mod compatibility.
4. E4 engine/renderer quality.
5. E5 Quest packaging as requested.

## Deferred

- Box3D physics for the ejected magazine. The GoldSrc `MOVETYPE_BOUNCE` path is
  used for the manual reload v1.
- Full-body IK/VRIK. The current contract is hand and weapon presence only.
- Detailed procedural hands generated from primitives. The block hand is the
  explicit unarmed placeholder and must not be reshaped into a fake grip.
