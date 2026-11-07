#!/usr/bin/env bash
# W0: prove native weapon route selection and legacy fallback.
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MONADO_DIR="$(cd "${REPO_DIR}/../openxr-tooling/monado" && pwd)"
MONADO_BUILD_DIR="${MONADO_BUILD_DIR:-${MONADO_DIR}/build-sim}"
MODEL="v_9mmhandgun"
# The client searches more than one gamedir in the dev tree, so the fallback
# leg has to hide the model in every place it can resolve it.
NATIVE_DIRS=(
    "${REPO_DIR}/out/valve_vr/models/native"
    "${REPO_DIR}/out/valve/models/native"
)
NATIVE_DIR="${NATIVE_DIRS[0]}"
NATIVE_MDL="${NATIVE_DIR}/${MODEL}.mdl"
SOURCE_MDL="${REPO_DIR}/assets/valve_vr/models/${MODEL}.mdl"
CFG="native_weapon_test.cfg"
TIMEOUT_SECS="${TIMEOUT_SECS:-70}"

QA_SCRIPT="${SCRIPT_DIR}/qa_evidence.py"
RUN_DIR="$(python3 "$QA_SCRIPT" new --gate W0 --command "./scripts/test_native_weapon_fallback.sh" --device monado)"

log_info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()   { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_err()  { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

# Hide the native model without deleting a deployed asset.
HIDDEN=()
hide_native() {
    for dir in "${NATIVE_DIRS[@]}"; do
        if [ -f "${dir}/${MODEL}.mdl" ] && [ ! -f "${dir}/${MODEL}.mdl.w0hold" ]; then
            mv "${dir}/${MODEL}.mdl" "${dir}/${MODEL}.mdl.w0hold"
            HIDDEN+=( "${dir}/${MODEL}.mdl" )
        fi
    done
}

restore_native() {
    for path in "${HIDDEN[@]:-}"; do
        [ -n "$path" ] || continue
        if [ -f "${path}.w0hold" ]; then
            mv "${path}.w0hold" "$path"
        fi
    done
    HIDDEN=()
}

cleanup() {
    pkill -9 -x monado-service 2>/dev/null || true
    restore_native
}

trap cleanup EXIT

mkdir -p "${NATIVE_DIR}"
if [ ! -f "$NATIVE_MDL" ]; then
    cp -f "$SOURCE_MDL" "$NATIVE_MDL"
fi

export PYTHONDONTWRITEBYTECODE=1
export XRT_NO_STDIN=true
unset XRT_WINDOW_PEEK
unset XRT_DEBUG_GUI
python3 "${SCRIPT_DIR}/hide_monado_window.py" >/dev/null 2>&1 &
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
export XR_RUNTIME_JSON="${MONADO_BUILD_DIR}/openxr_monado-dev.json"
export SDL_VIDEODRIVER=x11
export LD_LIBRARY_PATH=".:${LD_LIBRARY_PATH:-}"

cat > "${REPO_DIR}/out/${CFG}" <<EOF
snd_mute_losefocus 0
wait 60
sv_cheats 1
vr_native_weapons 1
give item_suit
give weapon_9mmhandgun
use weapon_9mmhandgun
wait 30
quit
EOF
cp -f "${REPO_DIR}/out/${CFG}" "${REPO_DIR}/out/valve/${CFG}"

run_once() {
    local tag="$1"
    local log="$2"
    pkill -9 -x monado-service 2>/dev/null || true
    sleep 0.5
    "${MONADO_BUILD_DIR}/src/xrt/targets/service/monado-service" > "${RUN_DIR}/monado_${tag}.log" 2>&1 &
    sleep 1
    cd "${REPO_DIR}/out"
    set +e
    timeout "${TIMEOUT_SECS}s" ./xash3d -dev 1 -condebug -ref gl_vr +sv_cheats 1 \
        +map crossfire +exec "${CFG}" > "${log}" 2>&1
    local rc=$?
    set -e
    cd "${REPO_DIR}"
    pkill -9 -x monado-service 2>/dev/null || true
    return "$rc"
}

set +e
run_once native "${RUN_DIR}/native.log"
NATIVE_RC=$?
hide_native
run_once fallback "${RUN_DIR}/fallback.log"
FALLBACK_RC=$?
restore_native
set -e

NATIVE_ROUTE=no
FALLBACK_ROUTE=no
grep -Eq '\[VR_WEAPON_ROUTE\].*route=native' "${RUN_DIR}/native.log" && NATIVE_ROUTE=yes
grep -Eq '\[VR_WEAPON_ROUTE\].*route=(fallback|legacy)' "${RUN_DIR}/fallback.log" && FALLBACK_ROUTE=yes

cat > "${RUN_DIR}/README.md" <<EOF
# W0 — native weapon route and legacy fallback

- Native placeholder: \`out/valve_vr/models/native/${MODEL}.mdl\` (copy of the legacy asset; existence is the only test variable).
- The fallback leg hides the model in every searched gamedir and restores it afterwards.
- Native run exit: ${NATIVE_RC}; route found: ${NATIVE_ROUTE}.
- Fallback run exit: ${FALLBACK_RC}; route found: ${FALLBACK_ROUTE}.
- Logs: \`native.log\`, \`fallback.log\`.
EOF

if [ "$NATIVE_ROUTE" = yes ] && [ "$FALLBACK_ROUTE" = yes ]; then
    log_ok "native route selected and legacy fallback observed"
    python3 "$QA_SCRIPT" finish --run "$RUN_DIR" --exit-code 0 --status PASS --device monado --note "native route + legacy fallback observed" >/dev/null
    exit 0
fi

log_err "native route=${NATIVE_ROUTE}, fallback route=${FALLBACK_ROUTE}"
python3 "$QA_SCRIPT" finish --run "$RUN_DIR" --exit-code 1 --status FAIL --device monado --note "native=${NATIVE_ROUTE} fallback=${FALLBACK_ROUTE}" >/dev/null || true
exit 1
