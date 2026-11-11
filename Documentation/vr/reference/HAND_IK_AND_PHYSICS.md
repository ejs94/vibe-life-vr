# Hand IK, Box3D contact and manual reload

**Status:** design plan. Nothing in this document is implemented.
**Scope:** arm IK for the standalone hand, the role Box3D plays in it, and how
spatial hand state upgrades the staged manual reload.

## 1. Verified starting point

These facts are read from the current tree, not assumed:

- The standalone hand is rigid. `R_VR_DrawHandAtBone`
  (`ref/gl_vr/gl_studio.c:5410`) copies the world transform of one baked
  viewmodel bone and `R_VR_DrawHandsAtGrip` (`ref/gl_vr/gl_studio.c:5465`)
  selects that bone. `R_DrawHandEntity` (`:5289`) draws the model there. There
  is no arm chain, no IK and no collision.
- A semantic hand map already exists. `vr_hand_slot_t`
  (`ref/gl_vr/gl_studio.c:57-77`) covers hand, palm and five fingers x three
  segments (17 slots), and `R_VR_HandSemantic` (`:97`) resolves `Bip01`,
  `Xbow biped`, `BoneNN` and `FingerNN` names. The OpenVR 31-bone layout also
  contains `Root`, `Wrist`, the arm chain and five auxiliary bones; those are
  the missing slots, not the fingers.
- The grip pose is the socket anchor: `XR_GetGripPoseTransform`
  (`engine/platform/openxr/xr_input.c:1381`). It is deliberately separate from
  the aim pose (D-002, D-023, D-024).
- Fingers are procedural or baked, not tracked. There is no
  `XR_EXT_hand_tracking` consumer in `engine/platform/openxr/`; the inputs are
  `vr_finger_curling`, `vr_hand_pose_source` and `vr_hand_anim_blend`
  (`engine/platform/openxr/xr_core.c:336-390`).
- Manual reload is a staged state machine in the game DLL, driven by
  `IN_RELOAD` presses: `CGlock::VRManualReloadThink`
  (`3rdparty/patches/hlsdk-vibe-life.patch:742`). Its own comment (`:738`)
  states that the spatial off-hand gate will replace the second and third
  presses once the engine exposes magwell/slide flags.
- The engine already carries VR state in the player entity: `vuser1` muzzle
  offset, `vuser2` aim angles, `vuser3` hand velocity, `vuser4[0]` two-hand
  flag, `vuser4[1]` VR-active flag, `vuser4[2]` reserved
  (`engine/server/sv_pmove.c:942-960`).
- Box3D is evaluated but not linked. `S0`-`S2` are defined in
  [`BOX3D.md`](BOX3D.md) section 5; `S2` is the hand/weapon query stage.
- Off-hand grab already uses an engine raycast through the `vr_grab` command
  (`engine/platform/openxr/xr_input.c:1275-1321`), not a physics query.

## 2. What Box3D is for, and what it is not

Box3D is not an IK solver. It provides collision shapes, contacts, joints and a
character mover; it cannot place an elbow. The IK solver belongs to the
renderer and must stay a pure function of the grip pose.

Box3D is the right tool for:

- Hand/weapon versus world overlap and ray/cast queries (Box3D `S1`/`S2`).
- Weapon clipping against walls, which is the "weapons have no clip" field
  report.
- Debris and thrown objects later (`S3`).

Box3D must not own the hand or the weapon transform. Both are kinematic and
authoritative; a dynamic body would fight `XR_GetWeaponPose()`.

Units stay in engine units. Call `b3SetLengthUnitsPerMeter(39.37)` once at
startup, as recorded in [`BOX3D.md`](BOX3D.md) section 2, and never convert to
meters in gameplay code.

## 3. Target rig contract

- The baked hand stays authoritative (D-003). IK drives the standalone
  `v_hand.mdl` arm only, and only while that hand is rendered.
- Do not add bones to a viewmodel (D-004). If the existing `v_hand.mdl` arm
  chain lacks a semantic wrist or elbow, extend the standalone hand through
  `scripts/build_twohand_mdl.py` and re-run `scripts/check_hand_asset.py`; never
  touch a weapon viewmodel.
- Extend, do not replace, `vr_hand_slot_t` with `VR_HAND_SLOT_ROOT`,
  `VR_HAND_SLOT_WRIST`, `VR_HAND_SLOT_ELBOW` and `VR_HAND_SLOT_SHOULDER`, and
  teach `R_VR_HandSemantic` the matching names.
- Three anchors define the chain: the shoulder is a body/head-relative point,
  the wrist is the grip pose origin, and the palm is a fixed offset from the
  wrist. The palm remains the reference point (hard rule in
  [`AGENTS.md`](../../../AGENTS.md)).
- Finger pose is unchanged: baked animation plus `vr_hand_input_curl`. IK never
  rotates a finger.
- A blend weight `vr_hand_ik` (0 = baked, 1 = IK) makes the stage reversible.
  The right-handed player poses must be numerically identical at weight 0.

## 4. Staged plan

