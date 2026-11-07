# W2 handoff — Glock detail work (paused)

**Status:** paused 2026-11-06. The shipped native Glock is complete and playable;
the detail work described here is unfinished and is handed to a future session,
ideally with a premium model and a human who can model in Blender.

## 1. What is already shipped

`assets/valve_vr/models/native/v_9mmhandgun.mdl` — Half-Life: VR SD Glock,
unmodified, copied from `xash3d-vr-ports/Half-Life-VR/art/models/SD/v_9mmhandgun.mdl`.

| Property | Value |
|---|---|
| Bodies | gun, magazine, Gordon/HEV glove hands |
| Attachments | 0 `muzzle_pos`, 1 `muzzle_pos2`, 2 `hud_pos`, 3 `hud_pos2` |
| Sequences | 10 |
| Engine proof | `[VR_WEAPON_ROUTE] ... route=native` + `[VM_DBG_CHANGE] ... models/native/v_9mmhandgun.mdl` |
| Gates | `W0` PASS, `M1` 44/44, `R1` 19/19, `D1`/`H1` PASS |

## 2. What is incomplete

| Item | State | Blocker |
|---|---|---|
| Trigger guard shape | original taper, no clean vertical rear edge | needs remodeling, not patching |
| Trigger blade | hand-authored 8-vertex box, never approved | depends on the guard |
| Magazine-release paddle | authored twice, never confirmed in a render | depends on the guard |
| Guard rear wall | added, visually blocked the rear of the opening | rejected |
| 6 physical sockets (grip, offhand, magwell, ejection, slide rack, trigger contact) | not authored | needs modeling |
| Export of the sculpted variant | not attempted | pointless until the guard is fixed |

## 3. Why we stopped

1. The original mesh has **no trigger geometry** and its trigger guard is a
   nearly solid block: ray casting through it found a slot only **0.3 units**
   tall (about 7 mm at asset scale). A real Glock guard is 25-30 mm.
2. Blind numeric sculpture in Blender produced pieces that were misplaced,
   floating, or inside the frame. Four trigger generations and three guard
   attempts were rejected, one by a vision judge as a regression (the guard
   detached from the grip).
3. The maintainer decided to stop until either a premium model or a human
   Blender session is available. This is a deliberate stop, not a failure to
   finish.

## 4. Hard-won technical facts (do not rediscover these)

### Coordinate bug that caused every misplacement

New vertices were created with **world** coordinates while the object had a
non-identity `matrix_world`, and a `BVHTree` built from `BVHTree.FromBMesh` is in
**local** space while rays were cast in world space.

Rules:

```python
inv = body.matrix_world.inverted()
vert_local = inv @ Vector(world_pos)          # when creating geometry
ray_origin_local = inv @ Vector(world_origin) # when ray casting
ray_dir_local = (inv.to_3x3() @ Vector(world_dir)).normalized()
hit_world = body.matrix_world @ hit_location  # when reading hits back
```

### Geometry is axis-aligned in world space

After the alignment pass (slide principal axes): **+X width (4.26), +Y forward
(9.91), +Z up (5.70)**. Slide long axis measured at 0.00 degrees off +Y.

### Measured guard region (world coordinates, this alignment)

| Feature | Range |
|---|---|
| Guard opening (open through X) | y -21.3 .. -19.6, z 37.6 .. 38.6 |
| Slot before opening the guard | z 38.15 .. 38.45 only |
| Trigger blade (current) | x -9.33 .. -9.00, y -20.62 .. -20.32, z 37.70 .. 38.55 |
| Rear wall attempt | y -21.02 .. -20.88, z 37.60 .. 38.58 |
| Magazine release attempt | x -11.15 .. -10.82, y -22.40 .. -22.00, z 38.10 .. 38.92 |
| Guard cut box that opened the slot | x -11.0 .. -7.0, y -21.85 .. -19.75, z 37.60 .. 38.60 (removed 14 faces) |
| Taper faces removed | 10 faces with centroids in y -21.55 .. -20.85, z 37.60 .. 38.62 — this detached the guard and was reverted |

### Texture linking

`bpy.ops.import_scene.smd` creates bare Principled materials with **no image
texture nodes**. Load `back.bmp`, `side.bmp`, `chrome.bmp`, `top.bmp` from the
SMD folder and wire an Image Texture node into Base Color, sRGB.

### Camera

`w2_cam` is orthographic; aim it with the gun's own up vector, not world Z:

```python
Z = d                      # direction from target to camera
Y = UP - Z * UP.dot(Z); Y.normalize()
X = Y.cross(Z)
cam.rotation_quaternion = Matrix([[X.x,Y.x,Z.x],[X.y,Y.y,Z.y],[X.z,Y.z,Z.z]]).to_quaternion()
cam.location = target + Z * 30
```

## 5. Files that hold the work

All under `out/` (not committed, local only):

| File | Content |
|---|---|
| `out/w2_work/bsvr_glock/w2_final.blend` | best sculpt attempt: textured, axis-aligned, guard opened, trigger centred |
| `out/w2_work/bsvr_glock/w2_b0_textured.blend` | clean base with textures, before any sculpting |
| `out/w2_work/bsvr_glock/w2_f1_aligned.blend` | exact axis alignment, no sculpting |
| `out/w2_work/bsvr_glock/w2_a9_muzzleframe.blend` | muzzle-face frame reference |
| `out/w2_work/bsvr_glock/` | decompiled source SMDs, textures, QC |
| `out/qa/W2/sessions/20261106_a0..a3/` | renders, audits, session notes |
| `/tmp/opencode/delegate/guard_v1.py` | free-agent script attempt (rejected result) |

