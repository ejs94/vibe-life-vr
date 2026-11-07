#!/usr/bin/env bash
# Fire one shot per native gun in the scale test bed and record where the shot
# starts, which way it travels and whether it follows the visible barrel.
#
# Evidence: out/qa/V1/shots_<timestamp>/ with the engine log, one capture per
# weapon and a parsed table from check_shot_origin.py.
set -uo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MONADO_DIR="$(cd "${REPO_DIR}/../openxr-tooling/monado" && pwd)"
MONADO_BUILD_DIR="${MONADO_BUILD_DIR:-${MONADO_DIR}/build-sim}"
STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="${REPO_DIR}/out/qa/V1/shots_${STAMP}"
CFG="shot_probe.cfg"
TIMEOUT_SECS="${TIMEOUT_SECS:-150}"

log_info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()   { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_err()  { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

# Hitscan guns only: projectiles and beams do not report an impact on the
# first frame, so they cannot prove where the shot started.
WEAPONS=(
    "v_9mmhandgun:weapon_9mmhandgun"
    "v_357:weapon_357"
    "v_shotgun:weapon_shotgun"
    "v_gauss:weapon_gauss"
)

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
    echo 'vr_test_hand_offset "0 0 0"'
    echo "vr_test_head 1"
    echo "vr_test_head_pitch 0"
    echo "vr_test_head_yaw 0"
    echo "vr_test_head_roll 0"
    echo "vr_hide_arms 0"
    echo "vr_offhand_render 0"
    echo "vr_debug_impacts 1"
    echo "vr_weapon_anchor_root 1"
    echo "vr_grip_probe 1"
    echo "impulse 101"
    echo "wait 60"
    for entry in "${WEAPONS[@]}"; do echo "give ${entry##*:}"; done
    for entry in "${WEAPONS[@]}"; do
        model="${entry%%:*}"
        weapon="${entry##*:}"
        echo "echo SHOT_PROBE weapon=${weapon}"
        echo "use ${weapon}"
        echo "wait 130"
        echo "+attack"
        echo "wait 8"
        echo "-attack"
        echo "wait 20"
        echo "vr_dumpeye shot_${model}.ppm"
        echo "wait 30"
    done
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

for ppm in "${REPO_DIR}"/out/shot_*.ppm; do
    [ -f "${ppm}" ] || continue
    convert "${ppm}" "${RUN_DIR}/$(basename "${ppm}" .ppm).png" 2>/dev/null || true
    rm -f "${ppm}"
done
rm -f "${REPO_DIR}"/out/vr_eye*.ppm

log_info "engine exit ${RC}"
if python3 "${SCRIPT_DIR}/check_shot_origin.py" "${RUN_DIR}/engine.log" | tee "${RUN_DIR}/shot_origin.txt"; then
    log_ok "shot origin evidence ready"
else
    log_err "shot origin checks failed"
fi
echo "${RUN_DIR}"
