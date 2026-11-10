# Reference port analysis: Half-Life: VR Mod and Blue Shift VR

**Status:** reference study, no implementation.
**Scope:** read-only analysis of the two GoldSrc VR mods added under
`xash3d-vr-ports/`, focused on what can be reused as a design input for
Vibe-Life VR. No code, asset or configuration was changed in this repository.

All source paths in this document are relative to the workspace root (the
directory that contains `vibe-life-vr/` and `xash3d-vr-ports/`). Line numbers
were checked against the snapshots described below.

## 1. Snapshots studied

| Project | Upstream | Snapshot | Shape |
|---|---|---|---|
| `xash3d-vr-ports/Half-Life-VR` | `github.com/maxmakesmods/Half-Life-VR` | `48aebe1c`, 0.7.7-beta (2025-12-25) | Windows-only OpenVR mod for classic Half-Life; `client.dll` + `hl.dll` + external `HLVRConfig.exe` |
| `xash3d-vr-ports/Blue-Shift-VR` | `github.com/DmitryShaburov/Blue-Shift-VR` | vendored tree, "Beta" | the same VR code ported onto the HL 25th Anniversary engine and the TWHL "Blue Shift Updated" SDK; Linux makefiles; in-game VGUI2 settings |

Facts established while reading:

- The two projects share one VR implementation. A diff of the movement handler
  shows formatting and API-port changes only
  (`xash3d-vr-ports/Half-Life-VR/src/dlls/VRMovementHandler.cpp` versus
  `xash3d-vr-ports/Blue-Shift-VR/dlls/vr/VRMovementHandler.cpp`). The same
  holds for `VRController`, `VRControllerInteractionManager` and
  `VRPhysicsHelper`. Treat Half-Life-VR as the design reference and Blue Shift
  VR as the newer integration/portability reference.
- Neither project owns the engine. Everything happens inside the game DLLs
  (client, server, and a fork of `pm_shared`), plus a renderer hook layer.
- Half-Life-VR is Windows-only; Blue Shift VR ships `linux/Makefile*`
  (`hl_cdll`, `hldll`, `rp3d`) and a `vgui.so`, so the same code builds on
  Linux.

Inference, not fact: the VR layer is portable across GoldSrc SDK generations
because its coupling points are narrow (movement fork, entity class names,
renderer entry points). Porting cost in Blue Shift VR came from SDK churn, not
from VR design.

## 2. Architecture comparison

| Concern | Vibe-Life VR | Half-Life-VR |
|---|---|---|
| Runtime | OpenXR (`engine/platform/openxr/`) | OpenVR/SteamVR (`cl_dll/openvr`) |
| Renderer | dedicated `ref/gl_vr/` | hooks into `client.dll` drawing, own eye FBOs and display-list multipass |
| Engine ownership | yes, we own Xash3D FWGS | no, stock HL engine |
| Movement owner | engine `pmove` with our prediction | forked `pm_shared` compiled into **both** DLLs |
| Pose source of truth | `XR_GetWeaponPose()` (D-002) | controller transform, then model attachments on the server |
| Pose transport | engine-side, predicted | three client commands per frame (`vrupd_hmd`, `vrupdctrl`) |
| Interaction | grab/socket contracts in `vr_weapons.json` + cvar set | reactphysics3d on the server plus class-name whitelists |
| Settings UI | cvar set + in-game `vr_menu_*` | external `.exe` (HLVR) / in-game VGUI2 pages (BS-VR) |
| Platform | Linux desktop + Quest standalone | Windows desktop (HLVR) / Windows + Linux (BS-VR) |

## 3. Observations

Each item lists the evidence, why it matters for us, and what I would do.

### 3.1 They own the mover instead of fighting it

Half-Life-VR forks `pm_shared/pm_shared.cpp` (about 4.2k lines) and compiles it
into **both** the client and the server DLL
(`xash3d-vr-ports/Blue-Shift-VR/linux/Makefile.hldll`, `pm_shared.o`). The
fork is driven by callback externs (`VRGlobalGetNoclipMode`,
`VRGetLadderMode`, `VRGetGrabbedLadder`, `VRIsPullingOnLedge`,
`VRIsAutoDuckingEnabled`, ...) declared at the top of
`xash3d-vr-ports/Half-Life-VR/src/pm_shared/pm_shared.cpp:37-51`.

