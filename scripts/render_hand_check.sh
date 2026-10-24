#!/bin/bash
# Render the standalone VR hand model under the Monado simulated runtime.
#
# Installs the requested v_hand.mdl into out/valve/models, runs the engine on
# c1a0 with rimrook_hand_check.cfg, and leaves the eye dumps in the working
# directory. The caller decides what the dumps are named.
#
# Usage: scripts/render_hand_check.sh <path-to-v_hand.mdl> <output-prefix>
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODEL_SRC="${1:?usage: render_hand_check.sh <v_hand.mdl> <prefix>}"
PREFIX="${2:?usage: render_hand_check.sh <v_hand.mdl> <prefix>}"

MONADO_DIR="$(cd "${REPO_DIR}/../openxr-tooling/monado" && pwd)"
MONADO_BUILD_DIR="${MONADO_DIR}/build-sim"

export XRT_NO_STDIN=true
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
export XR_RUNTIME_JSON="${MONADO_BUILD_DIR}/openxr_monado-dev.json"
export SDL_VIDEODRIVER=x11
export LD_LIBRARY_PATH=".:${LD_LIBRARY_PATH:-}"

# The engine mounts valve_vr/ (dir_vr) with higher search priority than valve/,
# so the override must be installed there or a stale copy shadows it.
mkdir -p "${REPO_DIR}/out/valve_vr/models"
cp -f "${MODEL_SRC}" "${REPO_DIR}/out/valve_vr/models/v_hand.mdl"
cp -f "${MODEL_SRC}" "${REPO_DIR}/out/valve/models/v_hand.mdl"
cp -f "${SCRIPT_DIR}/rimrook_hand_check.cfg" "${REPO_DIR}/out/"
cp -f "${SCRIPT_DIR}/rimrook_hand_check.cfg" "${REPO_DIR}/out/valve/" 2>/dev/null || true
cp -f "${SCRIPT_DIR}/rimrook_hand_check.cfg" "${REPO_DIR}/out/valve_vr/" 2>/dev/null || true

pkill -9 -x monado-service 2>/dev/null || true
sleep 1
"${MONADO_BUILD_DIR}/src/xrt/targets/service/monado-service" \
    > "/tmp/opencode/${PREFIX}_monado.log" 2>&1 &
sleep 2

cd "${REPO_DIR}/out"
rm -f rimrook_hands_open.ppm rimrook_hands_curl.ppm
timeout 90 ./xash3d -dev 1 -condebug -ref gl_vr \
    +sv_cheats 1 +map c1a0 +exec rimrook_hand_check.cfg \
    > "/tmp/opencode/${PREFIX}_engine.log" 2>&1 || true

mv -f rimrook_hands_open.ppm "${PREFIX}_open.ppm" 2>/dev/null || true
mv -f rimrook_hands_curl.ppm "${PREFIX}_curl.ppm" 2>/dev/null || true

pkill -9 -x monado-service 2>/dev/null || true
echo "renders: $(ls -1 "${PREFIX}"_*.ppm 2>/dev/null | tr '\n' ' ')"
