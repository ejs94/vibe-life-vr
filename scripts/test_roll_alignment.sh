#!/bin/bash
# ==============================================================================
# R2 - Authored barrel/aim alignment under wrist roll
# ==============================================================================
# The renderer aligns the AUTHORED two-point barrel basis (muzzle_pos -> hud_pos)
# to the aim direction. A quaternion/forward-only alignment can still look
# correct at identity and pure yaw, yet drift when the wrist rolls: the
# vr-modding-playbook measured 0.00 degrees at identity/yaw but 10.70 / 19.85 /
# 28.21 degrees at roll 45 / 90 / 180 through two equivalent Euler chains.
#
# M1 forces the hand angles to zero, so it cannot see that error. This gate runs
# the same probe four times with vr_test_hand_roll = 0, 45, 90, 180 and checks
# the [VR_AIM] telemetry with scripts/check_weapon_alignment.py.
#
# Evidence: out/qa/R2/runs/<timestamp>/roll_<deg>.log plus roll_summary.txt.
# Exit 0 only when all four rolls pass the alignment check.
# ==============================================================================

set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_DIR}"

TEMPLATE="${SCRIPT_DIR}/roll_probe.cfg"
CHECK_SCRIPT="${SCRIPT_DIR}/check_weapon_alignment.py"
GROUND_TRUTH="out/qa/P2/bore_ground_truth.json"
MAX_ANGLE="${MAX_ANGLE:-8.0}"
ENGINE_TIMEOUT="${ENGINE_TIMEOUT:-100}"
ROLLS="0 45 90 180"

