# Handoff: weapon bore / aim alignment (2026-11-12)

Read this before continuing the weapon work. It records what was tried, what
failed, why it failed, and the open questions the next implementer should
raise. The short version: **the shipped viewmodels were never authored for VR,
and no engine-side proxy vector can repair them.** Stop trying to compensate
in the renderer.

## Current state

- HEAD: `6b1ae8d8` lineage plus the D-031 commits. `vr_anchor_rotation` is
  now **0** by default (`engine/platform/openxr/xr_core.c`).
- `V3`, `R2` and M1 assertion 53 are **expected to FAIL**. That is the honest
  state: the simulator shows broken weapons and the tests say so.
- `F1` is a readiness manifest, `PROPOSED`, all candidates `validated: false`.
- Quest 3 HIL is **blocked** while `V3`/`R2` are red.
- Labelled evidence: `out/qa/V2/bore_fix_comparison.png` with an honest
  caption and `manifest.json` marked `REJECTED`.

## What was tried (chronology)

| Attempt | Reference | Result |
|---|---|---|
| Align `muzzle_pos -> muzzle_pos2` to the aim | D-024 | ~90 degree twist; the pair is the lateral muzzle-flash quad |
| Per-weapon `bore_axis` from QC `$hbox` axes in JSON | retired `B1` | model-space vector injected into world-space bone math |
| Runtime `grip -> muzzle` bone vector | D-027 | wrist-to-tip diagonal, not the barrel |
| Offline mesh PCA as ground truth | abandoned | `mdldec` triangle vertices are in a DIFFERENT coordinate space from the skeleton (MP5: mesh X `[-0.9,19.6]` vs `muzzle_pos` bone X `-37.8`) |
| `muzzle_pos -> hud_pos` aligned to aim | D-030 | rotated every bone 33-94 degrees, detached the baked hand; `V3`/`R2` green was tautological |
| Swap SD assets for HL:VR originals | `S0.5` | checksums proved our MDLs ARE the HL:VR SD variants; MP5 original improved 18.6 -> 10.0 degrees, still above the 8-degree criterion |

Measured `[VR_BORE]` corrections before D-031: Glock 52.3, MP5 69.4,
shotgun 54.7, RPG 73.7, tripmine 94.3, crossbow 33.0 degrees.

## Root cause (facts)

- The shipped native MDLs are byte-identical to the HL:VR **SD** variants
  (`839aa7aa1300` / `e70a29b943aa`). They were authored for flat-screen play.
- No vector inside these MDLs is canonically the visible barrel:
  - `muzzle_pos -> muzzle_pos2`: flash quad / the reference mods' ballistics
    convention, 4.8-87 degrees from `muzzle -> hud` depending on the model;
  - `muzzle_pos -> hud_pos`: internal rig anchor;
  - `grip -> muzzle`: wrist-to-tip diagonal;
  - `$hbox`: body cross-section (on the Glock it is the slide cross-section);
  - mesh vertices: wrong coordinate space.
- Only 2 of 17 HL:VR original viewmodels have `par ~= muzzle->hud` by the
  criterion we were using, which means **that criterion was invalid too** --
  not that the originals are bad. There is no measured "VR-ready" label yet.
- The reference mods do not compute a bore axis. `VRHelper::UpdateViewEnt`
  (`xash3d-vr-ports/Half-Life-VR/src/cl_dll/VRHelper.cpp:1282-1297`) copies
  controller position/angles into the viewmodel and their models are authored
  with the barrel on that basis. `REFERENCE_PORTS.md:425-429` already said
  there is no bore solution to copy, only the decoupling.
- `vibe-life-vr/Documentation/vr/reference/REFERENCE_PORTS.md` section 3.14
  and session `ses_e333b9c6affek2XP6wGBR3KjrF` reached the same conclusion.
  This is a recurring wall, not a new finding.

## Inference

`V3` and `R2` were green because the renderer forced `attachment[0] -
attachment[2]` onto the aim ray and the gate then measured that same vector.
The image `out/qa/V2/bore_fix_comparison.png` shows the truth: MP5 inclined
~40 degrees, baked hand detached, green laser leaving diagonally. Any gate
whose measured quantity is produced by the code under test is a false
positive. A green simulator with a broken weapon is worse than no test.

## Decided direction (D-031)

1. **Stop compensating.** `vr_anchor_rotation` OFF. The viewmodel follows the
   controller pose. `R_VR_RotateViewmodelToPalm` remains only as an A/B switch
   for asset preparation, never as a runtime fix.
