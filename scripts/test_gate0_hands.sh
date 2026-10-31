#!/bin/bash
# Gate 0 hands: Monado-only comparison of the baked MMOD hand vs the
# standalone Rimrook hand on the crossbow, Glock and MP5.
# No Quest, no APK.
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -d "${REPO_DIR}/../openxr-tooling/monado" ]; then
    MONADO_DIR="$(cd "${REPO_DIR}/../openxr-tooling/monado" && pwd)"
else
    MONADO_DIR="$(cd "${REPO_DIR}/../monado" && pwd)"
fi

OUTPUT_DIR="${REPO_DIR}/out/evidence/${OUTPUT_SUBDIR:-gate0_hands}/monado_$(date +%Y%m%d_%H%M%S)"
TIMEOUT_SECS="${TIMEOUT_SECS:-150}"

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
    echo "[FAIL] Monado runtime missing at ${MONADO_BUILD_DIR}" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
export XRT_NO_STDIN=true
unset XRT_WINDOW_PEEK
unset XRT_DEBUG_GUI
python3 "${SCRIPT_DIR}/hide_monado_window.py" >/dev/null 2>&1 &
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
export XR_RUNTIME_JSON="$MONADO_MANIFEST"
export SDL_VIDEODRIVER=x11
export LD_LIBRARY_PATH=".:${LD_LIBRARY_PATH:-}"

pkill -9 -x monado-service 2>/dev/null || true
sleep 0.5
"$MONADO_SERVICE" > "${OUTPUT_DIR}/monado_service.log" 2>&1 &
SERVICE_PID=$!
cleanup() {
    kill -TERM "$SERVICE_PID" 2>/dev/null || true
    pkill -9 -x monado-service 2>/dev/null || true
}
trap cleanup EXIT
sleep 1

cd "${REPO_DIR}/out"
CFG_NAME="${CFG_NAME:-gate0_hands.cfg}"
cp -f "${REPO_DIR}/scripts/${CFG_NAME}" "${REPO_DIR}/out/${CFG_NAME}"
cp -f "${REPO_DIR}/scripts/${CFG_NAME}" "${REPO_DIR}/out/valve/${CFG_NAME}" 2>/dev/null || true

TEST_LOG="${OUTPUT_DIR}/gate0_engine.log"
echo "[INFO] Running Gate 0 under Monado (${TIMEOUT_SECS}s timeout)..."
set +e
timeout "${TIMEOUT_SECS}s" ./xash3d -dev 1 -condebug -ref gl_vr +sv_cheats 1 +exec "${CFG_NAME}" > "$TEST_LOG" 2>&1
RUN_EXIT=$?
set -e
echo "[INFO] Engine exit code: ${RUN_EXIT}"

for ppm in gate*.ppm; do
    [ -f "$ppm" ] || continue
    cp -f "$ppm" "${OUTPUT_DIR}/$ppm"
    convert "${OUTPUT_DIR}/$ppm" "${OUTPUT_DIR}/${ppm%.ppm}.png" 2>/dev/null || true
    rm -f "$ppm"
done

# Contact sheets per weapon/mode if ImageMagick montage is available.
for prefix in crossbow glock mp5; do
    for mode in hide0 hide2; do
        files=( "${OUTPUT_DIR}"/*_${prefix}_${mode}_*.png )
        if [ -e "${files[0]}" ] && command -v montage >/dev/null 2>&1; then
            montage "${files[@]}" -tile 3x -geometry 420x330+4+4 \
                -background '#16181c' "${OUTPUT_DIR}/${prefix}_${mode}_sheet.png" 2>/dev/null || true
        fi
    done
done

echo "[INFO] Evidence: ${OUTPUT_DIR}"
echo "[INFO] Logs: ${TEST_LOG}"
