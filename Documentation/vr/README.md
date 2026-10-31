# Vibe-Life VR documentation

This directory is the canonical documentation for the VR port. Start with
[`STATUS.md`](STATUS.md); it tells you what is current, what is blocked and what
to do next.

## Canonical set

| Document | Read it when |
|---|---|
| [`STATUS.md`](STATUS.md) | You need the current commit, gate results or blockers |
| [`ROADMAP.md`](ROADMAP.md) | You need the active epics and their order |
| [`GATES.md`](GATES.md) | You are running or reviewing a gate |
| [`TESTING.md`](TESTING.md) | You need build, Monado, regression or Quest commands |
| [`ASSETS.md`](ASSETS.md) | You are changing a viewmodel, hand or weapon profile |
| [`UPSTREAM.md`](UPSTREAM.md) | You are adopting an upstream change |
| [`DECISIONS.md`](DECISIONS.md) | You need the reason behind an architectural rule |
| [`reference/MOD_COMPATIBILITY.md`](reference/MOD_COMPATIBILITY.md) | You are targeting a GoldSrc mod |
| [`reference/MODDER_GUIDE.md`](reference/MODDER_GUIDE.md) | You are integrating a mod or asset pack |

## Architecture in one screen

```text
engine/platform/openxr/   instance, session, action sets, swapchains, input
ref/gl_vr/                stereo renderer, viewmodel, hands, VR UI, debug
engine/client/            client integration and prediction
engine/server/            authoritative ballistics and gameplay bridge
assets/valve_vr/          overlay viewmodels, v_hand.mdl, vr_weapons.json
android/                  Horizon OS launcher and APK packaging
scripts/                  build, test, asset and QA tooling
Documentation/vr/         this documentation set
```

The flat `ref_gl` renderer is not the VR path. The VR path is `ref_gl_vr`.

## Current baseline

- Monado unit suite: 44 assertions.
- Regression battery: 19 assertions.
- Evidence root: `out/qa/`.
- Quest hardware validation: maintainer decision, pending by default.

Exact commands and pass rules live in [`GATES.md`](GATES.md) and
[`TESTING.md`](TESTING.md). Do not duplicate gate commands in other documents.

## Documentation rules

- Use relative paths only. Never use absolute host paths or `file://` links.
- Keep code comments and docstrings in English.
- Do not rewrite upstream documentation under `Documentation/` outside this
  directory.
- When a gate changes, update its row in `GATES.md`; do not create a per-gate
  specification document.
- When a decision changes, add an entry to `DECISIONS.md` instead of editing
  the old rationale.
