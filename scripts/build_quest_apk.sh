#!/bin/bash
# ==============================================================================
# Xash3D VR - Build Script for Meta Quest Standalone (Quest 1, 2, Pro, 3)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=========================================================="
echo "  Xash3D VR - Packaging Meta Quest Standalone APK"
echo "=========================================================="

if [ -z "$ANDROID_HOME" ] && [ -d "$HOME/Android/Sdk" ]; then
    export ANDROID_HOME="$HOME/Android/Sdk"
fi

if [ -z "$JAVA_HOME" ]; then
    if [ -d "/opt/android-studio/jbr" ]; then
        export JAVA_HOME="/opt/android-studio/jbr"
    else
        for jdk_candidate in "$HOME"/.gradle/jdks/*; do
            if [ -x "$jdk_candidate/bin/java" ]; then
                export JAVA_HOME="$jdk_candidate"
                break
            fi
        done
    fi
    if [ -n "$JAVA_HOME" ]; then
        export PATH="$JAVA_HOME/bin:$PATH"
    fi
fi

if [ -z "$ANDROID_HOME" ]; then
    echo "NOTICE: ANDROID_HOME is not currently configured."
    echo "To build the standalone APK, install the Android SDK and export:"
    echo "  export ANDROID_HOME=\$HOME/Android/Sdk"
    echo "  export ANDROID_NDK_HOME=\$ANDROID_HOME/ndk/<version>"
    echo ""
    echo "You can also build directly by opening the 'android/' directory"
    echo "in Android Studio and selecting 'Build -> Build APK(s)'."
fi

cd "${REPO_DIR}/android"

if [ -f "./gradlew" ]; then
    chmod +x ./gradlew
    echo "Invoking Gradle to package OpenXR standalone APK for Meta Quest devices..."
    ./gradlew assembleDebug -PenableVr=true --no-daemon || {
        echo "Error: Gradle build failed. Please verify your local Android NDK toolchain."
        exit 1
    }

    mkdir -p "${REPO_DIR}/out"
    find app/build/outputs/apk/ -name "*.apk" -exec cp {} "${REPO_DIR}/out/xash3d-vr-quest.apk" \;
    echo "SUCCESS! Meta Quest Standalone APK created: ${REPO_DIR}/out/xash3d-vr-quest.apk"
    echo "To install on your Meta Quest headset via USB or Wi-Fi ADB:"
    echo "  adb install -r ${REPO_DIR}/out/xash3d-vr-quest.apk"
else
    echo "Error: gradlew wrapper not found in android/ directory."
    exit 1
fi
