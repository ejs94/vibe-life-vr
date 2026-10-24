#!/bin/bash
# Render the VR weapon-hand replacement check under the Monado simulated runtime.
#
# Runs the engine on c1a0 with weapon_hand_check.cfg (holds the 9mm handgun and
# dumps the eye with the weapon's own glove hidden vs. shown) and leaves the eye
# dumps in out/. The caller decides what the dumps are named.
#
# Usage: scripts/render_weapon_hand_check.sh <output-prefix>
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PREFIX="${1:?usage: render_weapon_hand_check.sh <prefix>}"

MONADO_DIR="$(cd "${REPO_DIR}/../openxr-tooling/monado" && pwd)"
MONADO_BUILD_DIR="${MONADO_DIR}/build-sim"

export XRT_NO_STDIN=true
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
export XR_RUNTIME_JSON="${MONADO_BUILD_DIR}/openxr_monado-dev.json"
export SDL_VIDEODRIVER=x11
export LD_LIBRARY_PATH=".:${LD_LIBRARY_PATH:-}"

cp -f "${SCRIPT_DIR}/weapon_hand_check.cfg" "${REPO_DIR}/out/"
cp -f "${SCRIPT_DIR}/weapon_hand_check.cfg" "${REPO_DIR}/out/valve/" 2>/dev/null || true

pkill -9 -x monado-service 2>/dev/null || true
sleep 1
"${MONADO_BUILD_DIR}/src/xrt/targets/service/monado-service" \
    > "/tmp/opencode/${PREFIX}_monado.log" 2>&1 &
sleep 2

cd "${REPO_DIR}/out"
rm -f weaponhand_hidden.ppm weaponhand_vanilla.ppm
timeout 90 ./xash3d -dev 1 -condebug -ref gl_vr \
    +sv_cheats 1 +map c1a0 +exec weapon_hand_check.cfg \
    > "/tmp/opencode/${PREFIX}_engine.log" 2>&1 || true

mv -f weaponhand_hidden.ppm "${PREFIX}_hidden.ppm" 2>/dev/null || true
mv -f weaponhand_vanilla.ppm "${PREFIX}_vanilla.ppm" 2>/dev/null || true

pkill -9 -x monado-service 2>/dev/null || true
echo "renders: $(ls -1 "${PREFIX}"_*.ppm 2>/dev/null | tr '\n' ' ')"
