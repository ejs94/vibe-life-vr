#!/usr/bin/env bash
# ==============================================================================
# Weapon visual review capture (non-blocking human review)
# ==============================================================================
# Captures a weapon viewmodel from a world-space turntable and during idle,
# fire and reload sequences under the simulated Monado runtime. The output is
# a set of GIFs and a labelled contact sheet for human inspection. This is a
# review aid, not a gate: it never decides PASS/FAIL and never deploys an asset.
#
# Usage:
#   scripts/capture_weapon_review.sh [model.mdl] [label]
#
# Defaults:
#   model: out/viewmodel_work/glock_repair/v_9mmhandgun.mdl
#   label: glock_repair
#
# Output: out/qa/V1/runs/<timestamp>/ (or the directory printed by the script)
# ==============================================================================
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODEL="${1:-${REPO_DIR}/out/viewmodel_work/glock_repair/v_9mmhandgun.mdl}"
LABEL="${2:-glock_repair}"
MODEL_NAME="v_9mmhandgun"
CFG_NAME="weapon_review.cfg"
TIMEOUT_SECS="${TIMEOUT_SECS:-140}"

if [ ! -f "$MODEL" ]; then
    echo "[FAIL] model not found: $MODEL" >&2
    exit 1
fi

QA_SCRIPT="${SCRIPT_DIR}/qa_evidence.py"
REVIEW_DIR="$(python3 "$QA_SCRIPT" new --gate V1 --command "./scripts/capture_weapon_review.sh $MODEL $LABEL" --device monado)"
if command -v magick >/dev/null 2>&1; then
    IM=(magick)
    MONTAGE=(magick montage)
else
    IM=(convert)
    MONTAGE=(montage)
fi
BACKUP_DIR="${REVIEW_DIR}/backup"
MONADO_DIR="${REPO_DIR}/../openxr-tooling/monado"
MONADO_BUILD_DIR="${MONADO_BUILD_DIR:-${MONADO_DIR}/build-sim}"

