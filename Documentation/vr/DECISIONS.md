# Decisions

Architecture and process decisions are recorded here. Add new entries at the
bottom; do not rewrite history. A superseded decision keeps its entry and points
to the replacement.

## D-001: Dedicated VR renderer

**Status:** accepted

The VR path uses `ref/gl_vr/` rather than extending the flat `ref_gl` renderer.
The stereo eye loop, asymmetric frustum, OpenXR swapchain FBOs and 6DoF
viewmodel pass are VR-only concerns. Keeping them separate limits the blast
radius on GoldSrc compatibility.

## D-002: Single weapon pose source

**Status:** accepted

`XR_GetWeaponPose()` is the only place that computes the weapon pose. The
renderer, the viewmodel and the muzzle fallback consume it. Duplicating the
math at multiple call sites caused renderer/viewmodel drift in earlier work.

## D-003: Baked hand is authoritative

**Status:** accepted

When a viewmodel has an authored hand, draw it. The standalone hand is for
unarmed presence and the free offhand. It is a block glove, not a detailed hand
imitating a baked grip. Never generate a detailed hand from primitives. Never
reshape a glove by displacing vertices.

## D-004: No new viewmodel bones

**Status:** accepted

Do not add bones to viewmodels. Append attachments at the end of the attachment
table. Bones are part of the animation and studio-model contract; adding them
breaks existing sequences and third-party assets.

## D-005: Selective upstream sync

**Status:** accepted

Do not blind-merge or rebase upstream. Cherry-pick with a 60-90 day maturity
window, classify by subsystem, test in a sandbox, and then apply. Upstream
documentation is read-only.

## D-006: Quest validation is a maintainer decision

**Status:** accepted

Quest hardware-in-the-loop is not a global requirement for every stage. The
maintainer decides when to run it. Monado is the default local gate. A stage
that was not run on Quest is recorded as `pending`, never as passed.

## D-007: Standard evidence root

**Status:** accepted

All gate evidence goes to `out/qa/<gate-id>/`. Each run has a manifest with the
commit, dirty state, device, command, status and artifact checksums.
`out/qa/<gate-id>/latest` points at the newest run; `out/qa/INDEX.md` lists the
newest result per gate. The old `out/evidence` root was retired on 2026-10-31.

## D-008: GoldSrc bounce for the ejected magazine

**Status:** accepted

Box3D is deferred for the manual reload v1. The ejected magazine uses the
GoldSrc `MOVETYPE_BOUNCE` path. This keeps the interaction inside the engine's
existing physics contract and avoids a new physics dependency for one prop.

## D-009: MMOD reanimation pack is the viewmodel baseline

**Status:** accepted

The 15 MMOD viewmodels are the VR overlay baseline. Their provenance, archive
checksum and per-weapon audit are kept in
[`assets/valve_vr/CREDITS.md`](../../assets/valve_vr/CREDITS.md). The pack is a
non-commercial community asset; the maintainer confirms permissions before
release.

## D-010: Radial liner for accidental viewmodel holes

**Status:** accepted

Accidental holes are repaired by duplicating the boundary loop, offsetting the
new loop inward along the local normal, and bridging the two loops. This gives
the shell an inner wall without changing the outer silhouette. Intentional
openings (barrel, magwell, ejection port) are not capped. The repair must
preserve UVs, weights, bones, sequences, events, bodygroups and attachments.

## D-011: One gate registry, thin read-only gate agents

**Status:** accepted

`Documentation/vr/GATES.md` is the only gate registry. A gate is active only if
it has a row. Gate agents are read-only, read `GATES.md`, run the listed
command, write evidence under `out/qa/<id>/`, and return `PASS`, `FAIL` or
`INCONCLUSIVE`. They do not edit code, docs or assets, and they do not decide
the device mode.

## D-012: Box3D is the physics dependency

**Status:** accepted (dependency choice only; nothing is integrated yet)

Any rigid-body or geometric-query work adopts Box3D rather than
reactphysics3d. Box3D is portable C17, single-threaded by default, has a
runtime length-unit setting so the integration can stay in engine units, ships
hashed and versioned cooked mesh data for per-map caches, and provides a
deterministic record/replay path that can back a CI gate. reactphysics3d, used
by the reference mods, is C++ and was chosen there for a C++ codebase.

Scope: this decides the library, not the schedule. The roadmap still defers
physics work, and adoption is staged as described in
[`reference/BOX3D.md`](reference/BOX3D.md). No Box3D code is linked until the
staged plan reaches S0.

