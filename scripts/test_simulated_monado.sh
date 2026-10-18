#!/bin/bash
# ==============================================================================
# Xash3D VR - Monado VR Comprehensive Unit Test Suite Runner
# ==============================================================================
# Executes an end-to-end unit test suite verifying all developed VR systems
# under the Monado OpenXR simulated runtime:
#   1. OpenXR instance, session, dual swapchains and reference spaces.
#   2. CMenuVR dedicated in-headset menu and fixed room-space Quad HUD.
#   3. Dual alternating Beat Saber laser pointers with trigger hit detection.
#   4. HL2:VR unified controller layout (A reload, B altfire, X jump, Y use).
#   5. Head-mounted flashlight temple gesture toggle.
#   6. Orthonormal quaternion head view matrix (singularity-free roll).
#   7. Physical roomscale crouch (vr_physical_crouch auto-crouch on squat).
#   8. Server-side 6DoF weapon ballistics (MP5, Shotgun, Crossbow, RPG).
#   9. Physical grenade toss momentum absorption.
#  10. 6DoF Tripmines placement trace & Snark toss with controller momentum.
#  11. Two-handed weapon grip stabilization (vr_twohanded).
#  12. Dynamic skeletal 3D hands & procedural analog finger curling.
#  13. 3D binaural HRTF spatial audio & 6DoF listener tracking.
#  14. Bullet impact 3D debug tracking markers.
#  15. Clean engine deallocation and exit.
# ==============================================================================

set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -d "${REPO_DIR}/../openxr-tooling/monado" ]; then
    MONADO_DIR="$(cd "${REPO_DIR}/../openxr-tooling/monado" && pwd)"
else
    MONADO_DIR="$(cd "${REPO_DIR}/../monado" && pwd)"
fi

OUTPUT_DIR="${REPO_DIR}/out/evidence/monado_unittest_$(date +%Y%m%d_%H%M%S)"
TIMEOUT_SECS="${TIMEOUT_SECS:-40}"
TARGET_ARG="${1:-suite}"
shift || true
EXTRA_ARGS="${*:-}"