log_info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()   { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_err()  { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

strip_ansi() { sed -e 's/\x1b\[[0-9;]*[A-Za-z]//g' -e 's/\x1b[@-Z\\-_]//g'; }

# ------------------------------------------------------------------------------
# Runtime discovery. XR_RUNTIME_JSON must be absolute: the engine runs with
# cwd=out, and a relative manifest path silently fails xrCreateInstance.
# ------------------------------------------------------------------------------
if [ -z "${MONADO_BUILD_DIR:-}" ]; then
    if [ -d "${REPO_DIR}/../openxr-tooling/monado/build-sim" ]; then
        MONADO_BUILD_DIR="${REPO_DIR}/../openxr-tooling/monado/build-sim"
    else
        MONADO_BUILD_DIR="${REPO_DIR}/../monado/build"
    fi
fi
MONADO_BUILD_DIR="$(cd "${MONADO_BUILD_DIR}" && pwd)"
MONADO_SERVICE="${MONADO_BUILD_DIR}/src/xrt/targets/service/monado-service"
XR_RUNTIME_JSON="${MONADO_BUILD_DIR}/openxr_monado-dev.json"

for f in out/xash3d out/libref_gl_vr.so "${TEMPLATE}" "${CHECK_SCRIPT}" "${GROUND_TRUTH}"; do
    if [ ! -e "${f}" ]; then
        log_err "missing required path: ${f}"
        exit 1
    fi
done
if [ ! -x "${MONADO_SERVICE}" ] || [ ! -f "${XR_RUNTIME_JSON}" ]; then
    log_err "Monado build artifacts missing in ${MONADO_BUILD_DIR}"
    exit 1
fi

RUN_DIR="$(python3 "${REPO_DIR}/scripts/qa_evidence.py" new --gate R2 \
    --command "./scripts/test_roll_alignment.sh" --device monado)"
mkdir -p "${RUN_DIR}" out/valve

SERVICE_PID=""
cleanup() {
    if [ -n "${SERVICE_PID}" ]; then
        kill "${SERVICE_PID}" 2>/dev/null || true
        wait "${SERVICE_PID}" 2>/dev/null || true
        SERVICE_PID=""
    fi
    pkill -9 -x monado-service 2>/dev/null || true
    rm -f out/roll_probe.cfg out/valve/roll_probe.cfg
    # The engine dumps its eye buffer into cwd (out/); keep evidence in out/qa only.
    rm -f out/vr_eye0.ppm
}
trap cleanup EXIT INT TERM

start_service() {
    stop_service
    env XRT_NO_STDIN=true "${MONADO_SERVICE}" \
        > "${RUN_DIR}/monado_service.log" 2>&1 < /dev/null &
    SERVICE_PID=$!
    sleep 1.5
    if ! kill -0 "${SERVICE_PID}" 2>/dev/null; then
        log_err "monado-service exited during startup; see ${RUN_DIR}/monado_service.log"
        return 1
    fi
}

stop_service() {
    if [ -n "${SERVICE_PID}" ]; then
        kill "${SERVICE_PID}" 2>/dev/null || true
        wait "${SERVICE_PID}" 2>/dev/null || true
        SERVICE_PID=""
    fi
    pkill -9 -x monado-service 2>/dev/null || true
    sleep 0.5
}

log_info "Monado build: ${MONADO_BUILD_DIR}"
log_info "Run directory: ${RUN_DIR}"

SUMMARY="${RUN_DIR}/roll_summary.txt"
: > "${SUMMARY}"
declare -a ROWS=()
OVERALL_RC=0

for ROLL in ${ROLLS}; do
    log_info "=========== wrist roll ${ROLL} deg ==========="

    sed "s/@ROLL@/${ROLL}/g" "${TEMPLATE}" > out/roll_probe.cfg
    sed "s/@ROLL@/${ROLL}/g" "${TEMPLATE}" > out/valve/roll_probe.cfg

    start_service

    LOG="${RUN_DIR}/roll_${ROLL}.log"
    set +e
    (
        cd out && \
        env PYTHONDONTWRITEBYTECODE=1 \
            XRT_NO_STDIN=true \
            SDL_VIDEODRIVER=x11 \
            __NV_PRIME_RENDER_OFFLOAD=1 \
            __GLX_VENDOR_LIBRARY_NAME=nvidia \
            VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json \
            XR_RUNTIME_JSON="${XR_RUNTIME_JSON}" \
            LD_LIBRARY_PATH=".:${LD_LIBRARY_PATH:-}" \
            timeout "${ENGINE_TIMEOUT}" ./xash3d -dev 1 -condebug -ref gl_vr \
                +sv_cheats 1 +exec roll_probe.cfg
    ) > "${LOG}" 2>&1
    ENGINE_RC=$?
    set -e
    log_info "engine rc=${ENGINE_RC} (124 = timeout, the cfg should quit cleanly)"

    stop_service

    AIM_LINE="$(strip_ansi < "${LOG}" | grep '\[VR_AIM\]' | grep 'v_9mmhandgun' | tail -n 1 || true)"
    if [ -n "${AIM_LINE}" ]; then
        log_info "telemetry: ${AIM_LINE}"
    else
        log_err "no [VR_AIM] sample for v_9mmhandgun in ${LOG}"
    fi
    ANGLE="$(printf '%s\n' "${AIM_LINE}" | sed -n 's/.*angle=\([^ ]*\).*/\1/p')"
    [ -n "${ANGLE}" ] || ANGLE="n/a"

    set +e
    python3 "${CHECK_SCRIPT}" --log "${LOG}" --min-weapons 1 \
        --max-angle "${MAX_ANGLE}" --ground-truth "${GROUND_TRUTH}"
    ALIGN_RC=$?
    set -e

    if [ "${ALIGN_RC}" -eq 0 ]; then
        VERDICT="PASS"
        log_ok "roll ${ROLL}: angle=${ANGLE} PASS"
    else
        VERDICT="FAIL"
        OVERALL_RC=1
        log_err "roll ${ROLL}: angle=${ANGLE} FAIL (check rc=${ALIGN_RC})"
    fi
    ROWS+=("${ROLL}|${ANGLE}|${VERDICT}")
    printf '%s|%s|%s|engine_rc=%s align_rc=%s\n' \
        "${ROLL}" "${ANGLE}" "${VERDICT}" "${ENGINE_RC}" "${ALIGN_RC}" >> "${SUMMARY}"
done

echo ""
echo "ROLL | angle | verdict"
echo "-----|-------|--------"
for ROW in "${ROWS[@]}"; do
    echo "${ROW}"
done | tee -a "${SUMMARY}"

if [ "${OVERALL_RC}" -eq 0 ]; then
    log_ok "R2 PASS: authored barrel/aim alignment holds at roll 0/45/90/180"
else
    log_err "R2 FAIL: see ${SUMMARY}"
fi
cp "${SUMMARY}" out/qa/R2/roll_summary.txt
cp "${SUMMARY}" "${RUN_DIR}/gate.log"

QA_STATUS="FAIL"
if [ "${OVERALL_RC}" -eq 0 ]; then
    QA_STATUS="PASS"
fi
python3 "${REPO_DIR}/scripts/qa_evidence.py" finish \
    --run "${RUN_DIR}" \
    --exit-code "${OVERALL_RC}" \
    --status "${QA_STATUS}" \
    --device monado \
    --note "Roll sweep 0/45/90/180: ${QA_STATUS}"
exit "${OVERALL_RC}"
