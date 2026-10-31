# Vibe-Life VR

**Half-Life VR powered by Xash3D FWGS and OpenXR.**

Vibe-Life VR is a native OpenXR port of the Xash3D FWGS engine. It targets Meta
Quest standalone (Horizon OS, Android arm64-v8a) and Linux PCVR (Monado, WiVRn
and SteamVR) from one C99 codebase. The dedicated `ref_gl_vr` renderer owns the
stereo eye path, the 6DoF weapon viewmodel, hand presence, and the VR UI.

> This is a non-commercial community mod. Third-party asset credits live in
> [`assets/valve_vr/CREDITS.md`](assets/valve_vr/CREDITS.md).

## Quick start

Desktop Linux PCVR:

```sh
./waf configure --enable-openxr --enable-gl-vr
./waf build
./waf install --destdir=./out
./scripts/test_simulated_monado.sh
```

Meta Quest standalone:

```sh
./scripts/build_quest_apk.sh
adb install -r out/xash3d-vr-quest.apk
./scripts/deploy_quest_assets.sh valve /sdcard/xash
```

Quest validation is optional and is decided by the maintainer for each stage.
The default local gate is the simulated Monado suite.

## Documentation

Start with [`Documentation/vr/STATUS.md`](Documentation/vr/STATUS.md). The
canonical documentation set is:

| Document | Purpose |
|---|---|
| [`STATUS.md`](Documentation/vr/STATUS.md) | Current commit, gate results, blockers, next steps |
| [`ROADMAP.md`](Documentation/vr/ROADMAP.md) | Active epics and order of work |
| [`GATES.md`](Documentation/vr/GATES.md) | Single gate registry: command, evidence and device mode |
| [`TESTING.md`](Documentation/vr/TESTING.md) | Build, Monado, regression, Quest and evidence workflow |
| [`ASSETS.md`](Documentation/vr/ASSETS.md) | Viewmodels, hands, MMOD, asset repair pipeline and credits |
| [`UPSTREAM.md`](Documentation/vr/UPSTREAM.md) | Upstream sync policy and audit commands |
| [`DECISIONS.md`](Documentation/vr/DECISIONS.md) | Architecture and process decisions |
| [`reference/MOD_COMPATIBILITY.md`](Documentation/vr/reference/MOD_COMPATIBILITY.md) | GoldSrc mod compatibility tiers |
| [`reference/MODDER_GUIDE.md`](Documentation/vr/reference/MODDER_GUIDE.md) | Modder integration contract |

`AGENTS.md` contains the rules for coding agents working in this repository.
Upstream Xash3D documentation under `Documentation/` is read-only; it is not
part of this project's documentation set.

## Repository map

```text
engine/platform/openxr/   OpenXR instance, session, input, swapchains
ref/gl_vr/                dedicated stereo renderer and viewmodel handling
engine/client/            client integration and prediction
engine/server/            authoritative ballistics and gameplay bridge
assets/valve_vr/          VR overlay models, weapon profiles and credits
android/                  Horizon OS launcher and APK packaging
scripts/                  build, test, asset, QA and upstream tooling
Documentation/vr/         project documentation
```

## Evidence

Every gate writes to `out/qa/<gate-id>/`. The file
`out/qa/INDEX.md` lists the newest result per gate, and
`out/qa/<gate-id>/latest` points at the newest run. Generated evidence is not
committed.

## License and credits

The engine and game code retain their upstream licenses. The VR overlay assets
and their provenance are documented in
[`assets/valve_vr/CREDITS.md`](assets/valve_vr/CREDITS.md).
