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
