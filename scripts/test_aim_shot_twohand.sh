#!/usr/bin/env bash
# Prove the firing line follows the aim pose, not the two-hand stabilizer.
#
# The engine log is split into two segments. In the control segment the harness
# hand transform carries no offset; in the stress segment it carries a 20 degree
# yaw, emulating what XR_ApplyTwoHandStabilizer used to add. The muzzle path must
# report the aim angles in both segments, because it must not follow the hand
# transform. Run from the repository root:
#
#   ./scripts/test_aim_shot_twohand.sh
#
# Evidence: out/qa/V1/twohand_<timestamp>/ with engine.log and twohand_aim.txt.
set -uo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MONADO_DIR="$(cd "${REPO_DIR}/../openxr-tooling/monado" && pwd)"
MONADO_BUILD_DIR="${MONADO_BUILD_DIR:-${MONADO_DIR}/build-sim}"
STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="${REPO_DIR}/out/qa/V1/twohand_${STAMP}"
CFG="twohand_probe.cfg"
TIMEOUT_SECS="${TIMEOUT_SECS:-150}"

log_info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()   { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_err()  { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

mkdir -p "${RUN_DIR}"
{
    echo "snd_mute_losefocus 0"
    echo "sv_cheats 1"
    echo "map testbed_scale"
    echo "wait 180"
    echo "vr_native_weapons 1"
    echo "vr_test_hands 1"
    echo "vr_test_hand_pitch 0"
    echo "vr_test_hand_yaw 0"
    echo "vr_test_hand_roll 0"
    echo "vr_hide_arms 0"
    echo "vr_weapon_anchor_root 1"
    echo "vr_grip_probe 1"
    echo "impulse 101"
    echo "wait 60"
    echo "give weapon_9mmhandgun"
    echo "use weapon_9mmhandgun"
    echo "wait 130"
    echo "vr_test_hand_transform_yaw 0"
    echo "echo TWO_HAND_CONTROL_BEGIN"
    echo "wait 20"
    echo "+attack"
    echo "wait 8"
    echo "-attack"
    echo "wait 20"
    echo "echo TWO_HAND_CONTROL_END"
    echo "vr_test_hand_transform_yaw 20"
    echo "echo TWO_HAND_STRESS_BEGIN"
    echo "wait 20"
    echo "+attack"
    echo "wait 8"
    echo "-attack"
    echo "wait 20"
    echo "echo TWO_HAND_STRESS_END"
    echo "quit"
} > "${REPO_DIR}/out/${CFG}"
cp -f "${REPO_DIR}/out/${CFG}" "${REPO_DIR}/out/valve/${CFG}"

pkill -9 -x monado-service 2>/dev/null || true
sleep 0.5
XRT_NO_STDIN=true "${MONADO_BUILD_DIR}/src/xrt/targets/service/monado-service" \
    > "${RUN_DIR}/monado.log" 2>&1 &
sleep 2
(
    export PYTHONDONTWRITEBYTECODE=1 XRT_NO_STDIN=true SDL_VIDEODRIVER=x11
    export __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia
    export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
    export XR_RUNTIME_JSON="${MONADO_BUILD_DIR}/openxr_monado-dev.json"
    cd "${REPO_DIR}/out"
    timeout "${TIMEOUT_SECS}s" ./xash3d -dev 1 -condebug -ref gl_vr +sv_cheats 1 \
        +exec "${CFG}" > "${RUN_DIR}/engine.log" 2>&1
)
RC=$?
pkill -9 -x monado-service 2>/dev/null || true

log_info "engine exit ${RC}"
if python3 "${SCRIPT_DIR}/check_twohand_aim.py" "${RUN_DIR}/engine.log" \
    | tee "${RUN_DIR}/twohand_aim.txt"; then
    log_ok "two-hand aim evidence ready"
else
    log_err "two-hand aim check failed"
fi
echo "${RUN_DIR}"
