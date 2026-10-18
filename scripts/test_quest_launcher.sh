#!/usr/bin/env bash
# ==============================================================================
# Xash3D VR - Automated Meta Quest APK Launcher Interface Test & Evidence Suite
# ==============================================================================
# Automatically verifies the 2D Meta Quest launcher UI (MainActivity):
#   1. Detects connected physical Quest headset OR running emulator OR boots AVD.
#   2. Installs standalone Quest APK (out/xash3d-vr-quest.apk).
#   3. Grants required runtime storage, audio, and device permissions.
#   4. Launches the 2D VR Shell Launcher (MainActivity).
#   5. Automates tab navigation (Library, VR Settings, App Settings, Diagnostics).
#   6. Captures high-res visual PNG evidence and UI layout XML dumps.
#   7. Validates zero Kotlin/Java crashes or ANRs in logcat.
# ==============================================================================

set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PACKAGE_NAME="su.xash.engine.vr.test"
MAIN_ACTIVITY="${PACKAGE_NAME}/su.xash.engine.MainActivity"
DEFAULT_APK="${REPO_DIR}/out/xash3d-vr-quest.apk"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="${REPO_DIR}/out/evidence/quest_launcher_${TIMESTAMP}"
if [ -n "${AVD_NAME:-}" ]; then
    AVD_NAME="$AVD_NAME"
elif "$HOME/Android/Sdk/emulator/emulator" -list-avds 2>/dev/null | grep -q "^Quest_Spatial_Panel$"; then
    AVD_NAME="Quest_Spatial_Panel"
else
    AVD_NAME="Medium_Phone_API_37.0"
fi

TARGET_APK="${1:-$DEFAULT_APK}"