## 6. Brief for the next attempt (premium model or human)

Goal: a Glock trigger guard and trigger that read correctly at VR distance,
without touching the rest of the model.

Constraints, in priority order:

1. Do **not** change the outer silhouette, the slide, the grip or the UVs.
2. Do **not** cap intentional openings (muzzle, magwell, ejection port).
3. Keep the 34-bone rig and the existing vertex groups (`root`, `slide`,
   `barrel`, `trigger`). New frame geometry goes to `root`, new trigger
   geometry to `trigger`, weight 1.0.
4. The guard must become a real loop with an opening about **1.0-1.2 units**
   tall and a **vertical** rear edge, not a taper.
5. The trigger blade must hang inside that opening, roughly 1.0 unit tall,
   centred on the frame's centreline, touching the frame only at its pivot.
6. The magazine release is a small paddle on the **left** side (negative X),
   behind the trigger, protruding about 0.1 units.

Acceptance:

- boundary edges must not grow by more than 12 versus the input;
- no new non-manifold edges;
- a side render at the same camera must show: background visible through the
  guard, a vertical rear edge, a centred trigger;
- the maintainer approves the comparison sheet.

## 7. Why the asset work continues without this

The shipped Glock already has ten animations, HEV hands and four anchors. The
remaining detail work is cosmetic. The rest of the roadmap (arsenal, aim anchors,
hand swap, interaction reuse) does not depend on it and is described in
`WEAPONS.md` and `STATUS.md`.

## 8. Next-action plan (no modelling involved)

This is the plan to run in a fresh session. It does not depend on the paused
guard work.

### P1 — full arsenal (highest value for "playable")

1. Copy the 15 Half-Life: VR SD viewmodels from
   `xash3d-vr-ports/Half-Life-VR/art/models/SD/v_*.mdl` into
   `assets/valve_vr/models/native/`, plus `v_hand_hevsuit.mdl`.
2. Every one of them already carries four attachments and its own sequences:

   | Model | Attachments | Sequences |
   |---|---:|---:|
   | v_357 | 4 | 8 |
   | v_9mmar | 4 | 8 |
   | v_9mmhandgun | 4 | 10 |
   | v_crossbow | 4 | 12 |
   | v_crowbar | 4 | 11 |
   | v_egon | 4 | 11 |
   | v_gauss | 4 | 9 |
   | v_grenade | 4 | 8 |
   | v_hgun | 4 | 6 |
   | v_rpg | 4 | 9 |
   | v_satchel | 4 | 4 |
   | v_satchel_radio | 4 | 5 |
   | v_shotgun | 4 | 10 |
   | v_squeak | 4 | 6 |
   | v_tripmine | 4 | 9 |

3. Fix each `vr_weapons.json` entry: `muzzle_attachment 0`,
   `ejection_attachment -1`, `magwell_attachment -1` (attachments 2 and 3 are
   HUD anchors on these models).
4. Verification script: for each weapon, run the native route and assert
   `route=native` plus no model-load error in the log.

### P2 — aim anchor

5. Use `muzzle_pos2 - muzzle_pos` as the ballistic direction in
   `XR_GetWeaponMuzzleParams`, replacing the per-weapon `pitch_adjust`. That is
   what the reference mod does and it removes per-weapon calibration.
6. Prove the right-handed result is unchanged with
   `scripts/verify_grip_pose_math.py`, then run `M1` and `R1`.

### P3 — HEV hands (biggest visual gain per hour)

7. The engine already supports it: `vr_hand_profile=provided`,
   `vr_primary_hand_model`, `vr_offhand_hand_model`.
8. Deploy `v_hand_hevsuit.mdl` (31 bones, 4 attachments, 9 sequences) and point
   the cvars at it; keep `models/v_hand.mdl` as the fallback.
9. `M1` already asserts the unarmed-hand phase (`unit_23`, `unit_24`); watch
   `[VR_HAND_PROFILE]` in the log to confirm which model loaded.

### P4 — interaction without new geometry

10. Use the `BoxPistol` / `BoxGun` / `Box02` hitboxes already present in the QC
    as touch and melee colliders.
11. Re-point the manual reload (`A7`) at the `clip_reference` body and the
    `Box02` bone instead of authoring sockets.

### P5 — animated viewmodels (optional)

12. Test `animov/v_9mmhandgun.mdl` behind a cvar and measure whether the firing
    line moves.

### P6 — evidence

13. Per weapon: native-route log line, `M1`, `R1`. No new gate ids needed.

## 9. Lessons that must survive this handoff

1. Patching a 43-shell low-poly GoldSrc mesh blind costs more than adopting a
   complete asset from the same lineage.
2. Never mix local and world coordinates in this pipeline; the bug is documented
   in section 4 and it invalidated three attempts.
3. A "trigger guard" can be modelled as a block with a slot; measure it before
   assuming there is a cavity.
4. Attachment indices are part of the contract: the old MMOD model had
   attachment 0 on `Bip01 R Hand`, which is why the laser and muzzle position
   were wrong.
5. The SMD importer does not link textures; link them explicitly.
6. A cheap vision judge is useful for catching regressions, but the maintainer
   approves visuals and gates are run, not inferred.
