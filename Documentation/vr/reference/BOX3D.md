# Box3D as the physics dependency

**Status:** dependency evaluation. Nothing is integrated or linked yet.
**Snapshot:** `3rdparty/box3d`, `v0.1.0-42-g3362633` (2026-10-27), MIT, Erin Catto.

Paths prefixed with `3rdparty/` are relative to the workspace root (the
directory that contains `vibe-life-vr/`), not to this repository. Paths without
that prefix are repository-relative.

## 1. Why this document exists

The reference study in
[`REFERENCE_PORTS.md`](REFERENCE_PORTS.md) describes how Half-Life: VR Mod uses
reactphysics3d for hand, weapon and debris interaction. The maintainer prefers
Box3D for that role. This document records what Box3D actually provides, what
it would cost to adopt, and which parts of the reference design change as a
result.

## 2. Verified facts

Checked in this workspace on 2026-11-06, from the pinned snapshot:

- Portable C17, data-oriented, no C++ and no STL in the library: about 69k lines
  across `src/` and `include/`, 96 bytes for `b3MeshData` and 12 bytes for a
  `b3MeshTriangle`.
- Builds and passes its own unit suite on Linux x86_64 with GCC 16.2.1:

  ```sh
  cmake -S ../3rdparty/box3d -B out/box3d-build -DCMAKE_BUILD_TYPE=Release \
        -DBOX3D_SAMPLES=OFF -DBOX3D_UNIT_TESTS=ON
  cmake --build out/box3d-build -j 20
  out/box3d-build/bin/test
  ```

  Result: `All Box3D tests passed!` in 1.51 s. `libbox3d.a` is 1.85 MB
  unstripped.
- Single-threaded by default: `b3DefaultWorldDef()` leaves `workerCount` at 0,
  and `b3CreateWorld` only spawns its internal scheduler when the value is
  greater than 1 (`3rdparty/box3d/src/physics_world.c:367-388`). That matters
  because GoldSrc game logic is single-threaded and every Quest core counts.
- Units are configurable at runtime: `b3SetLengthUnitsPerMeter()`
  (`3rdparty/box3d/src/core.c:42-53`). GoldSrc uses 1 unit = 1 inch, so
  `b3SetLengthUnitsPerMeter(39.37)` lets the whole integration stay in engine
  units and keeps slops, tolerances and joint limits in the same space as
  gameplay code.
- Allocator is replaceable: `b3SetAllocator()`
  (`3rdparty/box3d/include/box3d/base.h:112`).
- Queries work without bodies: `b3World_OverlapAABB`, `b3World_OverlapShape`,
  `b3World_CastRay`, `b3World_CastRayClosest`, `b3World_CastShape`
  (`3rdparty/box3d/include/box3d/box3d.h:83-133`).
- A first-person character controller exists: `b3World_CastMover`,
  `b3World_CollideMover`, `b3SolvePlanes`, `b3ClipVector`, documented as
  "the style of mover common in first-person shooters"
  (`3rdparty/box3d/docs/character.md`). Marked experimental.
- Mesh cooking output is a self-describing blob: `b3MeshData` carries
  `version`, `hash`, `byteCount`, `nodeOffset`, `triangleOffset`
  (`3rdparty/box3d/include/box3d/types.h:2332-2360`), which is exactly the
  shape of a per-map cooked cache.
- Determinism: documented for both worker counts and (on 64-bit) platforms,
  with `-ffp-contract=off` as the required compiler flag
  (`3rdparty/box3d/docs/faq.md:169-181`,
  `3rdparty/box3d/docs/simulation.md:1995-2005`).
- Recording and replay are self-contained, including meshes and hulls
  (`3rdparty/box3d/docs/recording.md`).

Constraints that shape any integration:

- **Mesh shapes only create contacts on static bodies**
  (`3rdparty/box3d/include/box3d/box3d.h:906-908`). BSP world geometry is a
  perfect fit; moving brush entities (doors, `func_train`, elevators) are not.
  They need convex hulls on kinematic bodies, or a static body whose transform
  we update.
- Pre-1.0. The public API is still moving (42 commits past `v0.1.0`), and the
  character mover is explicitly experimental.
- Rapier-style "collision-only world" does not exist. The equivalent is a world
  with static bodies only and no `b3World_Step`, or pure query calls.

## 3. Box3D versus reactphysics3d for this project

| Criterion | Box3D | reactphysics3d (as used by Half-Life-VR) |
|---|---|---|
| Language | C17, no STL, no exceptions | C++11, allocation-heavy, throws |
| Engine integration | drops into a C99/C17 codebase | needs a C++ TU boundary and libstdc++/libc++ on Quest |
| Units | runtime `b3SetLengthUnitsPerMeter` | fixed meters, recommends 0.1-10 m shapes |
| Threading | off by default, external task system optional | own threading model, must be tamed |
| Determinism | documented, cross-worker and cross-platform | not a design goal |
| Character controller | built-in geometric mover plus plane solver | must be built on top |
| Cooked geometry | hashed, versioned, serializable blob | mesh built from triangles at runtime |
| Regression testing | record/replay built in | none |
| Footprint | 1.85 MB static lib, 96 B mesh header | larger, C++ runtime |