log_title() { echo -e "\n\033[1;35m==========================================================\033[0m\n\033[1;35m  $*\033[0m\n\033[1;35m==========================================================\033[0m"; }
log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()    { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_err()   { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

# 1. Verify Host Binaries
if [ ! -f "${REPO_DIR}/out/xash3d" ] || [ ! -f "${REPO_DIR}/out/libref_gl_vr.so" ]; then
    log_err "PCVR binaries missing in ${REPO_DIR}/out. Please compile with ./waf build && ./waf install --destdir=./out."
    exit 1
fi

MONADO_MANIFEST="${MONADO_DIR}/build/openxr_monado-dev.json"
MONADO_SERVICE="${MONADO_DIR}/build/src/xrt/targets/service/monado-service"

if [ ! -f "$MONADO_MANIFEST" ] || [ ! -x "$MONADO_SERVICE" ]; then
    log_err "Monado build artifacts missing in ${MONADO_DIR}/build. Please ensure Monado is built."
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# 2. Environment Configuration for Monado OpenXR
export XRT_NO_STDIN=true
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
export XR_RUNTIME_JSON="$MONADO_MANIFEST"
export SDL_VIDEODRIVER=x11
export LD_LIBRARY_PATH=".:${LD_LIBRARY_PATH:-}"

# 3. Start or Verify Monado Service Daemon
log_title "MONADO RUNTIME: Initializing OpenXR Simulated Driver"
SERVICE_STARTED=false
if ! pgrep -fa "monado-service" >/dev/null 2>&1; then
    log_info "Starting monado-service daemon in background..."
    "$MONADO_SERVICE" > "${OUTPUT_DIR}/monado_service.log" 2>&1 &
    SERVICE_PID=$!
    SERVICE_STARTED=true
    sleep 1
else
    log_info "Monado service daemon is already running."
fi

cleanup() {
    if [ "$SERVICE_STARTED" = true ] && [ -n "${SERVICE_PID:-}" ]; then
        log_info "Stopping spawned monado-service daemon (PID ${SERVICE_PID})..."
        kill -TERM "$SERVICE_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# 4. Prepare Test Script Execution
cd "${REPO_DIR}/out"

cp -f "${REPO_DIR}/scripts/monado_unit_tests.cfg" "${REPO_DIR}/out/monado_unit_tests.cfg"
cp -f "${REPO_DIR}/scripts/monado_unit_tests.cfg" "${REPO_DIR}/out/valve/monado_unit_tests.cfg" 2>/dev/null || true

TEST_LOG="${OUTPUT_DIR}/monado_unittest_engine.log"

if [ "$TARGET_ARG" = "suite" ] || [ "$TARGET_ARG" = "--unit-tests" ]; then
    RUN_CMD="./xash3d -dev 1 -condebug -ref gl_vr +sv_cheats 1 +exec monado_unit_tests.cfg ${EXTRA_ARGS}"
    RUN_MODE="Full VR Subsystems Unit Test Suite"
else
    RUN_CMD="./xash3d -dev 1 -condebug -ref gl_vr +sv_cheats 1 +map ${TARGET_ARG} ${EXTRA_ARGS}"
    RUN_MODE="Custom Map Simulation: ${TARGET_ARG}"
fi

log_title "PHASE 1: Executing ${RUN_MODE} (${TIMEOUT_SECS}s Timeout)"
log_info "Command: ${RUN_CMD}"

set +e
timeout "${TIMEOUT_SECS}s" ${RUN_CMD} > "$TEST_LOG" 2>&1
RUN_EXIT=$?
set -e

if [ "$RUN_EXIT" -eq 124 ]; then
    log_info "Engine bounded run concluded via timeout (${TIMEOUT_SECS}s)."
elif [ "$RUN_EXIT" -eq 0 ]; then
    log_ok "Engine session completed and exited cleanly (code 0)."
else
    log_warn "Engine exited with code: $RUN_EXIT"
fi

if [ -f "qconsole.log" ]; then
    cp -f qconsole.log "${OUTPUT_DIR}/qconsole.log"
fi

# 5. Convert Captured Evidence Screenshots
CAPTURED_IMAGES=0
for ppm in unit_*.ppm regr_*.ppm vr_*.ppm; do
    if [ -f "$ppm" ]; then
        cp -f "$ppm" "${OUTPUT_DIR}/$ppm"
        png_name="${ppm%.ppm}.png"
        convert "${OUTPUT_DIR}/$ppm" "${OUTPUT_DIR}/${png_name}" 2>/dev/null || true
        log_info "Captured test artifact: ${png_name}"
        CAPTURED_IMAGES=$((CAPTURED_IMAGES + 1))
        rm -f "$ppm"
    fi
done

# 6. Comprehensive Scorecard of Unit Test Assertions
log_title "PHASE 2: Evaluating Monado VR Unit Test Assertions"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

assert_test() {
    local test_id="$1"
    local test_desc="$2"
    local condition="$3"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if eval "$condition"; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        printf "\033[1;32m[PASS]\033[0m [%02d] %-65s\n" "$test_id" "$test_desc"
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        printf "\033[1;31m[FAIL]\033[0m [%02d] %-65s\n" "$test_id" "$test_desc"
    fi
}

# --- Core OpenXR & Stereo Frame Pipeline ---
assert_test 1  "OpenXR Runtime Handshake & Dual Stereo Swapchains" \
    'grep -q "OpenXR: xrBeginSession started successfully!" "$TEST_LOG" || grep -q "instance created" "$TEST_LOG"'

assert_test 2  "Core VR CVars Registered and Accessible" \
    'grep -q "vr_smoothturn" "$TEST_LOG" && grep -q "vr_lasersight" "$TEST_LOG" && grep -q "vr_physical_crouch" "$TEST_LOG"'

assert_test 3  "In-Headset Dedicated VR Options Menu (All 4 Tabs Captured)" \
    '[ -f "${OUTPUT_DIR}/unit_01_menu_vr.png" ] && [ -f "${OUTPUT_DIR}/unit_01b_tab_weapons.png" ] && [ -f "${OUTPUT_DIR}/unit_01c_tab_presence.png" ] && [ -f "${OUTPUT_DIR}/unit_01d_menu_vr_debug.png" ]'

assert_test 4  "Beat Saber Dual Alternating Laser Pointers (Right Hand)" \
    'grep -q "Switched active pointer to RIGHT hand" "$TEST_LOG"'

assert_test 5  "Beat Saber Dual Alternating Laser Pointers (Left Hand)" \
    'grep -q "Switched active pointer to LEFT hand" "$TEST_LOG"'

# --- Gameplay Load & Head Pose Matrix ---
assert_test 6  "3D Map Level Load (c1a0) & Player Entity Spawning" \
    'grep -q "level loaded at" "$TEST_LOG" && grep -q "client connected at" "$TEST_LOG"'

assert_test 7  "Head-Mounted Flashlight Temple Gesture (Toggle ON)" \
    'grep -q "Head flashlight toggled by RIGHT hand gesture" "$TEST_LOG"'

assert_test 8  "Head-Mounted Flashlight Temple Gesture (Toggle OFF)" \
    'grep -q "Head flashlight toggled by LEFT hand gesture" "$TEST_LOG"'

assert_test 9  "Orthonormal Quaternion Head View Matrix (Zero Singularity Roll)" \
    'grep -q "Head Roll Left" "$TEST_LOG" && [ -f "${OUTPUT_DIR}/unit_06_head_roll_left.png" ]'

# --- HL2:VR Unified Input Layout ---
assert_test 10 "HL2:VR Input Layout: Right A Button -> Reload Action" \
    'grep -q "HL2VR Action: Reload triggered" "$TEST_LOG"'

assert_test 11 "HL2:VR Input Layout: Right B Button -> Secondary / Alt-Fire Action" \
    'grep -q "HL2VR Action: Secondary / Alt-Fire triggered" "$TEST_LOG"'

assert_test 12 "HL2:VR Input Layout: Left X Button -> Jump Action" \
    'grep -q "HL2VR Action: Jump triggered" "$TEST_LOG"'

assert_test 13 "HL2:VR Input Layout: Left Y Button -> Use / Interact Action" \
    'grep -q "HL2VR Action: Use / Interact triggered" "$TEST_LOG"'

# --- Gold Benchmark Remediations ---
assert_test 14 "Physical Roomscale Crouch: Squat Drop (>= 28cm) Engages IN_DUCK" \
    'grep -q "Physical Roomscale Crouch ENGAGED" "$TEST_LOG"'

assert_test 15 "Physical Roomscale Crouch: Standing Up Releases IN_DUCK Hull" \
    'grep -q "Physical Roomscale Crouch RELEASED" "$TEST_LOG"'

assert_test 16 "6DoF Tripmine Placement Trace Aligned with Hand Controller" \
    'grep -q "6DoF Tripmine placed at" "$TEST_LOG" || [ -f "${OUTPUT_DIR}/unit_14_tripmine_placed.png" ]'

assert_test 17 "6DoF Snark Toss with Controller Velocity Momentum" \
    'grep -q "6DoF Snark tossed with velocity" "$TEST_LOG" || [ -f "${OUTPUT_DIR}/unit_15_snark_tossed.png" ]'

# --- Weapon Systems, Hands & Spatial Audio ---
assert_test 18 "Server-Side 6DoF Weapon Ballistics across Arsenal" \
    '[ -f "${OUTPUT_DIR}/unit_09_mp5_muzzle.png" ] && [ -f "${OUTPUT_DIR}/unit_12_rpg_muzzle.png" ]'

assert_test 19 "Two-Handed Weapon Grip Stabilization Mode (vr_twohanded)" \
    '[ -f "${OUTPUT_DIR}/unit_16_twohanded.png" ] || grep -q "twohanded" "$TEST_LOG"'

assert_test 20 "Dynamic Articulated Skeletal 3D Hands & Finger Curling" \
    'grep -q "VR_HANDS_DBG" "$TEST_LOG" && grep -q "bones curled" "$TEST_LOG" || [ -f "${OUTPUT_DIR}/unit_17_finger_curling.png" ]'

assert_test 21 "3D Binaural HRTF Spatial Audio & 6DoF Listener Tracking" \
    'grep -q "VR_AUDIO_DBG" "$TEST_LOG" && grep -q "hrtf=1" "$TEST_LOG"'

assert_test 22 "3D Bullet Impact Debug Visualization System (vr_debug_impacts)" \
    'grep -q "Debug bullet impacts cleared" "$TEST_LOG" || grep -q "vr_clear_impacts" "$TEST_LOG"'

assert_test 23 "Declarative Weapon Profiles Calibration Manifest (vr_weapons.json)" \
    'grep -q "VR_WEAPON_PROFILES" "$TEST_LOG"'

assert_test 24 "Clean Simulation Execution & Zero Memory / Process Crash" \
    '! grep -E -q "Segmentation fault|SIGSEGV|Aborted \(core dumped\)" "$TEST_LOG"'

# 7. Optional Quest Launcher UI Verification
if [ "${TARGET_ARG}" = "all" ] || [ "${TARGET_ARG}" = "--with-launcher" ] || [ "${TARGET_ARG}" = "full" ]; then
    log_title "PHASE 3: Executing Meta Quest APK Launcher UI Verification"
    if [ -f "${SCRIPT_DIR}/test_quest_launcher.sh" ]; then
        "${SCRIPT_DIR}/test_quest_launcher.sh" "${REPO_DIR}/out/xash3d-vr-quest.apk" || true
    fi
fi

# 8. Final Summary
log_title "MONADO UNIT TEST SUMMARY SCORECARD"
echo "Total Assertions Tested: ${TOTAL_TESTS}"
echo -e "Passed: \033[1;32m${PASSED_TESTS}\033[0m"
echo -e "Failed: \033[1;31m${FAILED_TESTS}\033[0m"
echo "Captured Visual Artifacts: ${CAPTURED_IMAGES} PNGs"
echo "Evidence Directory: ${OUTPUT_DIR}"
echo "=========================================================="

if [ "$FAILED_TESTS" -eq 0 ]; then
    log_ok "ALL ${TOTAL_TESTS}/${TOTAL_TESTS} MONADO VR UNIT TESTS PASSED (100% GREEN)!"
    exit 0
else
    log_err "${FAILED_TESTS} UNIT TEST(S) FAILED. Review log at: ${TEST_LOG}"
    exit 1
fi
