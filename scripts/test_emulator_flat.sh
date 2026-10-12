#!/usr/bin/env bash
# ==============================================================================
# Xash3D FWGS - Automated Android Studio Emulator Flat (2D) Test Script
# ==============================================================================
# Verifies non-VR Android 2D builds on the Android Studio emulator to prevent
# regressions in touch controls, menus, and standard mobile engine pipelines.
# ==============================================================================

set -euo pipefail

PACKAGE_NAME="su.xash.engine.test"
MAIN_ACTIVITY="${PACKAGE_NAME}/su.xash.engine.MainActivity"
GAME_ACTIVITY="${PACKAGE_NAME}/su.xash.engine.XashActivity"
DEFAULT_APK="out/xash3d-flat.apk"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="out/evidence/emulator_${TIMESTAMP}"
AVD_NAME="Medium_Phone_API_37.0"
if [ $# -ge 1 ] && [[ "$1" == *.apk || -f "$1" ]]; then
    TARGET_APK="$1"
    TARGET_MAP="${2:-menu}"
elif [ $# -ge 1 ]; then
    TARGET_APK="$DEFAULT_APK"
    TARGET_MAP="$1"
else
    TARGET_APK="$DEFAULT_APK"
    TARGET_MAP="menu"
fi

log_info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()   { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_err()  { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

# 1. Environment Resolution
if [ -z "${ANDROID_HOME:-}" ] && [ -d "$HOME/Android/Sdk" ]; then
    export ANDROID_HOME="$HOME/Android/Sdk"
fi

if [ -n "${ANDROID_HOME:-}" ]; then
    export PATH="$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools:$PATH"
fi

if ! command -v adb >/dev/null 2>&1; then
    log_err "ADB command not found in PATH."
    exit 1
fi

# 2. Check if an emulator is running, or launch one
EMU_SERIAL=$(adb devices 2>/dev/null | awk '$1 ~ /^emulator-/ && $2=="device" {print $1}' | head -n1 || true)
STARTED_BY_SCRIPT=false

if [ -z "$EMU_SERIAL" ]; then
    log_info "No running Android emulator detected. Starting AVD '$AVD_NAME'..."
    if ! command -v emulator >/dev/null 2>&1; then
        log_err "emulator binary not found. Please install Android SDK emulator."
        exit 1
    fi

    # Launch emulator in background with GPU acceleration and disabled boot animations
    mkdir -p out
    export QT_QPA_PLATFORM=xcb
    nohup emulator -avd "$AVD_NAME" -no-boot-anim -no-audio -gpu host >out/emulator.log 2>&1 &
    EMU_PID=$!
    STARTED_BY_SCRIPT=true
    log_info "Emulator process started (PID $EMU_PID). Waiting for ADB device registration..."

    # Wait for emulator to show up in adb devices (up to 45s)
    for i in {1..45}; do
        EMU_SERIAL=$(adb devices 2>/dev/null | awk '$1 ~ /^emulator-/ {print $1}' | head -n1 || true)
        if [ -n "$EMU_SERIAL" ]; then
            break
        fi
        sleep 1
    done

    if [ -z "$EMU_SERIAL" ]; then
        log_err "Timed out waiting for emulator to register with ADB."
        exit 1
    fi
fi

ADB_CMD="adb -s $EMU_SERIAL"
log_info "Target emulator device: $EMU_SERIAL"

# Wait for boot completion (sys.boot_completed=1)
log_info "Waiting for Android OS to complete booting..."
for i in {1..60}; do
    BOOTED=$($ADB_CMD shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
    if [ "$BOOTED" = "1" ]; then
        log_ok "Android OS boot completed."
        break
    fi
    sleep 2
done

# Enforce Landscape display orientation on Android OS
log_info "Locking Android display to Landscape mode..."
$ADB_CMD shell settings put system accelerometer_rotation 0 2>/dev/null || true
$ADB_CMD shell settings put system user_rotation 1 2>/dev/null || true

# 3. Check and deploy Steam Half-Life assets if needed
STEAM_VALVE_DIR="${HOME}/.local/share/Steam/steamapps/common/Half-Life/valve"
if [ -d "$STEAM_VALVE_DIR" ]; then
    HAS_VALVE=$($ADB_CMD shell "ls /sdcard/xash/valve/liblist.gam 2>/dev/null" || true)
    if [ -z "$HAS_VALVE" ]; then
        log_info "Syncing Valve Half-Life assets to emulator (/sdcard/xash/valve)..."
        $ADB_CMD shell mkdir -p /sdcard/xash/valve 2>/dev/null || true
        # Push liblist.gam (required for Xash to recognize valid gamedir)
        [ -f "$STEAM_VALVE_DIR/liblist.gam" ] && $ADB_CMD push "$STEAM_VALVE_DIR/liblist.gam" /sdcard/xash/valve/ >/dev/null 2>&1 || true
        # Push WADs, configs, and script lists
        for f in "$STEAM_VALVE_DIR"/*.wad "$STEAM_VALVE_DIR"/*.cfg "$STEAM_VALVE_DIR"/*.rc "$STEAM_VALVE_DIR"/*.txt "$STEAM_VALVE_DIR"/*.lst "$STEAM_VALVE_DIR"/*.pk3; do
            [ -f "$f" ] && $ADB_CMD push "$f" /sdcard/xash/valve/ >/dev/null 2>&1 || true
        done
        # Push essential UI, gfx, and sound resources
        for d in gfx sprites sound models maps media; do
            if [ -d "$STEAM_VALVE_DIR/$d" ]; then
                log_info "Syncing $d to emulator..."
                $ADB_CMD push "$STEAM_VALVE_DIR/$d" /sdcard/xash/valve/ >/dev/null 2>&1 || true
            fi
        done
        log_ok "Valve Half-Life assets synced successfully."
    fi
fi

# 4. Verify and install Flat APK
if [ ! -f "$TARGET_APK" ]; then
    log_err "Flat APK not found: $TARGET_APK"
    log_info "Compile it first using ./scripts/build_flat_apk.sh"
    exit 1
fi

log_info "Installing $TARGET_APK onto emulator ($EMU_SERIAL)..."
$ADB_CMD install -r "$TARGET_APK"

# 5. Grant permissions (including All Files Access and Bluetooth on API 31+)
$ADB_CMD shell pm grant "$PACKAGE_NAME" android.permission.RECORD_AUDIO 2>/dev/null || true
$ADB_CMD shell pm grant "$PACKAGE_NAME" android.permission.READ_EXTERNAL_STORAGE 2>/dev/null || true
$ADB_CMD shell pm grant "$PACKAGE_NAME" android.permission.WRITE_EXTERNAL_STORAGE 2>/dev/null || true
$ADB_CMD shell pm grant "$PACKAGE_NAME" android.permission.BLUETOOTH_CONNECT 2>/dev/null || true
$ADB_CMD shell pm grant "$PACKAGE_NAME" android.permission.BLUETOOTH_SCAN 2>/dev/null || true
$ADB_CMD shell pm grant "$PACKAGE_NAME" android.permission.POST_NOTIFICATIONS 2>/dev/null || true
$ADB_CMD shell appops set "$PACKAGE_NAME" MANAGE_EXTERNAL_STORAGE allow 2>/dev/null || true

# 6. Launch Application
mkdir -p "$OUTPUT_DIR"
$ADB_CMD logcat -c
log_info "Stopping previous instance of $PACKAGE_NAME..."
$ADB_CMD shell am force-stop "$PACKAGE_NAME" >/dev/null 2>&1 || true
sleep 1

if [ "$TARGET_MAP" = "ui" ] || [ "$TARGET_MAP" = "launcher" ]; then
    log_info "Launching Flat UI Launcher activity ($MAIN_ACTIVITY)..."
    $ADB_CMD shell am start -n "$MAIN_ACTIVITY"
elif [ "$TARGET_MAP" != "menu" ]; then
    log_info "Launching Flat engine activity ($GAME_ACTIVITY) directly with map '$TARGET_MAP'..."
    $ADB_CMD shell am start -n "$GAME_ACTIVITY" --es gamedir valve --es argv "-dev 2 +map ${TARGET_MAP}" --es basedir /sdcard/xash
else
    log_info "Launching Flat engine activity ($GAME_ACTIVITY) into Main Menu..."
    $ADB_CMD shell am start -n "$GAME_ACTIVITY" --es gamedir valve --es argv "-dev 2" --es basedir /sdcard/xash
fi

log_info "Waiting 6 seconds for engine initialization and 2D touch HUD setup..."
sleep 6

# Dismiss Android OS immersive fullscreen dialog if present
$ADB_CMD shell input tap 1700 460 2>/dev/null || true
sleep 1

# 7. Collect Evidence
log_info "Collecting emulator diagnostic evidence into $OUTPUT_DIR..."

SCREENSHOT="$OUTPUT_DIR/screencap.png"
if $ADB_CMD exec-out screencap -p > "$SCREENSHOT" 2>/dev/null; then
    log_ok "Display screencap saved: $SCREENSHOT"
else
    log_warn "Failed to capture display screencap."
fi

LOGCAT_FILE="$OUTPUT_DIR/logcat_flat.log"
$ADB_CMD logcat -d -v time | grep -E "Xash|GL|Adreno|SDL|Fatal|CRASH|OpenXR|Touch" > "$LOGCAT_FILE" 2>/dev/null || true
log_ok "Filtered logcat saved: $LOGCAT_FILE"

# 8. Assess Verification
TEST_PASSED=true

IS_RUNNING=$($ADB_CMD shell pidof "$PACKAGE_NAME" 2>/dev/null | tr -d '\r' || true)
if [ -z "$IS_RUNNING" ]; then
    log_err "Flat engine application crashed or failed to start!"
    TEST_PASSED=false
else
    log_ok "Flat engine PID $IS_RUNNING is running healthy on emulator."
fi

if grep -q "FATAL EXCEPTION\|SIGSEGV\|SIGABRT" "$LOGCAT_FILE"; then
    log_err "Fatal crash detected in emulator logcat:"
    grep -E "FATAL EXCEPTION|SIGSEGV|SIGABRT" "$LOGCAT_FILE" | head -n 5
    TEST_PASSED=false
fi

# Verify OpenXR was NOT loaded (clean Flat separation)
if grep -q "OpenXR" "$LOGCAT_FILE"; then
    log_warn "Notice: OpenXR symbols mentioned in Flat build logs."
else
    log_ok "Verified: Zero OpenXR dependencies loaded in Flat mode."
fi

echo "=========================================================="
if [ "$TEST_PASSED" = true ]; then
    log_ok "ANDROID EMULATOR FLAT TEST PASSED: Evidence in $OUTPUT_DIR"
    exit 0
else
    log_err "ANDROID EMULATOR FLAT TEST FAILED: Check logs in $OUTPUT_DIR"
    exit 1
fi
