#!/usr/bin/env bash
# Capture every native viewmodel from fixed cameras in the scale test bed.
#
# The point is visual regression, not a pass/fail gate: the run produces a
# labelled contact sheet (lateral, front, top per weapon) with a 10 cm scale
# bar and a 1 m floor grid in frame, so scale and placement can be judged
# without a headset.
#
# Usage: scripts/weapon_visual_sweep.sh [--no-sheet]
set -uo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MONADO_DIR="$(cd "${REPO_DIR}/../openxr-tooling/monado" && pwd)"
MONADO_BUILD_DIR="${MONADO_BUILD_DIR:-${MONADO_DIR}/build-sim}"
STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="${REPO_DIR}/out/qa/V1/weapons_${STAMP}"
CFG="weapon_sweep.cfg"
TIMEOUT_SECS="${TIMEOUT_SECS:-150}"

log_info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()   { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_err()  { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

# model:<weapon classname> pairs. v_satchel_radio is the detonator viewmodel and
# has no direct give/use classname, so it is not swept here.
WEAPONS=(
    "v_9mmhandgun:weapon_9mmhandgun"
    "v_357:weapon_357"
    "v_9mmAR:weapon_9mmAR"
    "v_shotgun:weapon_shotgun"
    "v_crossbow:weapon_crossbow"
    "v_rpg:weapon_rpg"
    "v_gauss:weapon_gauss"
    "v_egon:weapon_egon"
    "v_hgun:weapon_hornetgun"
    "v_grenade:weapon_handgrenade"
    "v_tripmine:weapon_tripmine"
    "v_satchel:weapon_satchel"
    "v_squeak:weapon_snark"
    "v_crowbar:weapon_crowbar"
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
    echo "vr_test_hand_offset \"0 0 0\""
    echo "vr_test_head 1"
    echo "vr_test_head_pitch 0"
    echo "vr_test_head_yaw 0"
    echo "vr_test_head_roll 0"
    echo "vr_hide_arms 0"
    echo "vr_offhand_render 0"
    echo "vr_hands_always_visible 0"
    echo "vr_debug_hand_pose 0"
    echo "vr_grip_probe 0"
    echo "vr_test_camera_fov 55"
    echo "vr_test_camera_distance 34"
    echo "vr_test_camera_aim 6"
    echo "vr_test_camera_target 0"
    echo "impulse 101"
    echo "wait 60"
    for entry in "${WEAPONS[@]}"; do
        model="${entry%%:*}"
        weapon="${entry##*:}"
        echo "give ${weapon}"
    done
    for entry in "${WEAPONS[@]}"; do
        model="${entry%%:*}"
        weapon="${entry##*:}"
        echo "use ${weapon}"
        echo "wait 45"
        echo "vr_test_camera 1"
        echo "wait 25"
        echo "vr_dumpeye w_${model}_right.ppm"
        echo "wait 20"
        echo "vr_test_camera 3"
        echo "wait 25"
        echo "vr_dumpeye w_${model}_front.ppm"
        echo "wait 20"
        echo "vr_test_camera 4"
        echo "wait 25"
        echo "vr_dumpeye w_${model}_left.ppm"
        echo "wait 20"
        echo "vr_test_camera 0"
        echo "wait 10"
    done
    echo "wait 30"
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
    timeout "${TIMEOUT_SECS}s" ./xash3d -dev 1 -condebug -ref gl_vr \
        +sv_cheats 1 +exec "${CFG}" > "${RUN_DIR}/engine.log" 2>&1
)
RC=$?
pkill -9 -x monado-service 2>/dev/null || true

CAPTURED=0
rm -f "${REPO_DIR}"/out/vr_eye*.ppm
for ppm in "${REPO_DIR}"/out/w_*.ppm; do
    [ -f "${ppm}" ] || continue
    base="$(basename "${ppm}" .ppm)"
    if convert "${ppm}" "${RUN_DIR}/${base}.png" 2>/dev/null; then
        CAPTURED=$((CAPTURED + 1))
    fi
    rm -f "${ppm}"
done

ROUTES=$(grep -c "\[VR_WEAPON_ROUTE\].*route=native" "${RUN_DIR}/engine.log" 2>/dev/null || true)
log_info "engine exit ${RC}; ${CAPTURED} captures; ${ROUTES} native route lines"
if [ "${ROUTES}" -lt 14 ]; then
    log_err "expected at least 14 native route lines, got ${ROUTES}"
fi
if [ "${CAPTURED}" -lt 42 ]; then
    log_err "expected 42 captures (14 weapons x 3 views), got ${CAPTURED}"
fi

if [ "${1:-}" != "--no-sheet" ] && [ "${CAPTURED}" -gt 0 ]; then
    if python3 "${SCRIPT_DIR}/make_weapon_contact_sheet.py" "${RUN_DIR}"; then
        log_ok "contact sheet ready"
        if python3 "${SCRIPT_DIR}/check_weapon_captures.py" "${RUN_DIR}"; then
            log_ok "captures are not empty"
        else
            log_err "capture checks failed"
            exit 1
        fi
    else
        log_err "contact sheet failed"
        exit 1
    fi
fi

echo "${RUN_DIR}"
exit 0