Two consequences for us:

1. The unit mismatch disappears. Half-Life VR scales everything to meters and
   keeps two coordinate conversions (`vrToHL`/`hlToVR` in `VRHelper`). We can
   point Box3D at engine units once and skip that class of bug.
2. A deterministic replay harness is a viable CI gate, in the same spirit as
   `M1` and `R1`: record a fixed scenario, replay it, compare the final state.
   No headset and no runtime needed.

## 4. What the reference design needs, mapped to Box3D

| Half-Life-VR need | Box3D answer |
|---|---|
| BSP world collision mesh | `b3CreateMeshShape` on a static body, `b3CreateMesh` with `identifyEdges = true` for shared edges |
| Per-map collision cache | `b3MeshData` blob with `version`/`hash`/`byteCount`; write it next to the BSP, validate the hash on load |
| Hand/weapon hitbox tests | `b3World_OverlapShape` / `b3World_CastShape` with a `b3ShapeProxy`; no bodies required |
| Controller touch and grab line of sight | `b3World_CastRayClosest` plus `b3World_OverlapShape` |
| Broad phase before entity work | `b3World_OverlapAABB` returns a `b3TreeStats` and per-shape callback |
| Player capsule tests | `b3World_CastMover` / `b3CollideMover` |
| Dragged object pushes the player | the mover API's `pushLimit` gives soft versus rigid contact, which the reference had to special-case |
| Debris and gibs with real contacts | dynamic bodies, `b3World_Step`, contact events |
| Ejected magazine (currently `MOVETYPE_BOUNCE`, D-008) | dynamic body; can be revisited after stage 3 |
| Moving platforms carrying the player | `b3MoverJoint` / dynamic mover sample, or kinematic hull bodies |
| Trigger volumes | sensors plus sensor events, or keep GoldSrc triggers |

Gaps to plan around:

- Moving brush entities cannot use meshes. Options: one hull per brush plane
  (GoldSrc brushes are convex by construction, so a hull is a natural fit),
  or a static body transform update per frame with mesh geometry.
- `b3MeshData` is cooked, not the BSP itself. Cooking must be done from the
  render faces and validated against the BSP's clip hulls, otherwise the
  physics world and the movement world disagree at step edges.

## 5. Integration plan

Staged so every stage is independently revertable and testable.

| Stage | Work | Gate | Risk |
|---|---|---|---|
| S0 | Add the library to the build as an isolated target; `b3SetLengthUnitsPerMeter(39.37)`, `workerCount = 1`, custom allocator; pin the commit | build on Linux, Android arm64 and the Quest APK | waf and Gradle both need the target |
| S1 | Cook the BSP into a static mesh, cache it beside the map with hash validation, expose only queries (no bodies, no step) | new assertion block in `M1`: ray/overlap results versus `SV_Move` traces | cooking cost and memory |
| S2 | Hand, weapon and melee queries on top of S1 (touch, grab, hit group, relative velocity) | extends `A7`; new "swing at air does nothing" assertion | gameplay feel |
| S3 | Debris and thrown objects as dynamic bodies with a strict body budget | new gate; `R1` must stay green | performance on Quest |
| S4 | Character mover as an alternative locomotion path, A/B against the current pmove path | `M1` plus a ladder/step scene | prediction drift |
| S5 | Moving brushes and platforms | `R1` | graph-order and timing bugs |

S0 and S1 are the only stages that should be attempted while the weapon epic is
frozen; they add no gameplay behaviour.

## 6. Verification spikes before any integration

1. Cook a representative BSP (a large map such as `c1a4f`) and measure cook time
   and mesh memory. Estimate for 50k triangles is about 4 MB from the struct
   sizes above; confirm it.
2. Confirm `b3SetLengthUnitsPerMeter(39.37)` does not break internal tolerances
   (`B3_LINEAR_SLOP`, `B3_MAX_AABB_MARGIN` scale with it).
3. Confirm the engine's warning set (`-Werror=...` in `wscript`) can be applied
   to the Box3D sources, or isolate them with their own flag set.
4. Confirm `-ffp-contract=off` can be set per-target in waf without touching the
   rest of the engine.
5. Confirm Android arm64 uses the NEON path (`simd_neon.h`) and that the Quest
   build stays single-threaded.
6. Confirm recording/replay determinism across the two build hosts we care
   about (Linux x86_64 and Android arm64).

## 7. Open questions

1. Does the deterministic replay gate belong to `M1`, or does it deserve its own
   gate id and evidence directory?
2. Do we cook the mesh at map load, or ship cooked data, or both with a
   first-run fallback?
3. Is the character mover (S4) worth pursuing before the hand and weapon
   interaction work is stable?
4. When Box3D becomes a build dependency, does it enter as a submodule of this
   repository pinned to the same commit, replacing the workspace-level clone?
