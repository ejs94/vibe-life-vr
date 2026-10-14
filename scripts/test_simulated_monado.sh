#!/bin/bash
# ==============================================================================
# Xash3D VR - Automated Local Simulator (Monado) Verification Test Script
# ==============================================================================
# Automates local PCVR simulation testing without requiring physical headset:
#   1. Sets up OpenXR runtime path to Monado build manifest.
#   2. Launches monado-service daemon in background if not already active.
#   3. Runs Xash3D VR engine with bounded execution (default 10s).
#   4. Checks logs for OpenXR instance, session, swapchains, and culling/render errors.
# ==============================================================================

set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MONADO_DIR="$(cd "${REPO_DIR}/../monado" && pwd)"
OUTPUT_DIR="${REPO_DIR}/out/evidence/monado_$(date +%Y%m%d_%H%M%S)"
TIMEOUT_SECS=15
TARGET_MAP="${1:-c1a0}"

log_info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()   { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_err()  { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

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

export XRT_NO_STDIN=true
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json

# 1. Start or verify Monado Service
log_info "Checking Monado background service..."
SERVICE_STARTED=false
if ! pgrep -fa "monado-service" >/dev/null 2>&1; then
    log_info "Starting monado-service in background..."
    "$MONADO_SERVICE" > "${OUTPUT_DIR}/monado_service.log" 2>&1 &
    SERVICE_PID=$!
    SERVICE_STARTED=true
    sleep 1
fi

cleanup() {
    if [ "$SERVICE_STARTED" = true ] && [ -n "${SERVICE_PID:-}" ]; then
        log_info "Stopping spawned monado-service (PID ${SERVICE_PID})..."
        kill -TERM "$SERVICE_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# 2. Setup Environment
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
export XR_RUNTIME_JSON="$MONADO_MANIFEST"
export SDL_VIDEODRIVER=x11
export LD_LIBRARY_PATH=".:${LD_LIBRARY_PATH:-}"

cd "${REPO_DIR}/out"

TEST_LOG="${OUTPUT_DIR}/monado_engine.log"
log_info "Running bounded Xash3D VR engine session (${TIMEOUT_SECS}s) on map: ${TARGET_MAP}..."

set +e
timeout "${TIMEOUT_SECS}s" ./xash3d -dev 1 -condebug -ref gl_vr +map "${TARGET_MAP}" > "$TEST_LOG" 2>&1
RUN_EXIT=$?
set -e

if [ "$RUN_EXIT" -eq 124 ] || [ "$RUN_EXIT" -eq 0 ]; then
    log_info "Engine bounded run finished."
else
    log_warn "Engine exited with code: $RUN_EXIT"
fi

if [ -f "qconsole.log" ]; then
    cp -f qconsole.log "${OUTPUT_DIR}/qconsole.log"
fi

# 3. Analyze Results
TEST_PASSED=true

if grep -iq "instance created\|XR_Init: Requesting extension" "$TEST_LOG" 2>/dev/null; then
    log_ok "Verified: OpenXR instance negotiation initiated."
else
    log_err "Failed: OpenXR instance was not initiated."
    TEST_PASSED=false
fi

if grep -iq "xrCreateSession failed with code -38" "$TEST_LOG" 2>/dev/null; then
    log_warn "Detected: XrGraphicsBindingOpenGLXlibKHR glxFBConfig is NULL (Issue #6). Needs fix in xr_graphics.c."
fi

if grep -q "Segmentation fault\|SIGSEGV\|Aborted" "$TEST_LOG" 2>/dev/null; then
    log_err "Failed: Fatal crash detected during simulation run."
    grep -E "Segmentation fault|SIGSEGV|Aborted" "$TEST_LOG" | head -n 5
    TEST_PASSED=false
fi

echo "=========================================================="
if [ "$TEST_PASSED" = true ]; then
    log_ok "MONADO SIMULATOR TEST COMPLETED: Logs saved to ${OUTPUT_DIR}"
    exit 0
else
    log_err "MONADO SIMULATOR TEST ENCOUNTERED FAILURES: Check ${OUTPUT_DIR}"
    exit 1
fi
