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

## Retired: grip/aim calibration decisions (D-015, D-016, D-017)

**Status:** superseded 2026-11-10 by D-024

These entries tuned the viewmodel with per-weapon `grip_rot`, a renderer
rotation, and a grip-vs-aim pose switch. They fixed the visual tilt but left
two sources of truth: the renderer aligned a grip->muzzle axis while the bullet
used hand angles. The bore anchors now define both; the long bodies were
removed during the 2026-11-10 cleanup.

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

## D-023: The firing line follows the aim pose, not the stabilized hand

**Status:** accepted 2026-11-10

**Superseded in part:** D-024 replaced the per-weapon `pitch_adjust` firing
direction with the model bore anchors later the same day. The rule that the
two-hand stabilizer must not change the firing direction still stands.

The muzzle path and the renderer disagreed about which controller pose defines
the barrel. `XR_GetPrimaryHandMuzzleTransform` read
`XR_GetPrimaryHandTransform`, which runs `XR_ApplyTwoHandStabilizer` and blends
the angle toward the primary-to-off-hand grip line whenever two hands are
engaged. The renderer reads the raw `XR_GetPrimaryAimPose`. With two hands on a
pistol, the bullet therefore left along the off-hand line while the visible
barrel pointed along the aim ray.

Decision:

- The muzzle path reads `XR_GetPrimaryAimPose` for `out_aim_angles` and keeps
  the per-weapon `pitch_adjust` application in one place
  (`engine/platform/openxr/xr_input.c`).
- The two-hand stabilizer keeps owning the palm/weapon pose; it no longer
  changes the firing direction.
- The renderer, the laser and the authoritative firing line now share one
  orientation source: the aim pose.

Consequences:

- `aim_shot_evidence.sh` passes with the shotgun spread down from 2.41 to 0.60
  degrees; `M1` 49/49, `R1` 19/19 and `W0` pass.
- The simulated harness cannot engage the stabilizer because the simulated
  primary and off-hand poses are identical, so a headset check with two hands
  is still required before claiming the visual fix.
- A model-anchor direction (`muzzle_pos2 - muzzle_pos`) is still rejected until
  the renderer is proven to align the visible bore to that same anchor.

## D-024: Model bore anchors are the single source of truth

**Status:** accepted 2026-11-10

**Premise under review (2026-11-11):** gate `A9` shows that the pair is the
muzzle's lateral axis, not the bore, on 7 of the 10 native barrel weapons
(Glock 89.8°, MP5 88.4°). The renderer and the firing line still share one axis,
which is the part that stands; the axis itself must be replaced by a per-weapon
bore override or a corrected asset. Do not treat the pair as the bore until
`A9` is aligned.

The renderer and the firing line read different axes. `R_VR_RotateViewmodelToPalm`
aligned `muzzle_pos - grip bone` to the aim pose, while the muzzle path fired
along hand angles plus per-weapon `pitch_adjust`. The visible barrel and the
bullet agreed only when the rotation matched the numbers; models whose
`muzzle_pos` is not the visual bore (Hivehand, RPG) tilted.

Decision:

- The model-owned pair `muzzle_pos` -> `muzzle_pos2` is the bore axis. The
  reference mod uses attachments 0 and 1 for ballistics; the project now does
  the same.
- The renderer rotates the native viewmodel so that pair follows the aim pose
  (`ref/gl_vr/gl_studio.c`, `R_VR_RotateViewmodelToPalm`). Models without
  `muzzle_pos2` fall back to `muzzle_pos - grip`.
- `XR_GetPrimaryHandMuzzleTransform` reads the same world-space pair from
  `clgame.viewent.attachment[0..1]` and derives the direction with
  `VectorAngles`. `pitch_adjust` remains only as a fallback when the anchors are
  absent.
- Melee and toss weapons skip the rotation and keep their authored pose.

Consequences:

- `scripts/aim_shot_evidence.sh` measures the shot against the model bore:
  Glock 0.00, .357 0.19, Gauss 0.00, shotgun 1.44 degrees (pellet spread).
- `M1` 49/49, `R1` 19/19 and `W0` pass.
- The two-hand stabilizer no longer affects the firing direction (D-023).
- Do not re-tune `pitch_adjust` to hide a bad anchor: fix the asset or add a
  per-model anchor override.

## D-025: Test integrity is a gate, not a convention

