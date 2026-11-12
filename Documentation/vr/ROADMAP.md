# Roadmap

This page is a short pointer. The single plan of truth is
[`PLAN.md`](PLAN.md); current state is in [`STATUS.md`](STATUS.md) and the gate
commands are in [`GATES.md`](GATES.md). Resolved issues remain in git history
and in the `pre-cleanup-2026-10-31` tag; they are not duplicated here.

## Epics

- **E1. Asset repair and hand/weapon presentation.** Make the VR viewmodels and
  hands presentable in the headset without changing the authoritative animation
  or breaking the grip pose. Gates: `A2`, `A3`, `A4`, `A5`, `A6`, `B1`, `M1`.
- **E2. Weapon interaction.** Physical reloading and weapon handling that feels
  intentional in VR. Gates: `A7`, `M1`, `R1`.
- **E3. Mod compatibility.** Let GoldSrc mods opt into VR without forking the
  engine. Gates: `A8`, `R1`.
- **E4. VR quality and engine integration.** Keep the OpenXR path stable while
  the VR renderer grows. Gates: `M1`, `R1`.
- **E5. Quest packaging and hardware validation.** Keep the standalone APK and
  Horizon OS launcher healthy. Gate: `Q1` (pending by default).

Stages, invariants, the blocker register and the exit criteria for each epic
are in [`PLAN.md`](PLAN.md).