Two design choices are worth stealing:

1. **The VR player walks in `MOVETYPE_NOCLIP` on purpose** so doors, elevators
   and crushers cannot kill or shove them, and a hand-written `PM_YesClip`
   resolves the real collision. See the comment at
   `xash3d-vr-ports/Half-Life-VR/src/pm_shared/pm_shared.cpp:3312`.
2. **Movement outside the input stream is done by re-entering the real mover**
   with a synthetic command. `VRMovementHandler::DoMovement` backs up
   `playermove_t`, sets a fake 10 ms frame, forces `IN_FORWARD`, sets
   `forwardmove` so the mover travels exactly the requested distance, calls
   `PM_PlayerMove(true)`, then restores everything
   (`xash3d-vr-ports/Half-Life-VR/src/dlls/VRMovementHandler.cpp:12, 32-119`).
   It also replays `Touch()` on every entity the synthetic move hit
   (`:131-140`), which is what makes a dragged object push buttons and doors.

Why it matters: this single helper is the backbone of immersive ladders,
ledge pull, and dragging physics objects without teleporting through geometry.
It keeps stair stepping, water, ladders and trigger volumes working for free.

For us: Xash3D FWGS has the equivalent entry point on the server,
`SV_RunCmd` (`engine/server/sv_pmove.c:882`), which builds a `playermove_t`
from a `usercmd_t`. A "synthetic step" spike is the natural Xash3D translation
of `DoMovement`; the risk to check is client prediction drift, since we predict
the same displacement rather than only committing it server-side.

### 3.2 Ladders: two modes, both with hacks that matter

`vr_ladder_mode` has three values: `Combined`, `ImmersiveOnly`,
`LegacyOnly` (`xash3d-vr-ports/Half-Life-VR/src/pm_shared/pm_defs.h:34-36` and
`HLVRConfig/Utilities/Settings/ModSettings.cs`, ladder category).

- **Legacy climb is relative to the ladder plane, not the camera**
  (`pm_shared.cpp:2107-2225`): the climb/descend axis and the sideways axis are
  derived from the ladder's face normal, with separate console variables for
  climb speed and sideways speed. Sideways input otherwise walks you off.
- **A hysteresis rule keeps you attached**: when the hull no longer touches the
  ladder, the code checks whether the player is still within 8 units of the
  ladder center before dropping (`pm_shared.cpp:2258-2300`). The source
  comment is explicit that "the slightest head movements make the player fall
  off a ladder".
- **Immersive climb moves the player by the inverse of the hand delta**: while
  a controller drags `func_ladder`, the server sets `pmoveIgnoreLadders` and
  runs `DoMovement` from `origin + previousOffset - offset`
  (`dlls/VRControllerInteractionManager.cpp:1194-1251`). Releasing the ladder
  transfers `-controller.velocity` so you can swing off it.
- Ladder detection is extended 72 units above the ladder top so you can climb
  onto the ledge; the same constant widens the drag bbox
  (`dlls/VRControllerInteractionManager.cpp:253-272`).
- There is a dedicated `X_IN_LETLADDERGO` button so "let go" does not reuse
  jump, which in GoldSrc catapults you off the ladder
  (`common/in_buttons.h:38-41`).

Why it matters: our notes already record fragile ladder behaviour. These three
details (ladder-relative axes, 8-unit hysteresis, explicit let-go) are the
cheapest fixes and they are independent of the physics layer.

### 3.3 Extended buttons: they invented a second button word

`buttons_ex` was added to `usercmd_t`
(`xash3d-vr-ports/Half-Life-VR/src/common/usercmd.h:38`) for `X_IN_UP`,
`X_IN_DOWN`, `X_IN_VRDUCK` and `X_IN_LETLADDERGO`. This is required because
GoldSrc's 16-bit `buttons` field is full and because VR duck must be
distinguishable from stick duck inside the mover (see
`pm_shared.cpp:2056-2070`).

For us: we do not need a new word. Xash3D FWGS already reserves four
delta-encoded `int32` slots in `usercmd_t`
(`common/q_client.h:30-53`, encoded as `reserved[0..3]` in
`engine/common/net_encode.c:69-72`). Those slots are the natural home for VR
state bits and pose deltas.