2. **Treat this as an asset problem.** For Bronze/Silver mods, render a
   VR-ready fallback viewmodel **per weapon class**, while the mod keeps its
   own damage, fire rate, animations, sounds and ballistics. Do not try to
   repair the mod's own viewmodel.
3. **`F1` is the mechanism, not the solution.**
   `assets/valve_vr/models/vr_fallback.json` lists candidate sources with
   checksums. It is `PROPOSED`, `human_decision: PENDING`, every candidate
   `validated: false`. Engine-side model substitution is NOT implemented.
4. **Acceptance is visual.** One labelled fixed-camera comparison sheet per
   weapon class with maintainer `ADVANCE`, then a fresh `V3`/`R2` at that
   commit. Numeric gates may only verify independent invariants.

## Points the next harness should criticise

- Are the `F1` candidates actually VR-ready, or just another mod's
  flat-screen assets? The only measured one (MP5 original) gave 10.0 degrees,
  still failing. **No candidate has passed a visual sheet.** Do not adopt any
  on the strength of this document.
- Does swapping the render model break the mod's viewmodel animations,
  bodygroups, events, muzzle flashes or prediction? A fallback by class is a
  coarse mapping; `weapon_x -> class` needs a real table per gamedir.
- Licensing/credits: before adopting any third-party MDL, add source URL and
  author credit to `assets/valve_vr/CREDITS.md` (project rule, section 8).
- Is `vr_anchor_rotation` persisted as 1 in existing configs (`FCVAR_ARCHIVE`)?
  A stale config could silently re-enable the harmful rotation. Check
  `vr_defaults.cfg` and any user config before claiming D-031 is active.
- Should `V3`'s metric be replaced entirely by an image-based check? The
  current telemetry still measures an internal attachment vector. An honest
  gate would compare the rendered weapon silhouette/laser pixels against the
  aim ray, with a negative control on a known-bad capture.
- `R2` (roll sweep) and `P2`/`P3` still carry D-030 vocabulary
  ("authored two-point barrel basis"). Rename or retire before reuse.
- With D-031 the `[VR_AIM]` samples are still UNSTABLE for the Glock
  (`[0.0, 52.3]`) and MP5 (`[0.0, 69.4, 69.4]`): some frames report 0.0
  degrees while the asset geometry is clearly off. Find the source of those
  0.0 frames before trusting any numeric alignment gate; `vr_hide_arms 2` is
  already excluded, so it is something else (stale attachments on equip, or a
  persisted `vr_anchor_rotation=1` in a user config).
- The `out/qa/V2/bore_fix_comparison.png` BEFORE frame is from an older M1 run
  with different cvars. A proper comparison needs BOTH frames from the same
  fixed camera and the same pose.

## Concrete next steps

1. Verify `vr_anchor_rotation` is 0 in the actual running config; capture a
   fresh BEFORE frame with the same fixed camera and pose as the AFTER frame.
2. Pick ONE class (pistol). Stage one candidate MDL under a new
   `assets/valve_vr/models/vr_ready/` path, add credits, and produce a labelled
   fixed-camera sheet. Get maintainer `ADVANCE` before wiring anything.
3. Only after approval: implement per-gamedir `weapon -> fallback model`
   resolution (`XR_ReloadWeaponProfiles()` already searches
   `<gamedir>_vr/models/vr_weapons.json` first,
   `engine/platform/openxr/xr_profile.c:1042-1053`) and cover it with a gate
   that does NOT measure a vector produced by the renderer.
4. Re-run the full battery at the new commit. Do not mark `V3`/`R2` PASS from
   an older run and do not relax the 8-degree / `in_front=1` thresholds.
5. Keep the independent gates: M1 1-52, `T1`, `P1`, `S1`, `S2`, `A2`, `A3`,
   `A5`, `A6`, `A8`, `D1`, `H1`. They do not depend on the bore claim.

## What NOT to do

- Do not reintroduce Euler trims (`pitch_adjust`), hitbox axes or mesh PCA as
  the barrel reference.
- Do not add a fifth attachment or change `cl_entity_t.attachment[4]`: it sits
  mid-struct and Bronze/Silver mod DLLs are untouched
  (`MOD_COMPATIBILITY.md:84`).
- Do not mark Quest 3 HIL unblocked while `V3`/`R2` are red.
- Do not treat an `F1` exit 0 as "weapons work": it only validates the JSON.

## Verification commands (read-only)

```sh
python3 scripts/progress_report.py
python3 scripts/check_vr_fallback.py --manifest assets/valve_vr/models/vr_fallback.json
python3 scripts/check_weapon_alignment.py --log out/qa/M1/latest/monado_unittest_engine.log --ground-truth out/qa/P2/bore_ground_truth.json
python3 scripts/check_docs.py
```
