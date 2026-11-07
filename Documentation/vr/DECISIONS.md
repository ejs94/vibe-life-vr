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

## D-013: Weapon base is a synthesis, not a replacement

**Status:** accepted; the Glock base choice is superseded by D-014. The lineage
analysis and the per-asset rule remain valid.

The native weapon path learns from the working community VR mods instead of
starting from the raw decompile. For the Glock, `W2` starts from the Blue Shift
VR derivative of the same MMOD mesh: it keeps the source silhouette, fixes the
authored winding, removes the helper camera faces, models the magazine interior
and adds the four model-authored anchors (`muzzle_pos`, `muzzle_pos2`,
`hud_pos`, `hud_pos2`). On the project's own `A1` metric that asset scores
30.00/35 where the raw MMOD decompile scores 9.67/35.

Scope and limits:

- This is Glock-only. The same mod's Magnum and crossbow score 3.33/35 and
  3.00/35 on that metric, below the MMOD sources, so those keep MMOD as the
  base. Adoption is per asset, never per mod.
- The adopted mesh is a starting point. The remaining accidental loops,
  non-manifold edges and zero-area T-junctions are fixed by hand, and the six
  interaction sockets the physical reload needs are authored by us.
- Credit is mandatory: the derivative must be recorded in
  `assets/valve_vr/CREDITS.md` with its source URL and both the Blue Shift VR
  and MMOD lineage.
- The anchor consumer is not decided by this entry. Whether the native route
  reads model anchors or `vr_weapons.json` offsets is a separate decision, and
  `XR_GetWeaponPose()` remains the single pose source either way.

## D-014: Ship the complete Half-Life: VR SD viewmodel instead of sculpting

**Status:** accepted 2026-11-06

The Glock detail work (trigger, guard opening, magazine release) was stopped
after four trigger generations and three guard attempts produced artefacts. The
guard of the source mesh is a near-solid block with a 0.3-unit slot, so every
patch traded one defect for another. Sculpting a 485-triangle GoldSrc viewmodel
blind costs more than adopting a finished one from the same lineage.

Decision:

- The shipped native Glock is Half-Life: VR's `art/models/SD/v_9mmhandgun.mdl`,
  copied unmodified to `models/native/`. It brings the HEV glove hands, three
  bodies, ten sequences and the four anchors.
- The rest of that mod's SD viewmodel set is the preferred source for the
  arsenal, because it shares one 34-bone rig and the same anchor layout. The
  Blue Shift VR set shares the rig too but ships scientist hands, so it is a
  per-asset fallback, not a base.
- Rejections are recorded, not deleted: the measurements and the brief for a
  future modelling attempt live in
  [`reference/W2_HANDOFF.md`](reference/W2_HANDOFF.md).
- No asset is modified by this project without a comparison sheet and the
  maintainer's approval. Copying a complete asset is not a modification.

Consequences:

- `ejection_attachment` and `magwell_attachment` are `-1` for models whose
  attachments 2 and 3 are HUD anchors.
- Aim direction follows the model anchors (`muzzle_pos2 - muzzle_pos`) rather
  than per-weapon pitch calibration once that change lands.
- Black Mesa is Source-engine content packed in VPK, so it is reference only
  and never a direct source for these models.

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