### 3.4 Pose transport is their weakest engineering decision

Every frame the client writes three console commands: `vrupd_hmd` with ten
floats at two decimals, and two `vrupdctrl` lines with thirteen fields each
(`cl_dll/VRHelper.cpp:1227-1280`). The server keeps a timestamp and drops
updates that are not newer (`dlls/player.cpp`, `UpdateVRHeadset`, and
`dlls/VRController.cpp:90-98`).

Consequences visible in their own changelogs: "stuff lagging behind controller
when being picked up", "jitter bugs on hand and weapon models", "fixed issues
with input actions bound to both hands", plus a long series of level-change
and save/load offset bugs.

Two facts make the comparison concrete:

- The pose source for shooting is the **server**, via model attachments
  (`dlls/player.cpp:4763-4799`): `GetGunPosition()` returns
  `muzzle_pos`, `GetAutoaimVector()` returns `normalize(muzzle_pos2 -
  muzzle_pos)`, and autoaim is disabled entirely.
- Their client-side viewmodel is separately forced onto the controller
  transform every frame (`cl_dll/VRHelper.cpp:1282-1296`).

So the hand you see and the hand that shoots are two different pieces of state
joined by a lossy text channel. That is exactly the drift our D-002 decision
forbids.

Recommendation: keep a single pose source and send it to the server in the
usercmd reserved slots, quantized, so prediction and authority consume the same
bytes; keep only a compact absolute resync for spawn, teleport and level
change. Do not copy the command-per-frame design.

### 3.5 Interaction is a whitelist of contracts, not a generic grab

The interaction manager is a per-class dispatcher:
`HandleButtonsAndDoors`, `HandleRechargers`, `HandleTriggers`,
`HandleBreakables`, `HandlePushables`, `HandleAlliedMonsters`, `HandleGrabbables`,
`HandleLadders`, `HandleTossables`
(`dlls/VRControllerInteractionManager.h:44-53`,
`...InteractionManager.cpp:581-597`).

Filtering, in the order it runs
(`dlls/VRControllerInteractionManager.cpp:236-349`):

1. skip entities flagged as non-interacting unless explicitly draggable;
2. skip anything the player just threw, so you cannot re-hit your own grenade;
3. special-case `func_ladder` against a widened box;
4. **broad phase first**: reject by bounding-sphere distance before any model
   work (this fixed their "too many entities checked per frame" bug);
5. use the controller's own hitboxes, then MDL hitboxes of a dragged object.

Drag distance has a 64-unit tolerance constant (`:383`), and draggable
entities are an explicit classname list plus an `IsDraggable()` opt-in
(`:351-363`).

Why it matters: this is the same shape as our `interaction_contract`
(`physical_parts` / `scripted`) in `WEAPONS.md`. It also gives us a
performance rule to adopt before we grow the interaction surface.

### 3.6 Melee is a relative-velocity problem, solved server-side

`DoDamage` builds the swing velocity as controller velocity **plus** the
rotation-induced velocity of the hit point, then subtracts the victim's own
velocity: `speed = |player + swing + rot - entity|`
(`dlls/VRControllerInteractionManager.cpp:774-789`). Damage comes from a
weapon-and-speed table, the hit group comes from the real model hitbox, and a
per-class `BaseBalled()` hook applies knockback
(`:789-816`). Explosive weapons have a small chance to detonate when used as a
club (`:818-836`).

For us: our `vr_melee_swing` currently gates a swing; the relative-velocity
formulation is a better definition for both damage and "did I actually hit",
and it removes the "swing at nothing still triggers" class of bug. It also
reuses the MDL hitboxes we already load, so it does not need a physics engine.

### 3.7 Physics: reactphysics3d plus a per-map collision cache

They embed reactphysics3d (`src/reactphysics3d`) on the server and build a
collision world from BSP geometry:

- per-BSP-model triangle meshes cached in memory
  (`VRPhysicsHelper::m_bspModelData`);
- dynamic (moving brush) models kept separately;
- hitbox caches keyed by `(mins, maxs)` so identical hitboxes share a body;
- a player capsule body for "is this inside me" tests;
- a **binary per-map cache file** with magic, version and a hash of the BSP,
  plus a sanity check that rejects a partially loaded cache
  (`dlls/VRPhysicsHelper.cpp:860-985`).