## Retired: W2 asset-sculpt decisions (D-013, D-014, D-022)

**Status:** retired 2026-11-09

These three entries governed the attempt to sculpt a Glock trigger guard onto a
decompiled 473-triangle GoldSrc viewmodel. The work was abandoned: the shipped
native Glock is adopted unmodified from Half-Life: VR (SD), and no cosmetic mesh
variant is adopted. Their long bodies and session brief were removed during the
2026-11-09 cleanup because they had become a maze of constraints that blocked
the real work. The asset policy now lives in [`WEAPONS.md`](WEAPONS.md) and
`assets/valve_vr/CREDITS.md`; the live blockers and the shot-vector handoff live
in [`STATUS.md`](STATUS.md). Durable engine facts from that period (attachment
indices, the local/world coordinate bug, the overlay trap) are preserved in
[`reference/REFERENCE_PORTS.md`](reference/REFERENCE_PORTS.md) and
[`AGENTS.md`](../../AGENTS.md).

## D-015: Native weapons use a measured local grip rotation

**Status:** accepted 2026-11-07

The imported Half-Life: VR viewmodels were authored for that mod's controller
pose. Reusing the MMOD `grip_offset`/`pitch_adjust` left every weapon pointing
about 46 degrees down and 8 degrees left of the hand: the barrel did not follow
the aim, even though the model itself was correct.

Decision:

- Each native weapon profile carries a `grip_rot` measured from its own barrel
  (`muzzle_pos` bone minus the palm/grip bone), applied as a true local rotation
  by `XR_GetWeaponPose`. Measured residuals after the fix are 0.0-0.6 degrees.
- `pitch_adjust` is `0` for the nine gun profiles. The bullet now follows the
  barrel the player sees instead of compensating for a misoriented model.
- Toss and melee weapons keep their old adjustment; their `muzzle_pos` bone is
  not a barrel axis.
- The authoritative firing line is unchanged in code: this is data, and `M1`
  test 18 plus `R1` prove the ballistics and the VR pose did not regress.

Consequences:

