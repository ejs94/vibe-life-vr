#!/bin/bash
# ==============================================================================
# Xash3D VR - Automated Meta Quest Standalone VR Verification Test Script
# ==============================================================================
# Automates end-to-end Standalone Quest validation:
#   1. Checks headset connection and battery/thermal health.
#   2. Wakes display and bypasses proximity sensor sleep.
#   3. Installs standalone OpenXR APK (out/xash3d-vr-quest.apk).
#   4. Grants required storage and device permissions.
#   5. Launches VR engine session into target map with bounded timeout.
#   6. Analyzes logcat for OpenXR loader, session lifecycle, and frame loop.
# ==============================================================================

set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${REPO_DIR}/out/evidence/quest_$(date +%Y%m%d_%H%M%S)"
TIMEOUT_SECS="${1:-35}"
TARGET_MAP="${2:-crossfire}"
PACKAGE_NAME="su.xash.engine.vr.test"
ACTIVITY_NAME="su.xash.engine.XashActivity"
APK_PATH="${REPO_DIR}/out/xash3d-vr-quest.apk"

log_info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()   { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_err()  { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

if ! command -v adb >/dev/null 2>&1 && [ -d "$HOME/Android/Sdk/platform-tools" ]; then
    export PATH="$HOME/Android/Sdk/platform-tools:$PATH"
fi

if ! command -v adb >/dev/null 2>&1; then
    log_err "ADB command not found. Ensure Android SDK platform-tools are in PATH."
    exit 1
fi

DEV_COUNT=$(adb devices 2>/dev/null | awk 'NR>1 && $2=="device"' | wc -l || true)
if [ "$DEV_COUNT" -eq 0 ]; then
    log_err "No authorized Meta Quest device detected via ADB."
    exit 1
fi

if [ ! -f "$APK_PATH" ]; then
    log_err "Standalone APK missing: $APK_PATH. Run ./scripts/build_quest_apk.sh first."
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# 1. Battery & Thermals check
if [ -f "${SCRIPT_DIR}/quest_battery.sh" ]; then
    "${SCRIPT_DIR}/quest_battery.sh" display || true
fi

# 2. Wake headset display, bypass proximity sleep, and clear competing VR apps
log_info "Waking headset display, disabling proximity sleep, and clearing competing VR sessions..."
adb shell input keyevent 224 2>/dev/null || true
adb shell input keyevent 82 2>/dev/null || true
adb shell svc power stayon true >/dev/null 2>&1 || true
adb shell am broadcast -a com.oculus.vrpowermanager.automation_disable >/dev/null 2>&1 || true
adb shell am broadcast -a com.oculus.vrpowermanager.prox_close >/dev/null 2>&1 || true
adb shell am force-stop org.meumeu.wivrn >/dev/null 2>&1 || true
adb shell setprop debug.oculus.guardian_pause 1 >/dev/null 2>&1 || true
adb shell input keyevent 4 2>/dev/null || true

# 3. Install APK
log_info "Installing Quest Standalone APK: $APK_PATH..."
adb install -r "$APK_PATH" >/dev/null 2>&1 || {
    log_err "Failed to install APK via ADB."
    exit 1
}
log_ok "APK installed successfully."

# 4. Grant runtime permissions
log_info "Granting application permissions..."
adb shell appops set "$PACKAGE_NAME" MANAGE_EXTERNAL_STORAGE allow >/dev/null 2>&1 || true
adb shell pm grant "$PACKAGE_NAME" android.permission.RECORD_AUDIO >/dev/null 2>&1 || true
adb shell pm grant "$PACKAGE_NAME" android.permission.BLUETOOTH_CONNECT >/dev/null 2>&1 || true

# 5. Clear logcat and prepare background capture
log_info "Clearing logcat buffer..."
adb logcat -c

LOGCAT_FILE="${OUTPUT_DIR}/logcat_quest.log"
adb logcat -v time > "$LOGCAT_FILE" 2>&1 &
LOGCAT_PID=$!

# 6. Launch Standalone VR engine
log_info "Launching Xash3D VR Activity (${ACTIVITY_NAME}) on map '${TARGET_MAP}'..."
adb shell "am start -a android.intent.action.MAIN -c com.oculus.intent.category.VR -n ${PACKAGE_NAME}/${ACTIVITY_NAME} --es gamedir valve --es argv '-dev 2 +map ${TARGET_MAP}' --es basedir /sdcard/xash" >/dev/null 2>&1

# 7. Monitor execution for bounded duration
log_info "Monitoring Standalone VR execution for ${TIMEOUT_SECS} seconds..."
RUNNING=false
for i in $(seq 1 "$TIMEOUT_SECS"); do
    sleep 1
    if adb shell "pidof ${PACKAGE_NAME}" >/dev/null 2>&1; then
        RUNNING=true
    fi
done

# Try capturing in-headset eye swapchain dump if available
if adb shell "test -f /sdcard/xash/vr_eye0.ppm" >/dev/null 2>&1; then
    log_info "Pulling vr_eye0.ppm from headset storage..."
    adb pull /sdcard/xash/vr_eye0.ppm "${OUTPUT_DIR}/vr_eye0.ppm" 2>/dev/null || true
    adb shell "rm -f /sdcard/xash/vr_eye0.ppm" 2>/dev/null || true
fi

# 8. Force stop activity and terminate logcat collector
log_info "Stopping application and finalizing logs..."
adb shell am force-stop "$PACKAGE_NAME" >/dev/null 2>&1 || true
kill "$LOGCAT_PID" 2>/dev/null || true
wait "$LOGCAT_PID" 2>/dev/null || true

# 9. Evaluate test evidence
TEST_PASSED=true

if [ "$RUNNING" != true ]; then
    log_err "Application failed to run or crashed immediately upon start."
    TEST_PASSED=false
fi

if grep -iq "xrInitializeLoaderKHR initialized successfully" "$LOGCAT_FILE" 2>/dev/null; then
    log_ok "Verified: OpenXR Android loader initialized successfully."
else
    log_err "Failed: xrInitializeLoaderKHR was not called or failed."
    TEST_PASSED=false
fi

if grep -iq "xrCreateInstance" "$LOGCAT_FILE" 2>/dev/null && ! grep -iq "xrCreateInstance failed" "$LOGCAT_FILE" 2>/dev/null; then
    log_ok "Verified: OpenXR instance created on Meta Quest."
fi

if grep -iq "OpenGL ES Meta Quest Standalone Graphics Binding initialized successfully" "$LOGCAT_FILE" 2>/dev/null; then
    log_ok "Verified: OpenGL ES Quest graphics binding accepted by compositor."
fi

if grep -iq "XrSession created" "$LOGCAT_FILE" 2>/dev/null; then
    log_ok "Verified: OpenXR session created."
fi

if grep -iq "Stereo swapchains created" "$LOGCAT_FILE" 2>/dev/null; then
    log_ok "Verified: Hardware stereo swapchains created."
fi

if grep -iq "xrBeginSession started successfully\|R_SetupXREyeFbos" "$LOGCAT_FILE" 2>/dev/null; then
    log_ok "Verified: VR frame loop active and rendering to Quest panels."
fi

if grep -iq "Fatal signal\|DEBUG   : crash" "$LOGCAT_FILE" 2>/dev/null; then
    log_err "Fatal native crash detected in Quest execution:"
    grep -E "Fatal signal|backtrace:" "$LOGCAT_FILE" | head -n 10 || true
    TEST_PASSED=false
fi

echo "=========================================================="
if [ -f "${SCRIPT_DIR}/quest_battery.sh" ]; then
    log_info "Post-test Battery Status:"
    "${SCRIPT_DIR}/quest_battery.sh" display || true
fi

if [ "$TEST_PASSED" = true ]; then
    log_ok "QUEST STANDALONE VR TEST PASSED: Evidence captured in ${OUTPUT_DIR}"
    exit 0
else
    log_err "QUEST STANDALONE VR TEST FAILED: Check logs in ${OUTPUT_DIR}"
    exit 1
fi