Query API used by gameplay: `ModelIntersectsBBox`, `ModelIntersectsCapsule`,
`ModelIntersectsLine`, `BBoxIntersectsLine` (`dlls/VRPhysicsHelper.h`).

Why it matters for us: our roadmap defers Box3D. This project shows a staged
path where step 1 is *not* a physics engine: hitbox-accurate touch and melee
with the hitboxes we already have, and only then a collision cache if we ever
need real bodies. If we do reach that point, copy the cache design (magic,
version, BSP hash, sanity check) rather than the engine. Box3D already produces
that cache shape natively; see [`BOX3D.md`](BOX3D.md) for the dependency
evaluation and the staged plan that replaces reactphysics3d.

### 3.8 Hands and weapons: a model-authored attachment contract

This is the most directly reusable part of the study.

Attachment naming, verified by parsing the shipped MDL headers:

| Model | Helper bones / attachments |
|---|---|
| `art/models/v_hand_labcoat.mdl` (also shipped as `v_hand.mdl`) | `muzzle_pos`, `muzzle_pos2`, `hud_pos`, `hud_pos2`, `R_Arm_bone`; 31 bones total (arm chain + 5 fingers x 3); 9 sequences; 4 attachments |
| `art/models/v_9mmhandgun.mdl` | `Bip01 R Clavicle`/`UpperArm`/`Forearm`/`Hand`, `Hands mesh` 1-3, `muzzle_pos`, `muzzle_pos2`, `HUD_pos`, `HUD_pos2`, `BoxPistol` |
| `installer/payload/models/v_9mmhandgun.mdl` (BS-VR, replaced hands) | `Hands biped`, `Bone01`, `Bone02`, `muzzle_pos`, `muzzle_pos2`, `BoxGun`, `hud_pos`, `hud_pos2`, `Box02` |

The semantics are fixed by code, not by convention:

- attachment 0 = muzzle (`VR_MUZZLE_ATTACHMENT`,
  `cl_dll/VRHelper.cpp:1494-1506`);
- 0 and 1 together define the ballistic direction
  (`cl_dll/VRHelper.cpp:1508-1520`, `dlls/player.cpp:4784-4799`);
- 2 and 3 are the HUD anchor and HUD up vector
  (`cl_dll/VRHelper.cpp:1566-1590`);
- `Box*` bones are melee/touch colliders.