| Stage | Work | Test hook | Risk |
|---|---|---|---|
| `H0` | Extend the semantic map with root, wrist, elbow and shoulder; add a name/index dump for `v_hand.mdl` | new `scripts/check_hand_skeleton.py` | asset layout differs from the enum |
| `H1` | Analytic two-bone arm IK in the renderer, wrist target from the grip pose, elbow pole from the shoulder frame, joint limits | new `scripts/verify_hand_ik_math.py`; `M1` assertions | arm pop and shoulder placement |
| `H2` | Link Box3D as `S0` and expose `S1` world queries | build on Linux and Android; `M1` ray assertions | waf and Gradle targets |
| `H3` | Contact-aware hand: overlap/cast the hand against the world, never penetrate | extends `A4` and `M1` | query cost on Quest |
| `H4a` | Spatial reload gate using relative socket math only, no Box3D | extends `A7` | socket calibration |
| `H4b` | Add wall occlusion to the reload gate via `H2` | extends `A7` | false negatives near cover |
| `H5` | Weapon-vs-wall clipping and push-back | `V1` visual and `R1` | breaks the aim pose if done in the wrong layer |
| `H6` | Debris and ejected magazine as dynamic bodies (`S3`) | new gate | Quest budget |

`H0`-`H1` have no physics dependency and can start now. `H4a` also needs no
Box3D, which is why the reload upgrade is split from the wall test. Do not start
`H2` before the weapon epic accepts a new build dependency.

When a stage lands, add its gate row to [`../GATES.md`](../GATES.md) in the same
commit. The names above are stage names, not registered gates yet.

## 5. Engine to game data contract

The game DLL cannot read renderer state, so the reload gate needs an explicit
channel. The cheapest option that does not change the network protocol:

- Use the reserved `vuser4[2]` float as a bitfield written by `SV_PlayerRunThink`
  next to the existing VR state (`engine/server/sv_pmove.c:942-960`).
- Bit 0: off-hand inside the magwell volume.
- Bit 1: off-hand inside the ejection volume.
- Bit 2: off-hand touching the slide and moving along the rack axis.
- Bit 3: reload is allowed (weapon has a clip to move).
- The game DLL reads the bits in `VRManualReloadThink` and keeps the pressed
  button as an accessibility fallback.

If the socket set grows, add a versioned `vr_state` usercmd extension instead of
packing more floats. Do not publish per-frame positions through cvars: cvars
are configuration, not a state bus, and they break recording/replay.

## 6. Reload state machine: today and target

Today (`3rdparty/patches/hlsdk-vibe-life.patch:742`), every stage is one
`IN_RELOAD` press gated by `vr_manual_reload`:

| Stage | Today | Target spatial gate |
|---|---|---|
| 0 idle | any B press | off-hand near the magwell, grip pressed |
| 1 ejected | B press | fresh magazine near the magwell, release |
| 2 inserted | B press | off-hand touching the slide, fast motion along the rack axis |

Proposed cvar values, to be documented in [`../WEAPONS.md`](../WEAPONS.md)
when implemented:

- `vr_manual_reload 0`: off.
- `vr_manual_reload 1`: staged button path, current behaviour.
- `vr_manual_reload 2`: spatial gate, with the button as fallback when the
  off-hand tracking is unavailable.

The gate needs three sockets on the weapon: magwell, ejection and slide rack.
Those are part of the six interaction sockets that are still a later task
([`../WEAPONS.md`](../WEAPONS.md) line 197). Append them as attachments; never
add bones.

## 7. Acceptance criteria

- `verify_hand_ik_math.py` proves the solver in isolation: target error, chain
  length clamp, joint limits and right-handed invariance at `vr_hand_ik 0`.
- `M1` gains assertions for wrist target error below half a GoldSrc unit and
  for an unstretched chain.
- `A7` gains a negative case: with the off-hand 20 units away from the magwell,
  the spatial gate must not advance the reload.
- `A4` keeps the labelled comparison sheet rule; a green math test is not a
  visual approval.
- The headset check remains the final authority for the firing line and the
  reload feel.

## 8. Risks and invariants

- Never let IK touch the firing line. `XR_GetWeaponPose()` and the bore anchors
  stay the single source of truth (D-002, D-024).
- Never re-skin a baked weapon hand; map it. The baked hand owns the animation
  ([`AGENTS.md`](../../../AGENTS.md) hard rules).
- Keep Box3D worlds static-only until `H6`; do not call `b3World_Step` for a
  query.
- Box3D is pre-1.0; isolate it behind a small `vr_physics` wrapper so the
  renderer and game code never include its headers directly.
- Quest cost: queries only, no bodies, no threads (`workerCount = 1`).

## 9. Open questions

1. Does the arm need to exist while `vr_hide_arms < 2`, that is, while the baked
   viewmodel hand is visible? The default answer is no: the baked hand owns the
   frame.
2. Should the shoulder anchor follow the head or the player's torso? The head is
   simpler and already available, but it makes the arm swing with look.
3. Do we ship a cooked BSP cache for `H2`, or cook on first load? See
   [`BOX3D.md`](BOX3D.md) section 7.
4. Is the spatial reload gate worth the socket calibration for every magazine
   weapon, or do we ship the Glock first and measure the feel?

## 10. Related

- [`../STATUS.md`](../STATUS.md) - blockers and gate state.
- [`../WEAPONS.md`](../WEAPONS.md) - sockets, rig and asset policy.
- [`../DECISIONS.md`](../DECISIONS.md) - D-002, D-003, D-004, D-012, D-024.
- [`BOX3D.md`](BOX3D.md) - dependency facts and `S0`-`S5`.
- [`QUEST_FIELD_REPORTS.md`](QUEST_FIELD_REPORTS.md) - the reports this plan
  answers.