- A model or pose-math change requires re-measuring `grip_rot`. The procedure is
  documented in [`WEAPONS.md`](WEAPONS.md#grip-alignment-for-native-models).
- The visual sweep (`scripts/weapon_visual_sweep.sh`) is the review artefact;
  the numeric residual only tells you the measurement converged.

## D-016: Barrel alignment is a renderer rotation, not per-weapon data

**Status:** accepted 2026-11-07

D-015 stored a measured `grip_rot` per weapon. That fixed one pose and drifted
at others, because the tilt comes from the flat-screen idle animation, not from
a constant model offset. The renderer now rotates native viewmodels around the
palm so `muzzle_pos - grip bone` follows the controller grip pose
(`R_VR_RotateViewmodelToPalm`), and the per-weapon `grip_rot` values were
removed. The same rotation is skipped for weapons without a muzzle.

Left-handed mode mirrors the whole viewmodel through the existing
`cl_righthand` flip path, so the baked hand is a left hand and the barrel
rotation runs against the left grip.

The hand-angle conversion hypothesis was tested and rejected: the legacy
converter already maps OpenXR pitch/yaw/roll to the GoldSrc axes, which is now
guarded by an `M1` assertion.

## D-017: The weapon is oriented by the aim pose, not the grip pose

**Status:** accepted 2026-11-09

The OpenXR runtime exposes two poses per controller: the aim pose (the ray the
player points with) and the grip pose (where the palm sits). The grip pose is
tilted roughly 30-40 degrees relative to the aim ray on a Touch controller.

The renderer used the grip pose for the viewmodel orientation. The simulated
Monado harness returned the same values for both poses, so the suite stayed
green while every firearm pointed upward in the headset. The viewmodel and
`viewmodel` entity now read `XR_GetPrimaryAimPose()` for orientation and keep
`XR_GetPrimaryGripTransform()` only for the palm position. The muzzle, the laser
and the authoritative firing line already followed the aim pose, so barrel and
shot are now consistent.

The suite gained assertion 49 and `scripts/check_aim_pose.py`: the simulated
grip pose is deliberately tilted 35 degrees away from the aim pose and both the
renderer and the viewmodel must stay at the aim orientation. Reverting the
renderer to the grip pose makes the assertion fail with a 35 degree pitch.

Consequences:

- A change to the viewmodel orientation must keep the aim/grip split; making
  the simulated poses identical again removes the regression coverage.
- `vr_test_grip_delta_pitch` exists only for the harness and must stay `0` in
  shipped configs.

## D-018: The menu quad is anchored in the same reference space as the head

**Status:** accepted 2026-11-09

`XR_AnchorMenuQuad` located the head in `g_xrLocalSpace` (STAGE when the runtime
supports it) and then created a new `XR_REFERENCE_SPACE_TYPE_LOCAL` space from
those coordinates. LOCAL and STAGE do not share an origin: LOCAL is relative to
the initial headset position while STAGE is the centre of the tracked area.
On the simulated runtime both origins coincide, so the menu landed in front of
the player and the `M1` menu assertions passed; on Quest the offset could push
the panel out of view.

The anchor space is now created with `g_xrLocalSpaceType`, the same type used
for the head pose. The anchor log prints `space_type`, the head position, the
forward vector and the final quad position so a headset run can be diagnosed
from one line.

Consequences:

- The pointer raycast still treats the quad as an identity pose inside
  `g_xrMenuQuadSpace`, so the existing dual-pointer path is unchanged.
- `M1` assertions 36 and 37 still require the menu button path, the quad
  submission and a quad facing the player at a 90 degree heading.

## D-019: A viewmodel's baked off-hand owns that slot

**Status:** accepted 2026-11-09

The satchel viewmodel has a baked off-hand and no baked primary hand; the
charge mesh is skinned to the left arm. The shared hand layer assumed a baked
off-hand always came with a baked primary, and the post-weapon fallback drew
the standalone off-hand without checking the baked one. Together those produced
a hand floating next to the charge when the persistent hand layer was disabled.

Decision:

- `s_viewmodel_offhand_only` marks viewmodels with a baked off-hand and no
  baked primary (currently the satchel).
- For those viewmodels the left arm is not collapsed (the charge would vanish
  with it), the standalone primary hand is not drawn, and the standalone
  off-hand may still be drawn for the free controller.
- The post-weapon fallback only draws the standalone off-hand when the
  viewmodel does not already provide one (or is off-hand-only).

Consequences:

- The satchel now shows the charge plus the baked hand that holds it and no
  duplicate. The baked hand follows the weapon, not the left controller; rigging
  the charge to the real off-hand would need the modelling work that is still
  paused.
- `vr_hide_arms 2` still replaces baked hands with the debug standalone path.

## D-020: Accessibility UI is deferred until the build is playable

**Status:** accepted 2026-11-09

The in-headset menu had four tabs of comfort, handedness, calibration and
debug toggles, and the Quest launcher had a parallel "VR Settings" preference
screen. Both were premature: they were being tuned while the core aiming and
hand alignment were still moving, and the duplication made every default
change a two-place edit.

Decision:

- The in-headset menu is a single **VR Play** page: Continue, Testbed Scale,
  Crossfire (DM), Hazard Course and Quit Game.
- The Quest launcher drops the "VR Settings" destination, its fragment and
  `vr_preferences.xml`; the navigation rail keeps Library, Engine Settings and
  VR Diagnostics.
- The launch arguments no longer read `vr_preferences`. Shipped defaults live
  in `assets/valve_vr/vr_defaults.cfg`, including snap turn and the native
  weapon route. Every deleted toggle remains available as a cvar for console
  and config-file use.
- Accessibility options return only after there is a playable build that the
  maintainer is actively adjusting.

## D-021: The scale testbed ships with the APK and installs on demand

**Status:** accepted 2026-11-09

`testbed_scale` was generated into `out/` and only reachable after a manual
`quest push`. That made the new "Testbed" menu entry fail on a fresh install.

Decision:

- A built copy is committed at `assets/valve_vr/maps/testbed_scale.bsp`, so the
  APK can carry it under `assets/valve_vr/maps/`.
- `scripts/deploy_quest_assets.sh` pushes every `assets/valve_vr/maps/*.bsp` to
  `<basedir>/<gamedir>/maps/`.
- `su.xash.engine.util.TestMaps` copies the bundled map into the active game
  directory before an engine launch that requests `+map testbed_scale`. The
  launcher therefore works without a host-side deploy step.
- `scripts/setup_out_gamedir.sh` replaces the Steam `maps` symlink with a local
  directory of per-file symlinks, then copies the testbed in. It never writes
  into the Steam install.

