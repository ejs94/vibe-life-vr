#!/bin/bash
# ==============================================================================
# Xash3D FWGS - Build Script for Standard Android Phones & Tablets (Flat / Non-VR)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=========================================================="
echo "  Xash3D FWGS - Packaging Standard Flat Android APK"
echo "=========================================================="

if [ -z "$ANDROID_HOME" ] && [ -d "$HOME/Android/Sdk" ]; then
    export ANDROID_HOME="$HOME/Android/Sdk"
fi

if [ -z "$JAVA_HOME" ]; then
    if [ -d "/opt/android-studio/jbr" ]; then
        export JAVA_HOME="/opt/android-studio/jbr"
        export PATH="$JAVA_HOME/bin:$PATH"
    fi
fi

if [ -z "$ANDROID_HOME" ]; then
    echo "NOTICE: ANDROID_HOME is not currently configured."
    echo "To build the standalone APK, install the Android SDK and export:"
    echo "  export ANDROID_HOME=\$HOME/Android/Sdk"
    echo "  export ANDROID_NDK_HOME=\$ANDROID_HOME/ndk/<version>"
fi

cd "${REPO_DIR}/android"

if [ -f "./gradlew" ]; then
    chmod +x ./gradlew
    echo "Invoking Gradle to package standard flat Android APK (Non-VR)..."
    ./gradlew assembleDebug -PenableVr=false --no-daemon || {
        echo "Error: Gradle build failed. Please verify your local Android NDK toolchain."
        exit 1
    }

    mkdir -p "${REPO_DIR}/out"
    find app/build/outputs/apk/ -name "*.apk" -exec cp {} "${REPO_DIR}/out/xash3d-flat.apk" \;
    echo "SUCCESS! Flat Android APK created: ${REPO_DIR}/out/xash3d-flat.apk"
    echo "To install on your Android device via ADB:"
    echo "  adb install -r ${REPO_DIR}/out/xash3d-flat.apk"
else
    echo "Error: gradlew wrapper not found in android/ directory."
    exit 1
fi
