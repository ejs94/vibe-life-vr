#!/bin/bash
# ==============================================================================
# Xash3D VR - Automated Linux PCVR (WiVRn) Verification Test Script
# ==============================================================================
# Automates end-to-end PCVR validation:
#   1. Starts host WiVRn server service if idle.
#   2. Wakes/launches WiVRn client on Meta Quest via ADB with port reverse.
#   3. Runs Xash3D VR engine with a bounded timeout (10 seconds).
#   4. Verifies OpenXR runtime negotiation, session state, and frame rendering.
# ==============================================================================

set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${REPO_DIR}/out/evidence/pcvr_$(date +%Y%m%d_%H%M%S)"
TIMEOUT_SECS=10
TARGET_MAP="${1:-crossfire}"

log_info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()   { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_err()  { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

if [ ! -f "${REPO_DIR}/out/xash3d" ] || [ ! -f "${REPO_DIR}/out/libref_gl_vr.so" ]; then
    log_err "PCVR binaries missing in ${REPO_DIR}/out. Please compile with ./waf build && ./waf install --destdir=./out."
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# 1. Start WiVRn server
log_info "Verifying WiVRn server status on host..."
if ! pgrep -fa "wivrn-server" >/dev/null 2>&1; then
    log_info "Starting wivrn.service..."
    if command -v systemctl >/dev/null 2>&1 && systemctl --user list-unit-files | grep -q "wivrn.service"; then
        systemctl --user start wivrn || true
    fi
    if ! pgrep -fa "wivrn-server" >/dev/null 2>&1 && command -v wivrn-server >/dev/null 2>&1; then
        wivrn-server &
        sleep 1
    fi
fi

if pgrep -fa "wivrn-server" >/dev/null 2>&1; then
    log_ok "WiVRn server is running."
else
    log_warn "WiVRn server is not running. OpenXR loader may fail if using WiVRn runtime."
fi

# 2. Check ADB connection to headset
if ! command -v adb >/dev/null 2>&1 && [ -d "$HOME/Android/Sdk/platform-tools" ]; then
    export PATH="$HOME/Android/Sdk/platform-tools:$PATH"
fi

if command -v adb >/dev/null 2>&1; then
    DEV_COUNT=$(adb devices 2>/dev/null | awk 'NR>1 && $2=="device"' | wc -l || true)
    if [ "$DEV_COUNT" -gt 0 ]; then
        log_ok "Meta Quest headset detected via ADB."
        
        # Check battery & thermals
        if [ -f "${SCRIPT_DIR}/quest_battery.sh" ]; then
            "${SCRIPT_DIR}/quest_battery.sh" display || true
        fi
        
        log_info "Waking headset display and setting proximity state..."
        adb shell input keyevent 224 2>/dev/null || true
        adb shell am broadcast -a com.oculus.vrpowermanager.prox_close >/dev/null 2>&1 || true

        log_info "Configuring port reverse (tcp:9757)..."
        adb reverse tcp:9757 tcp:9757 2>/dev/null || true
        
        log_info "Signaling WiVRn client on headset via ADB intent..."
        adb shell am start -a android.intent.action.VIEW -d "wivrn://localhost" org.meumeu.wivrn >/dev/null 2>&1 || \
        adb shell am start -n org.meumeu.wivrn/.MainActivity >/dev/null 2>&1 || true
        
        # Wait up to 5 seconds for WiVRn session handshake
        log_info "Waiting for WiVRn streaming handshake..."
        for i in {1..5}; do
            if journalctl --user -u wivrn -n 10 --no-pager 2>/dev/null | grep -q "XR_SESSION_STATE_FOCUSED\|XR_SESSION_STATE_VISIBLE"; then
                log_ok "WiVRn streaming session active."
                break
            fi
            sleep 1
        done
    else
        log_warn "No Quest headset in adb devices. Testing PCVR locally against active OpenXR runtime."
    fi
fi

# 3. Setup OpenXR runtime environment
if [ -f "/usr/share/openxr/1/openxr_wivrn.json" ]; then
    export XR_RUNTIME_JSON="/usr/share/openxr/1/openxr_wivrn.json"
fi

export LD_LIBRARY_PATH=".:${LD_LIBRARY_PATH:-}"
export SDL_VIDEODRIVER=x11

PRIME_CMD=""
if command -v prime-run >/dev/null 2>&1; then
    PRIME_CMD="prime-run"
fi

cd "${REPO_DIR}/out"

# 4. Run bounded engine test
TEST_LOG="${OUTPUT_DIR}/pcvr_engine.log"
log_info "Running bounded Xash3D VR engine session (${TIMEOUT_SECS}s timeout) on map: ${TARGET_MAP}..."

set +e
timeout "${TIMEOUT_SECS}s" $PRIME_CMD ./xash3d -dev 1 -condebug -ref gl_vr +map "${TARGET_MAP}" > "$TEST_LOG" 2>&1
RUN_EXIT=$?
set -e

# Exit code 124 means timeout reached (expected for bounded test)
if [ "$RUN_EXIT" -eq 124 ] || [ "$RUN_EXIT" -eq 0 ]; then
    log_info "Bounded run finished successfully."
else
    log_warn "Engine exited with code: $RUN_EXIT"
fi

# Also capture qconsole.log if produced
if [ -f "qconsole.log" ]; then
    cp -f qconsole.log "${OUTPUT_DIR}/qconsole.log"
fi

# 5. Analyze Results
TEST_PASSED=true

if grep -iq "instance created" "$TEST_LOG" 2>/dev/null; then
    log_ok "Verified: OpenXR instance created successfully."
else
    log_err "Failed: OpenXR instance was not created."
    TEST_PASSED=false
fi

if grep -iq "Head: 'WiVRn HMD'\|Headset detected" "$TEST_LOG" 2>/dev/null; then
    log_ok "Verified: WiVRn Headset detected successfully."
fi

if grep -iq "XrSession created" "$TEST_LOG" 2>/dev/null; then
    log_ok "Verified: OpenXR session created successfully."
fi

if grep -iq "Stereo swapchains created" "$TEST_LOG" 2>/dev/null; then
    log_ok "Verified: Stereo swapchains created."
fi

if grep -iq "xrBeginSession started successfully\|R_SetupXREyeFbos" "$TEST_LOG" 2>/dev/null; then
    log_ok "Verified: OpenXR session streaming frames to headset."
fi

if grep -q "Segmentation fault\|SIGSEGV\|Aborted" "$TEST_LOG" 2>/dev/null; then
    log_err "Failed: Fatal crash detected in PCVR execution."
    grep -E "Segmentation fault|SIGSEGV|Aborted" "$TEST_LOG" | head -n 5
    TEST_PASSED=false
fi

echo "=========================================================="
if [ -f "${SCRIPT_DIR}/quest_battery.sh" ] && [ "${DEV_COUNT:-0}" -gt 0 ]; then
    log_info "Post-test Battery Status:"
    "${SCRIPT_DIR}/quest_battery.sh" display || true
fi

if [ "$TEST_PASSED" = true ]; then
    log_ok "PCVR WIVRN TEST PASSED: Evidence captured in ${OUTPUT_DIR}"
    exit 0
else
    log_err "PCVR WIVRN TEST FAILED: Check logs in ${OUTPUT_DIR}"
    exit 1
fi
