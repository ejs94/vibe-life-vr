#!/usr/bin/env bash
# ==============================================================================
# Vibe-Life VR — Glock manual reload vertical slice
# ==============================================================================
# Builds the local HLSDK server/client, installs them into out/valve without
# following the Steam symlinks, then runs the three-stage Glock reload under the
# simulated Monado runtime.
#
# Usage: scripts/test_manual_reload.sh
# ==============================================================================
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HLSDK_DIR="${REPO_DIR}/3rdparty/hlsdk-portable"
HLSDK_BUILD="${HLSDK_DIR}/build-vibe-linux64"
OUT_VALVE="${REPO_DIR}/out/valve"
EVIDENCE_DIR="${REPO_DIR}/out/evidence/manual_reload_$(date +%Y%m%d_%H%M%S)"
MONADO_DIR="$(cd "${REPO_DIR}/../openxr-tooling/monado" && pwd)"
MONADO_BUILD_DIR="${MONADO_DIR}/build-sim"

log_info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()   { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_err()  { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

if [ ! -d "${HLSDK_DIR}" ]; then
    log_err "HLSDK not found at 3rdparty/hlsdk-portable"
    exit 1
fi

if [ ! -f "${HLSDK_BUILD}/CMakeCache.txt" ]; then
    log_info "Configuring the local HLSDK build..."
    cmake -S "${HLSDK_DIR}" -B "${HLSDK_BUILD}" \
        -D64BIT=ON -DBUILD_CLIENT=ON -DBUILD_SERVER=ON -DGOLDSOURCE_SUPPORT=OFF >/dev/null
fi

log_info "Building the local HLSDK..."
cmake --build "${HLSDK_BUILD}" -j "$(nproc)" >/dev/null

# Replace the Steam symlinks with real directories before copying. A plain cp
# through a symlink would rewrite the user's Half-Life installation.
for pair in "dlls:hl_amd64.so" "cl_dll:client_amd64.so"; do
    src_dir="${pair%%:*}"
    lib="${pair##*:}"
    dst_dir="${src_dir}"
    if [ "${src_dir}" = "cl_dll" ]; then dst_dir="cl_dlls"; fi
    dst="${OUT_VALVE}/${dst_dir}"
    if [ -L "${dst}" ]; then
        src="$(readlink -f "${dst}")"
        rm "${dst}"
        mkdir -p "${dst}"
        cp -a "${src}/." "${dst}/"
    fi
    mkdir -p "${dst}"
    cp -f "${HLSDK_BUILD}/${src_dir}/${lib}" "${dst}/${lib}"
done

mkdir -p "${EVIDENCE_DIR}"
cp -f "${SCRIPT_DIR}/manual_reload_test.cfg" "${OUT_VALVE}/manual_reload_test.cfg"

export XRT_NO_STDIN=true
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
export XR_RUNTIME_JSON="${MONADO_BUILD_DIR}/openxr_monado-dev.json"
export SDL_VIDEODRIVER=x11

pkill -9 -x monado-service 2>/dev/null || true
sleep 1
"${MONADO_BUILD_DIR}/src/xrt/targets/service/monado-service" \
    > "${EVIDENCE_DIR}/monado_service.log" 2>&1 &
MONADO_PID=$!
sleep 2

cleanup() {
    kill -TERM "${MONADO_PID}" 2>/dev/null || true
    pkill -9 -x monado-service 2>/dev/null || true
}
trap cleanup EXIT

cd "${REPO_DIR}/out"
set +e
timeout 150 ./xash3d -dev 1 -condebug -ref gl_vr +sv_cheats 1 \
    +map c1a0 +exec manual_reload_test.cfg > "${EVIDENCE_DIR}/manual_reload_engine.log" 2>&1
RUN_RC=$?
set -e

LOG="${EVIDENCE_DIR}/manual_reload_engine.log"
grep -q '\[VR_RELOAD\] manual eject' "${LOG}" || {
    log_err "manual eject stage not observed"
    tail -40 "${LOG}" >&2
    exit 1
}
grep -q '\[VR_RELOAD\] manual insert' "${LOG}" || {
    log_err "manual insert stage not observed"
    tail -40 "${LOG}" >&2
    exit 1
}
grep -q '\[VR_RELOAD\] manual complete' "${LOG}" || {
    log_err "manual complete stage not observed"
    tail -40 "${LOG}" >&2
    exit 1
}

log_ok "Glock manual reload stages passed (engine exit ${RUN_RC})"
grep '\[VR_RELOAD\] manual' "${LOG}" | tail -8
echo "Evidence: ${EVIDENCE_DIR}"
