---
description: Rebuild the Meta Quest APK from current sources
agent: build
---

Rebuild the standalone Quest APK from the current working tree.

1. Run `./scripts/build_quest_apk.sh` from the repository root.
2. Confirm the Gradle externalNativeBuild step refreshed the arm64-v8a native
   libraries in `android/app/src/main/jniLibs/arm64-v8a/`. Compare their
   timestamps with the newest source file under `engine/`, `ref/`, or
   `3rdparty/` that changed.
3. Report the APK path and size, the native library timestamps, and any build
   warnings or errors.

Do not install the APK or deploy assets unless I ask.
