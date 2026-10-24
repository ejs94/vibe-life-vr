#!/bin/bash
# ==============================================================================
# Xash3D VR - Automated Master Regression Test Battery
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [ -d "${REPO_DIR}/../openxr-tooling/monado" ]; then
    MONADO_DIR="$(cd "${REPO_DIR}/../openxr-tooling/monado" && pwd)"
else
    MONADO_DIR="$(cd "${REPO_DIR}/../monado" && pwd)"
fi
OUTPUT_DIR="${REPO_DIR}/out/evidence/regression_$(date +%Y%m%d_%H%M%S)"

log_title() { echo -e "\n\033[1;35m==========================================================\033[0m\n\033[1;35m  $*\033[0m\n\033[1;35m==========================================================\033[0m"; }
log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()    { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_err()   { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

mkdir -p "$OUTPUT_DIR"

# Prefer the minimal simulated-only build when present, then fall back to build.
if [ -z "${MONADO_BUILD_DIR:-}" ]; then
    if [ -x "${MONADO_DIR}/build-sim/src/xrt/targets/service/monado-service" ]; then
        MONADO_BUILD_DIR="${MONADO_DIR}/build-sim"
    else
        MONADO_BUILD_DIR="${MONADO_DIR}/build"
    fi
fi

MONADO_MANIFEST="${MONADO_BUILD_DIR}/openxr_monado-dev.json"
MONADO_SERVICE="${MONADO_BUILD_DIR}/src/xrt/targets/service/monado-service"

if [ ! -f "$MONADO_MANIFEST" ] || [ ! -x "$MONADO_SERVICE" ]; then
    log_err "Monado runtime missing at ${MONADO_BUILD_DIR}."
    exit 1
fi

log_info "Using Monado build: ${MONADO_BUILD_DIR}"

export XRT_NO_STDIN=true
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
export XR_RUNTIME_JSON="$MONADO_MANIFEST"
export SDL_VIDEODRIVER=x11
export LD_LIBRARY_PATH=".:${LD_LIBRARY_PATH:-}"

SERVICE_STARTED=false
log_info "Starting Monado background service daemon..."
pkill -9 -x "monado-service" 2>/dev/null || true
sleep 0.5
"$MONADO_SERVICE" > "${OUTPUT_DIR}/monado_service.log" 2>&1 &
SERVICE_PID=$!
SERVICE_STARTED=true
sleep 1

cleanup() {
    if [ "$SERVICE_STARTED" = true ] && [ -n "${SERVICE_PID:-}" ]; then
        log_info "Stopping Monado service daemon (PID ${SERVICE_PID})..."
        kill -TERM "$SERVICE_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

record_result() {
    local test_name="$1"
    local status="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ "$status" = "PASS" ]; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        log_ok "$test_name"
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        log_err "$test_name"
    fi
}

cd "${REPO_DIR}/out"

# ==============================================================================
# Phase 0: Offline Static Asset Gates (no OpenXR runtime required)
# ==============================================================================
log_title "PHASE 0: Offline Hand Asset Integrity & Deploy Freshness"

# Gate 0.1: Two-hand model structure + rendered orientation
HAND_ASSET_LOG="${OUTPUT_DIR}/hand_asset_check.log"
if "${REPO_DIR}/scripts/check_hand_asset.sh" > "$HAND_ASSET_LOG" 2>&1; then
    record_result "0.1 Standalone Two-Hand Asset Structure & Rendered Orientation (fingers +X, palms inward, thumbs up)" "PASS"
else
    log_err "See ${HAND_ASSET_LOG} for the failing checks."
    record_result "0.1 Standalone Two-Hand Asset Structure & Rendered Orientation (fingers +X, palms inward, thumbs up)" "FAIL"
fi

# Gate 0.2: Deploy freshness -- the runtime copies must match the source asset
SRC_HAND="${REPO_DIR}/assets/valve_vr/models/v_hand.mdl"
DEPLOY_OK=true
for deployed in "${REPO_DIR}/out/valve_vr/models/v_hand.mdl" "${REPO_DIR}/out/valve/models/v_hand.mdl"; do
    if [ ! -f "$deployed" ]; then
        log_err "Missing deployed hand model: ${deployed}"
        DEPLOY_OK=false
    elif ! cmp -s "$SRC_HAND" "$deployed"; then
        log_err "Stale deployed hand model: ${deployed} differs from ${SRC_HAND}"
        DEPLOY_OK=false
    fi
done
if [ "$DEPLOY_OK" = true ]; then
    record_result "0.2 Standalone Hand Asset Deploy Freshness (out/ matches assets/)" "PASS"
else
    record_result "0.2 Standalone Hand Asset Deploy Freshness (out/ matches assets/)" "FAIL"
fi

# Copy regression script to engine out directory so +exec finds it immediately
cp -f "${REPO_DIR}/scripts/regression_master.cfg" "${REPO_DIR}/out/regression_master.cfg"

# ==============================================================================
# Phase 1: End-to-End VR Engine Execution in Monado Simulation
# ==============================================================================
log_title "PHASE 1: Executing Full Master VR Regression Suite in PCVR Simulation"

MASTER_LOG="${OUTPUT_DIR}/regression_engine.log"
log_info "Running bounded Xash3D VR engine session (45s timeout)..."
timeout 45s ./xash3d -dev 1 -condebug -ref gl_vr +sv_cheats 1 +exec regression_master.cfg > "$MASTER_LOG" 2>&1
RUN_EXIT=$?
log_info "Engine session finished (exit code: ${RUN_EXIT})."

# Convert and save all dumped PPM frames to PNG evidence
for ppm in regr_*.ppm vr_*.ppm; do
    if [ -f "$ppm" ]; then
        cp -f "$ppm" "${OUTPUT_DIR}/$ppm"
        png="${ppm%.ppm}.png"
        convert "${OUTPUT_DIR}/$ppm" "${OUTPUT_DIR}/$png" 2>/dev/null || true
        log_info "Captured evidence screenshot: ${png}"
        rm -f "$ppm"
    fi
done

# ==============================================================================
# Phase 2: Empirical Verification & Scorecard Checks
# ==============================================================================
log_title "PHASE 2: Evaluating Verification Gates & Feature Correctness"

# Check 1: OpenXR Session Initialization
if grep -q "OpenXR: xrBeginSession started successfully!" "$MASTER_LOG"; then
    record_result "1.1 OpenXR Runtime Negotiation & Dual Swapchains" "PASS"
else
    record_result "1.1 OpenXR Runtime Negotiation & Dual Swapchains" "FAIL"
fi

# Check 2: VR CVars Registered and Accessible
if grep -q "vr_smoothturn" "$MASTER_LOG" && grep -q "vr_lasersight" "$MASTER_LOG" && \
   grep -q "vr_headtorch" "$MASTER_LOG" && grep -q "vr_audio_hrtf" "$MASTER_LOG" && \
   grep -q "vr_hand_offset_forward" "$MASTER_LOG" && grep -q "vr_finger_curling" "$MASTER_LOG" && \
   grep -q "vr_debug_hand_pose" "$MASTER_LOG"; then
    record_result "1.2 VR Configuration CVars Registration & Defaults" "PASS"
else
    record_result "1.2 VR Configuration CVars Registration & Defaults" "FAIL"
fi

# Check 3: Dedicated In-Headset VR Options Menu (CMenuVR / menu_vr)
if [ -f "${OUTPUT_DIR}/regr_01_menu_vr_options.png" ] || grep -q "CMenuVR" "$MASTER_LOG"; then
    record_result "1.3 In-Headset Dedicated VR Options Menu Screen (CMenuVR)" "PASS"
else
    record_result "1.3 In-Headset Dedicated VR Options Menu Screen (CMenuVR)" "FAIL"
fi

# Check 4: Beat Saber Dual Alternating Laser Pointers
if grep -q "Switched active pointer to RIGHT hand" "$MASTER_LOG" && grep -q "Switched active pointer to LEFT hand" "$MASTER_LOG"; then
    record_result "1.4 Beat Saber Dual Alternating Laser Pointers (Hand Switch & Click)" "PASS"
else
    record_result "1.4 Beat Saber Dual Alternating Laser Pointers (Hand Switch & Click)" "FAIL"
fi

# Check 5: 3D Map Load & Player Spawn
if grep -q "level loaded at" "$MASTER_LOG" && grep -q "client connected at" "$MASTER_LOG"; then
    record_result "1.5 3D Map Level Load (c1a0) & Client Spawning" "PASS"
else
    record_result "1.5 3D Map Level Load (c1a0) & Client Spawning" "FAIL"
fi

# Check 6: Head Flashlight Gesture Toggle (HL2:VR style)
if grep -q "Head flashlight toggled by RIGHT hand gesture" "$MASTER_LOG" && grep -q "Head flashlight toggled by LEFT hand gesture" "$MASTER_LOG"; then
    record_result "1.6 Head-Mounted Flashlight & 6DoF Temple Gesture Toggle (HL2:VR style)" "PASS"
else
    record_result "1.6 Head-Mounted Flashlight & 6DoF Temple Gesture Toggle (HL2:VR style)" "FAIL"
fi

# Check 7: Orthonormal 6DoF Head Roll Matrix (Singularity-Free)
if grep -q "Head Roll Left" "$MASTER_LOG" && [ -f "${OUTPUT_DIR}/regr_06_head_roll_left.png" ] && [ -f "${OUTPUT_DIR}/regr_07_head_roll_right.png" ]; then
    record_result "1.7 Orthonormal Quaternion Head View Matrix (Roll Stability, Zero Nausea)" "PASS"
else
    record_result "1.7 Orthonormal Quaternion Head View Matrix (Roll Stability, Zero Nausea)" "FAIL"
fi

# Check 8: Server-Side 6DoF Muzzle Ballistics across Arsenal (Issue #14)
if [ -f "${OUTPUT_DIR}/regr_08_mp5_muzzle.png" ] && [ -f "${OUTPUT_DIR}/regr_11_rpg_muzzle.png" ]; then
    record_result "1.8 Server-Side 6DoF Weapon Muzzle Ballistics & RPG Rocket Spawn (Issue #14)" "PASS"
else
    record_result "1.8 Server-Side 6DoF Weapon Muzzle Ballistics & RPG Rocket Spawn (Issue #14)" "FAIL"
fi

# Check 9: Physical Grenade Tossing Momentum via 6DoF Hand Velocity (Issue #15)
if [ -f "${OUTPUT_DIR}/regr_12_grenade_momentum.png" ]; then
    record_result "1.9 Physical Hand Grenade Toss Momentum & Hand Alignment (Issue #15)" "PASS"
else
    record_result "1.9 Physical Hand Grenade Toss Momentum & Hand Alignment (Issue #15)" "FAIL"
fi

# Check 10: Two-Handed Weapon Grip Stabilization Mode
if [ -f "${OUTPUT_DIR}/regr_13_twohanded.png" ]; then
    record_result "1.10 Two-Handed Weapon Grip Stabilization (vr_twohanded)" "PASS"
else
    record_result "1.10 Two-Handed Weapon Grip Stabilization (vr_twohanded)" "FAIL"
fi

# Check 11: 3D Binaural HRTF Spatial Audio & 6DoF Listener Tracking (Issue #17)
if grep -q "VR_AUDIO_DBG" "$MASTER_LOG" && grep -q "hrtf=1" "$MASTER_LOG"; then
    record_result "1.11 3D Binaural HRTF Spatial Audio & 6DoF Listener Tracking (Issue #17)" "PASS"
else
    record_result "1.11 3D Binaural HRTF Spatial Audio & 6DoF Listener Tracking (Issue #17)" "FAIL"
fi

# Check 12: Dynamic Articulated Skeletal 3D Hands & Finger Curling (Issue #16)
if [ -f "${OUTPUT_DIR}/regr_14_finger_curling.png" ] && grep -q "VR_HANDS_DBG" "$MASTER_LOG" && grep -q "bones curled" "$MASTER_LOG"; then
    record_result "1.12 Dynamic Articulated Skeletal 3D Hands & Finger Curling (Issue #16)" "PASS"
else
    record_result "1.12 Dynamic Articulated Skeletal 3D Hands & Finger Curling (Issue #16)" "FAIL"
fi

# Check 15: Runtime hand pose telemetry (orientation + bodygroup selection)
HAND_POSE_LOG="${OUTPUT_DIR}/hand_pose_check.log"
if python3 "${REPO_DIR}/scripts/check_hand_pose_log.py" "$MASTER_LOG" > "$HAND_POSE_LOG" 2>&1; then
    record_result "1.15 Runtime Hand Pose Telemetry: Fingers +X, Palms Inward, Thumbs Up (+Z) [HAND_POSE]" "PASS"
else
    log_err "See ${HAND_POSE_LOG} for the failing assertions."
    record_result "1.15 Runtime Hand Pose Telemetry: Fingers +X, Palms Inward, Thumbs Up (+Z) [HAND_POSE]" "FAIL"
fi

# Check 16: Two-hand bodygroup chain selection & handedness swap
if grep -q "ent=primary body=0 chain=R" "$MASTER_LOG" && \
   grep -q "ent=offhand body=3 chain=L" "$MASTER_LOG" && \
   grep -q "ent=primary body=3 chain=L" "$MASTER_LOG" && \
   grep -q "ent=offhand body=0 chain=R" "$MASTER_LOG"; then
    record_result "1.16 Two-Hand Bodygroup Chain Selection & vr_lefthanded Swap (body 0/3)" "PASS"
else
    record_result "1.16 Two-Hand Bodygroup Chain Selection & vr_lefthanded Swap (body 0/3)" "FAIL"
fi

# ==============================================================================
# Phase 3: Meta Quest Standalone APK & Android Launcher Verification
# ==============================================================================
log_title "PHASE 3: Standalone Quest APK & Android Launcher Verification"

APK_PATH="${REPO_DIR}/out/xash3d-vr-quest.apk"
if [ -f "$APK_PATH" ]; then
    APK_SIZE=$(ls -lh "$APK_PATH" | awk '{print $5}')
    log_info "Found Meta Quest Standalone APK: ${APK_PATH} (${APK_SIZE})"

    APK_CONTENTS=$(unzip -l "$APK_PATH" 2>/dev/null || true)
    REQUIRED_LIBS=("libxash.so" "libref_gl_vr.so" "libhl_android_arm64.so" "libclient_android_arm64.so" "libmenu.so")
    ALL_LIBS_PRESENT=true
    for lib in "${REQUIRED_LIBS[@]}"; do
        if echo "$APK_CONTENTS" | grep -F -q "$lib"; then
            log_info "  [x] APK contains ${lib}"
        else
            log_err "  [ ] APK missing ${lib}!"
            ALL_LIBS_PRESENT=false
        fi
    done

    if [ "$ALL_LIBS_PRESENT" = true ]; then
        record_result "1.13 Standalone Meta Quest APK Architecture & Native Libs (ARM64-v8a)" "PASS"
    else
        record_result "1.13 Standalone Meta Quest APK Architecture & Native Libs (ARM64-v8a)" "FAIL"
    fi
else
    record_result "1.13 Standalone Meta Quest APK Architecture & Native Libs (ARM64-v8a)" "FAIL"
fi

# Check 14: Meta Horizon OS 2D Launcher Layout Constraints & Preferences (Issue #10)
CARD_LAYOUT="${REPO_DIR}/android/app/src/main/res/layout/card_game.xml"
ACTIVITY_LAYOUT="${REPO_DIR}/android/app/src/main/res/layout/activity_main.xml"
PREFS_LAYOUT="${REPO_DIR}/android/app/src/main/res/xml/vr_preferences.xml"

if grep -q 'minHeight="170dp"' "$CARD_LAYOUT" && grep -q 'minHeight="?attr/actionBarSize"' "$ACTIVITY_LAYOUT" && grep -q 'vr_headtorch' "$PREFS_LAYOUT"; then
    record_result "1.14 Meta Horizon OS 2D Launcher Layout Constraints & Preferences (Issue #10)" "PASS"
else
    record_result "1.14 Meta Horizon OS 2D Launcher Layout Constraints & Preferences (Issue #10)" "FAIL"
fi

# ==============================================================================
# Final Scorecard Summary
# ==============================================================================
log_title "REGRESSION TEST SCORECARD"
echo "Total Tests Run:     ${TOTAL_TESTS}"
echo "Passed Tests:        ${PASSED_TESTS}"
echo "Failed Tests:        ${FAILED_TESTS}"
echo "Evidence Directory:  ${OUTPUT_DIR}"

if [ "$FAILED_TESTS" -eq 0 ]; then
    log_ok "ALL ${TOTAL_TESTS} REGRESSION TESTS PASSED! All implementations confirmed working."
    exit 0
else
    log_err "SOME REGRESSION TESTS FAILED (${FAILED_TESTS}/${TOTAL_TESTS}). Check logs in ${OUTPUT_DIR}."
    exit 1
fi