log_info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()   { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_err()  { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

if [ ! -x "${MONADO_BUILD_DIR}/src/xrt/targets/service/monado-service" ]; then
    log_err "Monado runtime missing at ${MONADO_BUILD_DIR}"
    python3 "$QA_SCRIPT" finish --run "$REVIEW_DIR" --exit-code 1 --status FAIL --device monado --note "Monado runtime missing" >/dev/null 2>&1 || true
    exit 1
fi

mkdir -p "$BACKUP_DIR" "$REVIEW_DIR/frames"
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

mkdir -p "${REPO_DIR}/out/valve/models" "${REPO_DIR}/out/valve_vr/models"
if [ -f "${REPO_DIR}/out/valve/models/${MODEL_NAME}.mdl" ]; then
    cp -f "${REPO_DIR}/out/valve/models/${MODEL_NAME}.mdl" "${BACKUP_DIR}/valve.mdl"
else
    touch "${BACKUP_DIR}/valve.missing"
fi
if [ -f "${REPO_DIR}/out/valve_vr/models/${MODEL_NAME}.mdl" ]; then
    cp -f "${REPO_DIR}/out/valve_vr/models/${MODEL_NAME}.mdl" "${BACKUP_DIR}/valve_vr.mdl"
else
    touch "${BACKUP_DIR}/valve_vr.missing"
fi

restore_models() {
    if [ -f "${BACKUP_DIR}/valve.missing" ]; then
        rm -f "${REPO_DIR}/out/valve/models/${MODEL_NAME}.mdl"
    elif [ -f "${BACKUP_DIR}/valve.mdl" ]; then
        cp -f "${BACKUP_DIR}/valve.mdl" "${REPO_DIR}/out/valve/models/${MODEL_NAME}.mdl"
    fi
    if [ -f "${BACKUP_DIR}/valve_vr.missing" ]; then
        rm -f "${REPO_DIR}/out/valve_vr/models/${MODEL_NAME}.mdl"
    elif [ -f "${BACKUP_DIR}/valve_vr.mdl" ]; then
        cp -f "${BACKUP_DIR}/valve_vr.mdl" "${REPO_DIR}/out/valve_vr/models/${MODEL_NAME}.mdl"
    fi
}
cleanup() {
    pkill -9 -x monado-service 2>/dev/null || true
    rm -f "${REPO_DIR}/out/vr_eye0.ppm"
    restore_models
}
trap cleanup EXIT

cp -f "$MODEL" "${REPO_DIR}/out/valve/models/${MODEL_NAME}.mdl"
cp -f "$MODEL" "${REPO_DIR}/out/valve_vr/models/${MODEL_NAME}.mdl"

pkill -9 -x monado-service 2>/dev/null || true
sleep 0.5
"${MONADO_BUILD_DIR}/src/xrt/targets/service/monado-service" > "${REVIEW_DIR}/monado_service.log" 2>&1 &
sleep 1

cat > "${REPO_DIR}/out/${CFG_NAME}" <<EOF
snd_mute_losefocus 0
wait 60
sv_cheats 1
give item_suit
give weapon_9mmhandgun
use weapon_9mmhandgun
wait 30
vr_test_camera 5
vr_test_camera_distance 42
vr_test_camera_fov 45
vr_test_camera_aim 8
vr_test_camera_target 0
vr_weapon_true_depth 0
vr_test_hands 1
vr_test_hand_pitch 0
vr_test_hand_yaw 0
vr_debug_hand_pose 0
r_drawviewmodel 1
vr_holster 0
vr_hide_arms 2
vr_hands_always_visible 0
vr_offhand_render 0
wait 20

// Turntable: 36 azimuth frames at a 15-degree elevation.
vr_test_camera_elevation 15
EOF

frame=0
for azimuth in $(seq 0 10 350); do
    printf 'vr_test_camera_azimuth %s\nwait 3\nvr_dumpeye review_orbit_%03d.ppm\n' "$azimuth" "$frame" >> "${REPO_DIR}/out/${CFG_NAME}"
    frame=$((frame + 1))
done

cat >> "${REPO_DIR}/out/${CFG_NAME}" <<EOF

// Elevation sweep: front three-quarter from below to above.
vr_test_camera_azimuth 45
EOF

frame=0
for elevation in $(seq -60 10 60); do
    printf 'vr_test_camera_elevation %s\nwait 3\nvr_dumpeye review_elev_%03d.ppm\n' "$elevation" "$frame" >> "${REPO_DIR}/out/${CFG_NAME}"
    frame=$((frame + 1))
done

cat >> "${REPO_DIR}/out/${CFG_NAME}" <<EOF

// Idle animation at a three-quarter view.
vr_test_camera_azimuth 0
vr_test_camera_elevation 10
EOF

for frame in $(seq -w 0 9); do
    printf 'wait 4\nvr_dumpeye review_idle_%s.ppm\n' "$frame" >> "${REPO_DIR}/out/${CFG_NAME}"
done

for angle in 0 90 180; do
    cat >> "${REPO_DIR}/out/${CFG_NAME}" <<EOF

// Fire sequence at azimuth ${angle}.
vr_test_camera_azimuth ${angle}
+attack
EOF
    for frame in $(seq -w 0 7); do
        printf 'wait 2\nvr_dumpeye review_fire_%s_%s.ppm\n' "$angle" "$frame" >> "${REPO_DIR}/out/${CFG_NAME}"
    done
    printf -- '-attack\nwait 10\n' >> "${REPO_DIR}/out/${CFG_NAME}"
done

for angle in 0 90 180; do
    cat >> "${REPO_DIR}/out/${CFG_NAME}" <<EOF

// Reload sequence at azimuth ${angle}.
vr_test_camera_azimuth ${angle}
vr_test_btn_reload 1
wait 2
vr_test_btn_reload 0
EOF
    for frame in $(seq -w 0 13); do
        printf 'wait 3\nvr_dumpeye review_reload_%s_%s.ppm\n' "$angle" "$frame" >> "${REPO_DIR}/out/${CFG_NAME}"
    done
done

printf 'wait 20\nquit\n' >> "${REPO_DIR}/out/${CFG_NAME}"
cp -f "${REPO_DIR}/out/${CFG_NAME}" "${REPO_DIR}/out/valve/${CFG_NAME}"

cd "${REPO_DIR}/out"
set +e
timeout "${TIMEOUT_SECS}s" ./xash3d -dev 1 -condebug -ref gl_vr +sv_cheats 1 \
    +map crossfire +exec "${CFG_NAME}" > "${REVIEW_DIR}/engine.log" 2>&1
RUN_RC=$?
set -e

for ppm in review_*.ppm; do
    [ -f "$ppm" ] || continue
    cp -f "$ppm" "${REVIEW_DIR}/frames/${ppm}"
    "${IM[@]}" "${REVIEW_DIR}/frames/${ppm}" "${REVIEW_DIR}/frames/${ppm%.ppm}.png" 2>/dev/null || true
    rm -f "$ppm" "${REVIEW_DIR}/frames/${ppm}"
done

make_gif() {
    local pattern="$1"
    local output="$2"
    local delay="${3:-6}"
    local files=( ${REVIEW_DIR}/frames/${pattern}*.png )
    if [ -e "${files[0]}" ]; then
        "${IM[@]}" -delay "$delay" -loop 0 "${files[@]}" "${REVIEW_DIR}/${output}"
    fi
}

make_gif "review_orbit_" "turntable.gif" 5
make_gif "review_elev_" "elevation.gif" 8
make_gif "review_idle_" "idle.gif" 8
make_gif "review_fire_0_" "fire_az000.gif" 8
make_gif "review_fire_90_" "fire_az090.gif" 8
make_gif "review_fire_180_" "fire_az180.gif" 8
make_gif "review_reload_0_" "reload_az000.gif" 8
make_gif "review_reload_90_" "reload_az090.gif" 8
make_gif "review_reload_180_" "reload_az180.gif" 8

if command -v montage >/dev/null 2>&1; then
    "${MONTAGE[@]}" "${REVIEW_DIR}/frames/review_orbit_000.png" \
        "${REVIEW_DIR}/frames/review_orbit_009.png" \
        "${REVIEW_DIR}/frames/review_orbit_018.png" \
        "${REVIEW_DIR}/frames/review_orbit_027.png" \
        "${REVIEW_DIR}/frames/review_elev_006.png" \
        "${REVIEW_DIR}/frames/review_elev_012.png" \
        -tile 3x2 -geometry 420x420+4+4 -background '#16181c' \
        "${REVIEW_DIR}/contact_sheet.png" 2>/dev/null || true
fi

cat > "${REVIEW_DIR}/README.md" <<EOF
# Weapon visual review: ${LABEL}

This is a human review aid, not a gate. It shows the engine viewmodel from a
world-space turntable and during idle, fire and reload.

- Model under review: \`${MODEL_NAME}.mdl\`
- Turntable: \`turntable.gif\`
- Elevation sweep: \`elevation.gif\`
- Idle: \`idle.gif\`
- Fire: \`fire_az000.gif\`, \`fire_az090.gif\`, \`fire_az180.gif\`
- Reload: \`reload_az000.gif\`, \`reload_az090.gif\`, \`reload_az180.gif\`
- Contact sheet: \`contact_sheet.png\`
- Engine log: \`engine.log\`

The model is temporarily copied to \`out/valve/models\` and
\`out/valve_vr/models\` for the capture and restored on exit.
EOF

printf 'engine_exit=%s\n' "$RUN_RC" > "${REVIEW_DIR}/result.txt"
if [ "$RUN_RC" -eq 0 ] || [ "$RUN_RC" -eq 124 ]; then
    STATUS=INCONCLUSIVE
    log_ok "Visual review artifacts written to ${REVIEW_DIR}"
else
    STATUS=FAIL
    log_err "Engine review capture failed (exit ${RUN_RC}); see ${REVIEW_DIR}/engine.log"
fi
python3 "$QA_SCRIPT" finish --run "$REVIEW_DIR" --exit-code "$RUN_RC" --status "$STATUS" --device monado --note "Human visual review artifact; not a gate" >/dev/null 2>&1 || true
echo "Review directory: ${REVIEW_DIR}"