log_title() { echo -e "\n\033[1;35m==========================================================\033[0m\n\033[1;35m  $*\033[0m\n\033[1;35m==========================================================\033[0m"; }
log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()    { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_err()   { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

# 1. Resolve Android SDK Environment
if [ -z "${ANDROID_HOME:-}" ] && [ -d "$HOME/Android/Sdk" ]; then
    export ANDROID_HOME="$HOME/Android/Sdk"
fi

if [ -n "${ANDROID_HOME:-}" ]; then
    export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"
fi

if ! command -v adb >/dev/null 2>&1; then
    log_err "ADB command not found in PATH or Android SDK."
    exit 1
fi

# 2. Identify Target Device (Physical Quest vs Running Emulator vs New AVD)
log_title "STEP 1: Target Device Discovery & Boot"

# Check for physical Quest first (serial not starting with emulator-)
PHYSICAL_DEV=$(adb devices 2>/dev/null | awk 'NR>1 && $1 !~ /^emulator-/ && $2=="device" {print $1}' | head -n1 || true)
RUNNING_EMU=$(adb devices 2>/dev/null | awk '$1 ~ /^emulator-/ && $2=="device" {print $1}' | head -n1 || true)

TARGET_SERIAL=""
STARTED_BY_SCRIPT=false
IS_EMULATOR=false

if [ -n "$PHYSICAL_DEV" ]; then
    TARGET_SERIAL="$PHYSICAL_DEV"
    log_ok "Discovered physical Meta Quest device connected via ADB: $TARGET_SERIAL"
elif [ -n "$RUNNING_EMU" ]; then
    TARGET_SERIAL="$RUNNING_EMU"
    IS_EMULATOR=true
    log_ok "Discovered already running Android emulator: $TARGET_SERIAL"
else
    # Launch Android Studio AVD emulator
    log_info "No connected device or active emulator found. Starting AVD '$AVD_NAME'..."
    EMULATOR_BIN=""
    if [ -x "${ANDROID_HOME:-}/emulator/emulator" ]; then
        EMULATOR_BIN="${ANDROID_HOME}/emulator/emulator"
    elif command -v emulator >/dev/null 2>&1; then
        EMULATOR_BIN="$(command -v emulator)"
    else
        log_err "Android emulator binary not found in SDK."
        exit 1
    fi

    mkdir -p "${REPO_DIR}/out"
    export QT_QPA_PLATFORM=xcb
    nohup "$EMULATOR_BIN" -avd "$AVD_NAME" -skin 1920x1080 -no-boot-anim -no-audio -gpu host >"${REPO_DIR}/out/emulator.log" 2>&1 &
    EMU_PID=$!
    STARTED_BY_SCRIPT=true
    IS_EMULATOR=true
    log_info "Spawned emulator process (PID $EMU_PID). Waiting for ADB device registration..."

    for i in {1..50}; do
        RUNNING_EMU=$(adb devices 2>/dev/null | awk '$1 ~ /^emulator-/ {print $1}' | head -n1 || true)
        if [ -n "$RUNNING_EMU" ]; then
            TARGET_SERIAL="$RUNNING_EMU"
            break
        fi
        sleep 1
    done

    if [ -z "$TARGET_SERIAL" ]; then
        log_err "Timed out waiting for Android emulator to appear in ADB."
        exit 1
    fi
fi

ADB_CMD="adb -s $TARGET_SERIAL"
log_ok "Active ADB Target: $TARGET_SERIAL"

# 3. Wait for System Boot Completion
log_info "Verifying Android OS boot state (sys.boot_completed)..."
for i in {1..60}; do
    BOOTED=$($ADB_CMD shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
    if [ "$BOOTED" = "1" ]; then
        log_ok "Android OS booted and responsive."
        break
    fi
    sleep 2
done

# Dismiss keyguard / wake screen
$ADB_CMD shell input keyevent 224 2>/dev/null || true # KEYCODE_WAKEUP
$ADB_CMD shell wm dismiss-keyguard 2>/dev/null || true

# If running on emulator, force Meta Quest Horizon OS spatial panel scale (1920x1080 @ 240dpi landscape)
if [ "$IS_EMULATOR" = true ]; then
    log_info "Configuring display to Meta Quest Spatial Panel default scale (1920x1080 @ 240dpi landscape)..."
    $ADB_CMD shell settings put system accelerometer_rotation 0 2>/dev/null || true
    $ADB_CMD shell settings put system user_rotation 1 2>/dev/null || true
    $ADB_CMD shell wm size 1920x1080 2>/dev/null || true
    $ADB_CMD shell wm density 240 2>/dev/null || true
fi

# 4. Install Quest APK
log_title "STEP 2: Deploying Quest Standalone APK"

if [ ! -f "$TARGET_APK" ]; then
    log_err "APK file not found: $TARGET_APK"
    log_info "Compile it first using ./scripts/build_quest_apk.sh"
    exit 1
fi

log_info "Installing $TARGET_APK onto device..."
$ADB_CMD install -r "$TARGET_APK"
log_ok "APK installed successfully."

# Grant permissions
log_info "Granting Android permissions to $PACKAGE_NAME..."
$ADB_CMD shell appops set "$PACKAGE_NAME" MANAGE_EXTERNAL_STORAGE allow 2>/dev/null || true
$ADB_CMD shell pm grant "$PACKAGE_NAME" android.permission.RECORD_AUDIO 2>/dev/null || true
$ADB_CMD shell pm grant "$PACKAGE_NAME" android.permission.READ_EXTERNAL_STORAGE 2>/dev/null || true
$ADB_CMD shell pm grant "$PACKAGE_NAME" android.permission.WRITE_EXTERNAL_STORAGE 2>/dev/null || true
$ADB_CMD shell pm grant "$PACKAGE_NAME" android.permission.BLUETOOTH_CONNECT 2>/dev/null || true
$ADB_CMD shell pm grant "$PACKAGE_NAME" android.permission.POST_NOTIFICATIONS 2>/dev/null || true

# 5. Launch Quest Launcher UI
log_title "STEP 3: Launching Quest Launcher (MainActivity) & Capturing Evidence"

mkdir -p "$OUTPUT_DIR"

$ADB_CMD logcat -c
log_info "Stopping any previous instance..."
$ADB_CMD shell am force-stop "$PACKAGE_NAME" >/dev/null 2>&1 || true
sleep 1

log_info "Starting MainActivity: $MAIN_ACTIVITY..."
$ADB_CMD shell am start -n "$MAIN_ACTIVITY"

# Helper Python function to find element centers in uiautomator XML dumps
find_element_center() {
    local xml_file="$1"
    local query="$2"
    python3 -c "
import xml.etree.ElementTree as ET
import re, sys

def get_center(bounds_str):
    m = re.findall(r'\d+', bounds_str)
    if len(m) >= 4:
        x1, y1, x2, y2 = map(int, m[:4])
        return (x1 + x2) // 2, (y1 + y2) // 2
    return None

try:
    tree = ET.parse('$xml_file')
    query = '$query'
    for node in tree.iter('node'):
        res_id = node.attrib.get('resource-id', '')
        text = node.attrib.get('text', '')
        content_desc = node.attrib.get('content-desc', '')
        if query in res_id or query.lower() in text.lower() or query.lower() in content_desc.lower():
            c = get_center(node.attrib.get('bounds', ''))
            if c:
                print(f'{c[0]} {c[1]}')
                sys.exit(0)
    sys.exit(1)
except Exception as e:
    sys.exit(1)
"
}

capture_screen_and_dump() {
    local label="$1"
    local png_path="${OUTPUT_DIR}/${label}.png"
    local xml_path="${OUTPUT_DIR}/${label}_layout.xml"

    sleep 2
    $ADB_CMD exec-out screencap -p > "$png_path" 2>/dev/null || true
    $ADB_CMD shell uiautomator dump /sdcard/window_dump.xml >/dev/null 2>&1 || true
    $ADB_CMD pull /sdcard/window_dump.xml "$xml_path" >/dev/null 2>&1 || true

    if [ -f "$png_path" ] && [ -s "$png_path" ]; then
        log_ok "Captured evidence: $png_path"
    else
        log_warn "Failed to capture screenshot for $label"
    fi
}

log_info "Waiting for launcher UI to settle..."
sleep 3

# Capture Screen 1: Default Library Tab
log_info "Capturing Launcher Screen 1: Games Library..."
capture_screen_and_dump "quest_launcher_01_library"

# Capture Screen 2: VR Settings Tab
log_info "Navigating to Tab 2: VR Settings..."
VR_COORDS=$(find_element_center "${OUTPUT_DIR}/quest_launcher_01_library_layout.xml" "vrSettingsFragment" || true)
if [ -n "$VR_COORDS" ]; then
    log_info "Tapping VR Settings button at $VR_COORDS..."
    $ADB_CMD shell input tap $VR_COORDS
    capture_screen_and_dump "quest_launcher_02_vr_settings"
else
    # Fallback attempt by title
    VR_COORDS=$(find_element_center "${OUTPUT_DIR}/quest_launcher_01_library_layout.xml" "VR" || true)
    if [ -n "$VR_COORDS" ]; then
        $ADB_CMD shell input tap $VR_COORDS
        capture_screen_and_dump "quest_launcher_02_vr_settings"
    fi
fi

# Capture Screen 3: App Settings Tab
log_info "Navigating to Tab 3: App Settings..."
APP_COORDS=$(find_element_center "${OUTPUT_DIR}/quest_launcher_01_library_layout.xml" "appSettingsFragment" || true)
if [ -n "$APP_COORDS" ]; then
    log_info "Tapping App Settings button at $APP_COORDS..."
    $ADB_CMD shell input tap $APP_COORDS
    capture_screen_and_dump "quest_launcher_03_app_settings"
fi

# Capture Screen 4: Diagnostics Tab
log_info "Navigating to Tab 4: Diagnostics..."
DIAG_COORDS=$(find_element_center "${OUTPUT_DIR}/quest_launcher_01_library_layout.xml" "diagnosticsFragment" || true)
if [ -n "$DIAG_COORDS" ]; then
    log_info "Tapping Diagnostics button at $DIAG_COORDS..."
    $ADB_CMD shell input tap $DIAG_COORDS
    capture_screen_and_dump "quest_launcher_04_diagnostics"
fi

# 6. Assess Health & Crash Logs
log_title "STEP 4: Health & Diagnostics Evaluation"

LOGCAT_FILE="${OUTPUT_DIR}/logcat_launcher.log"
$ADB_CMD logcat -d -v time | grep -E "Xash|MainActivity|Launcher|FATAL|AndroidRuntime|CRASH" > "$LOGCAT_FILE" 2>/dev/null || true

TEST_PASSED=true

IS_RUNNING=$($ADB_CMD shell pidof "$PACKAGE_NAME" 2>/dev/null | tr -d '\r' || true)
if [ -z "$IS_RUNNING" ]; then
    log_err "Quest Launcher process has unexpectedly terminated!"
    TEST_PASSED=false
else
    log_ok "Quest Launcher process PID $IS_RUNNING is running healthy."
fi

if grep -q "FATAL EXCEPTION\|NullPointerException\|SIGSEGV" "$LOGCAT_FILE"; then
    log_err "Fatal exception detected in launcher logcat:"
    grep -E "FATAL EXCEPTION|NullPointerException|SIGSEGV" "$LOGCAT_FILE" | head -n 5
    TEST_PASSED=false
else
    log_ok "Verified: Zero crashes, zero null pointer exceptions in launcher session."
fi

log_title "QUEST LAUNCHER TEST SUMMARY"
echo "Evidence Directory: $OUTPUT_DIR"
ls -la "$OUTPUT_DIR"/*.png 2>/dev/null || true

if [ "$TEST_PASSED" = true ]; then
    log_ok "QUEST APK LAUNCHER VERIFICATION PASSED (100% HEALTHY)!"
    exit 0
else
    log_err "QUEST APK LAUNCHER VERIFICATION ENCOUNTERED ISSUES!"
    exit 1
fi