Because these live in the model, **there is no per-weapon alignment code**.
That is exactly the property our W4 acceptance asks for ("Magnum replication
with no per-weapon code"). Our `vr_weapons.json` already carries a per-weapon
socket; the natural evolution is to make the four attachments the contract and
demote numeric offsets to a fallback, mirroring the precedence we already have
for `grip_rot` versus Euler adjust.

Two more observations:

- **Weapon and hand models are server entities** with hitboxes and bodygroups:
  the bare hand swaps labcoat/hevsuit, uses bodygroup 3 for "flashlight on",
  and plays `FULLGRAB_START`/`FULLGRAB_END` while dragging
  (`dlls/VRController.cpp:225-268`). Making the hand a real entity is how they
  get lighting, shadows and touch for free.
- **Animated viewmodels are a separate model set** (`art/models/animov/`) behind
  `vr_use_animated_weapons`, and their own config text warns that it "affects
  aiming" (`HLVRConfig/Utilities/Settings/ModSettings.cs`). Our W3 goal should
  therefore state the aiming invariant explicitly: an animated viewmodel may
  not change the firing line.

Caveat: their hand assets are acknowledged as broken by the Blue Shift VR
README ("Hand models on weapons are mess"). Copy the rig and naming contract,
never the geometry.

### 3.9 Rendering: single-eye submission, world-space HUD, in-VR menus

- `vr_eye_mode` supports `Both`, `LeftOnly`, `RightOnly`, and two *mirrored*
  variants (`vr_shared/VRShared.h:21-29`). Submission for the mirrored modes
  reuses one eye texture for both eyes
  (`cl_dll/VRHelper.cpp:679-712`). This is aimed at players who effectively see
  with one eye; the same switch is our biggest fill-rate lever on Quest.
  Verification needed on our side: confirm that the second scene pass is
  actually skipped, otherwise the cost saving is zero.
- HUD is not a screen overlay. They intercept `SPR_Set`/`SPR_DrawAdditive` and
  redraw each HUD element as a world-space sprite with `vr_hud_mode`
  (`2` = on controllers, `1` = true HUD in view, `0` = off) plus per-element
  offsets and scale (`cl_dll/VRRenderer.h:12-23, 62`, settings groups
  `vr_hud_*`). Screen-space damage/pain gradients are separate.
- The menus render into a texture placed on a quad with `vr_menu_scale`,
  `vr_menu_opacity` and placement; the intermission has a dedicated room. Blue
  Shift VR goes further with a hex weapon wheel modelled on HL2VR
  (`Blue-Shift-VR/cl_dll/vr/VRWeaponWheel.cpp:24-45`).
- They keep two display-list render paths because the stock engine renderer is
  the bottleneck. That is not transferable to us.

### 3.10 Input: versioned action manifest with per-device defaults

`game/actions/` contains `actions.manifest`, a localized action name table
(`actions_en_us.json`), one default binding file per controller family
(Vive, Knuckles, Oculus Touch, WMR/holographic), and `customactions.cfg`. A
release note records adding a version to the manifest specifically to force a
rebind when the scheme changes (0.7.5-beta).

For us: our OpenXR action set should carry a version, ship per-controller
defaults, and treat remapping as a supported path rather than a cvar edit.

### 3.11 Settings: a declarative schema, not a pile of cvars

`HLVRConfig/Utilities/Settings/ModSettings.cs` is a single schema of roughly
130 settings: name, human label, type (`COUNT`, `SPEED`, `DISTANCE`, `FACTOR`),
default, allowed values, and inter-setting dependencies
(`SettingDependency("vr_ladder_mode", "1", MUST_NOT_MATCH)`). The same table
drives the UI, defaults, and the key/value settings file.

Half-Life-VR needs a Windows `.exe` to edit it; Blue Shift VR replaced that with
in-game VGUI2 pages (`Blue-Shift-VR/cl_dll/vr/VRSettingsPages.cpp`), which
removes the platform dependency and the settings drift.

Why it matters: our rule is "document every new cvar", and today that is manual.
A single declarative table could generate the VR menu, the docs table, and a
validation check, and would make D1 catch undocumented cvars mechanically.

### 3.12 Immersion and compatibility hacks worth cataloguing

They expose every engine/game incompatibility as a cvar instead of patching it
inside gameplay code:

- `vr_disable_func_friction` (no slippery surfaces), `vr_no_gauss_recoil`,
  `vr_make_levers_nonsolid`, `vr_make_mountedguns_nonsolid`,
  `vr_blastpit_fan_nonsolid` + `vr_blastpit_fan_delay`,
  `vr_semicheat_spinthingyspeed`, `vr_force_introtrainride`,
  `vr_dont_rotate_with_trains`, `vr_view_dist_to_walls`,
  `vr_rl_ducking_enabled`/`vr_rl_duck_height`, `vr_autocrouch_enabled`,
  `vr_smooth_steps`(+intensity), `vr_toggle_crouch`.
- NPC interactions: gunpoint reactions with a "get angry" level
  (`vr_npc_gunpoint` 0/1/2), grabbing a friendly NPC's shoulder to toggle
  follow/wait.
- Trains and mounted guns use "tank controls" with a max reach and an
  instant-turn toggle (`vr_tankcontrols` 0/1/2, `vr_tankcontrols_max_distance`,
  `vr_tankcontrols_instant_turn`).
- Teleporting makes AI-audible noise scaled by distance.
- Throwables: `vr_weapon_grenade_mode` chooses controller velocity versus
  aim-plus-fixed-speed; live snarks can be re-captured; thrown grenades can be
  picked up and thrown again.
- Audio: FMOD with per-material occlusion percentages (wall/door/water/glass).
  The idea (material-class occlusion expressed as a percentage) is portable
  even if the library is not.

### 3.13 Portability lessons from Blue Shift VR

- The VR subsystem survived the jump to the 25th Anniversary engine with
  mostly mechanical changes, plus `game_shared/vr/VRComModelHL25.h` and a
  BSP converter for the older Blue Shift maps. Owning the engine, as we do,
  removes this entire class of work.
- They added Linux makefiles for client, server and VGUI2, which contradicts
  the "no Linux support" line inherited from Half-Life-VR and confirms the
  limitation was tooling, not design.
- What they dropped is a good "minimum VR feature set" list: FMOD, speech
  recognition, Steam API/achievements, the external config tool, upscaled
  textures. The VR core (hands, weapons, movement, interaction, ladder,
  teleporter, HUD, menu) survived untouched.
- Defects they still accept and we should gate explicitly: Xen teleport
  insta-death, hand/weapon alignment, crash on launch or level change, save
  corruption, and "immersive ladders are hard to dismount".

## 4. What not to copy

| Item | Why |
|---|---|
| Pose sync through per-frame client commands | Lossy, un-predicted, and the source of their drift and lag bugs; we own the network path. |
| External settings executable | Platform-locked; we can generate an in-game menu from one table. |
| Display-list multipass renderer | Workaround for the stock engine; `ref/gl_vr` is already ours. |
| Generic magnet grab | They had to add distance tolerances and "just thrown" filtering to make it usable; explicit contracts age better. |
| Speech recognition, FMOD, Steam achievements as core features | Platform-locked and out of scope for Quest. |
| Their hand geometry | Acknowledged as broken upstream; copy the rig contract only. |
| Server as the ballistic pose source | Conflicts with D-002 and with client prediction. |

## 5. Proposed follow-ups

Ordered by expected value per unit of work. Sizes are rough.

| # | Proposal | Epic | Size | Evidence needed |
|---|---|---|---|---|
| 1 | `vr_eye_mode` with single-pass render and mirrored submission | E4/E5 | S | eye dump on Monado; Quest fill-rate measurement before any default change |
| 2 | Attachment contract `muzzle_pos`/`muzzle_pos2`/`hud_pos`/`hud_pos2` in `vr_weapons.json`, offsets demoted to fallback | E1/E3 | M | A8 naming check extended to attachments; W4 acceptance "no per-weapon code" |
| 3 | Move VR pose and button state into the `usercmd_t` reserved slots | E4 | M | R1 plus a network soak; must keep prediction identical |
| 4 | Declarative cvar schema that generates docs and the VR menu | E4 | M | D1 fails on an undocumented cvar |
| 5 | Ladder v2: ladder-relative axes, 8-unit hysteresis, explicit let-go button | E2/E4 | M | new Monado scene; does not need physics |
| 6 | Touch/melee from MDL hitboxes with relative-velocity damage | E2 | M | extends A7; new assertion for "swing at air deals no damage" |
| 7 | Immersion compatibility cvar set from 3.12 | E3 | S | R1 only |
| 8 | In-game settings pages fed by the same schema as #4 | E4 | L | depends on #4 |
| 9 | Synthetic player step (`SV_RunCmd`) for immersive ladder and dragging | E2/E4 | L | spike first; prediction drift is the risk |
| 10 | Box3D stages S0-S1: build target and cooked BSP queries, no bodies | E4 | L | see [`BOX3D.md`](BOX3D.md) |
| 11 | Per-map collision cache plus rigid bodies | deferred | XL | only if the Box3D deferral is lifted |

## 6. Open questions

1. Can Xash3D FWGS run a synthetic step through `SV_RunCmd` without disturbing
   the usercmd stream, and can client prediction replay it deterministically?
2. Does a single-eye mode actually halve the frame cost in `ref/gl_vr`, or is
   the second pass still submitted?
3. Do our current viewmodels have usable attachment slots, or does the native
   route need a new attachment contract?
4. How much of the settings schema is worth porting before the weapon epic
   unfreezes?

## 7. Method notes

- Sources read: `README.md`, `docs/release-notes.md`, `docs/dev-guide.md`,
  `docs/README.md` for both projects; the VR subsystems listed in section 3;
  `HLVRConfig/Utilities/Settings/ModSettings.cs`; `game/actions/`; the shipped
  MDL headers of the hand and 9mm handgun models.
- MDL header fields, bone and attachment names were read directly from the
  binary files with a throwaway parser, not from documentation.
- No VR mod code was executed. Statements about behaviour come from reading
  the code paths cited above; statements about user-visible effects come from
  the projects' own release notes.