**Status:** accepted 2026-11-11

- `M1`'s 49 assertions were mostly log greps and could pass on a truncated or
  crashed run; engine exit code and the suite sentinel are now required.
- `T1` mutates the evidence and requires the assertions to flip, so a green
  suite cannot hide a tautological check.
- `A9`-style diagnostics record a FINDING, not a PASS; the `B1` gate (retired
  2026-11-11) tried to convert the bore finding into a real failing gate.

## D-026: Per-weapon bore_axis override

**Status:** superseded 2026-11-11 by D-027

- The 7 off-axis native weapons get a model-space `bore_axis` in
  `vr_weapons.json`; the renderer resolves its sign from the muzzle-minus-grip
  bone vector.
- The 3 aligned weapons keep the legacy pair path.
- The `B1` gate (retired) verified the overrides; HIL visual confirmation is
  still required.

## D-027: The bore axis is measured at runtime from the bone hierarchy

**Status:** accepted 2026-11-11

- The `muzzle_pos -> muzzle_pos2` pair is a lateral muzzle-flash quad, not the
  barrel. Aligning it to the aim pose twisted the native viewmodels by roughly
  90 degrees and made the MP5 shot leave the barrel as a vertical tracer.
- Asset-space axes taken from SMD hitboxes, Blender coordinates or the MDL
  conversion live in a different space than the studio bone transforms. They
  must not be injected into world-space bone math; that is why the per-weapon
  `bore_axis` override twisted the gun and is being removed.
- `R_VR_RotateViewmodelToPalm` now uses the world-space grip-bone -> muzzle-bone
  vector, and the native firing path keeps the raw aim angles
  (`ref/gl_vr/gl_studio.c`, `engine/platform/openxr/xr_input.c`).
- `M1` assertion 52 rejects a vertical green tracer in the weapon captures. The
  earlier 49 log-grep assertions could not detect a bullet firing straight up.


## D-028: The rig curl axis is measured from the MDL, and OpenVR is only a guide

**Status:** accepted 2026-11-11

- `v_hand.mdl` is a Bip01/Valve rig. Measuring its rest bones gives
  `|dot(local Z, curl axis)| = 0.9998` and `local Y = 0.0175`. The old
  "Rimrook local Y" branch swept all five fingers towards -Z instead of
  closing the fist; the renderer now curls every rig about local Z.
- Gate `S1` measures that axis directly from the MDL. `--legacy-y` is a
  negative control that must fail, so recompiling the MDL with a different
  axis convention cannot silently regress.
- The OpenVR 31-bone skeleton is a semantic guide for names and indices,
  not a runtime dependency. The target is the Meta Quest 3 on OpenXR;
  skeletal input must be consumed through OpenXR, never through an OpenVR
  runtime.

**Known limitation (2026-11-11):** the laser is still not collinear with
the visible barrel on the Glock and SMG captures (~40 degrees). D-027
fixed the gun pose and the upward tracer, not the ray/barrel angle. Do
not cite it as a complete aim alignment fix.

**Hand skeleton clarification (2026-11-11):** the OpenXR equivalent of the
OpenVR hand skeleton is `XR_EXT_hand_tracking` with 26 `XrHandJointEXT`
joints, not 31 bones. `S2` maps the shipped rig to that 26-joint set as
the primary reference; the OpenVR enum remains a secondary semantic guide.
The project does not consume `XR_EXT_hand_tracking` yet.

## D-029: A green simulator with a broken weapon is a failing simulator

**Status:** accepted 2026-11-11

- The maintainer will not request Quest 3 HIL while the Monado captures
  show misaligned aim/laser/barrel/hands and the gates still pass.
- `XR_GetPrimaryHandMuzzleTransform` emits `[VR_AIM]` telemetry measuring
  the angle between the authored visible barrel (attachment 0 `muzzle_pos`
  -> attachment 2 `hud_pos`) and the firing/laser direction, plus whether
  the muzzle is in front of the eye. This reference is independent of the
  flash-quad pair used before and of the renderer alignment.
- Gate `V3` and M1 assertion 53 require `angle <= 8` degrees, `in_front=1`
  and at least 6 distinct weapons. Both are intentionally RED on the
  current build (8 of 9 weapons fail; crossbow is behind the head). They
  must not be loosened or marked PASS from an older run.
