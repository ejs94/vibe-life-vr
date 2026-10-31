#!/usr/bin/env bash
# ==============================================================================
# Side-by-side weapon visual review (non-blocking human review)
# ==============================================================================
# Runs capture_weapon_review.sh for an original and a patched model, then
# builds labelled comparison GIFs and a contact sheet. This is a review aid,
# not a gate. It does not deploy assets and does not decide PASS/FAIL.
#
# Usage:
#   scripts/compare_weapon_review.sh [patched.mdl] [original.mdl] [label]
#
# Defaults:
#   patched:  out/viewmodel_work/glock_repair/v_9mmhandgun.mdl
#   original: assets/valve_vr/models/v_9mmhandgun.mdl
#   label:    glock
# ==============================================================================
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PATCHED="${1:-${REPO_DIR}/out/viewmodel_work/glock_repair/v_9mmhandgun.mdl}"
ORIGINAL="${2:-${REPO_DIR}/assets/valve_vr/models/v_9mmhandgun.mdl}"
LABEL="${3:-glock}"
COMPARE_DIR="${REPO_DIR}/out/qa/V1/compare_${LABEL}"

if [ ! -f "$PATCHED" ]; then
    echo "[FAIL] patched model not found: $PATCHED" >&2
    exit 1
fi
if [ ! -f "$ORIGINAL" ]; then
    echo "[FAIL] original model not found: $ORIGINAL" >&2
    exit 1
fi

mkdir -p "${REPO_DIR}/out/qa/V1"
ORIG_LOG="$(mktemp -p "${REPO_DIR}/out/qa/V1" compare-original-XXXXXX.log)"
PATCH_LOG="$(mktemp -p "${REPO_DIR}/out/qa/V1" compare-patched-XXXXXX.log)"
trap 'rm -f "$ORIG_LOG" "$PATCH_LOG"' EXIT

echo "[INFO] Capturing original model..."
"${SCRIPT_DIR}/capture_weapon_review.sh" "$ORIGINAL" "${LABEL}_original" | tee "$ORIG_LOG"
ORIG_DIR="$(sed -n 's/^Review directory: //p' "$ORIG_LOG" | tail -1)"

echo "[INFO] Capturing patched model..."
"${SCRIPT_DIR}/capture_weapon_review.sh" "$PATCHED" "${LABEL}_patched" | tee "$PATCH_LOG"
PATCH_DIR="$(sed -n 's/^Review directory: //p' "$PATCH_LOG" | tail -1)"

if [ -z "$ORIG_DIR" ] || [ -z "$PATCH_DIR" ]; then
    echo "[FAIL] could not determine review directories" >&2
    exit 1
fi

if command -v magick >/dev/null 2>&1; then
    IM=(magick)
    MONTAGE=(magick montage)
else
    IM=(convert)
    MONTAGE=(montage)
fi

rm -rf "$COMPARE_DIR"
mkdir -p "$COMPARE_DIR/frames"

label_image() {
    local source="$1"
    local label="$2"
    local output="$3"
    "${IM[@]}" "$source" -gravity northwest -pointsize 22 -fill white \
        -undercolor '#000000AA' -annotate +10+10 "$label" "$output"
}

compare_pattern() {
    local pattern="$1"
    local gif="$2"
    local delay="$3"
    local frame
    for frame in "${PATCH_DIR}"/frames/${pattern}*.png; do
        [ -f "$frame" ] || continue
        local base
        base="$(basename "$frame")"
        label_image "${ORIG_DIR}/frames/${base}" "ORIGINAL" "${COMPARE_DIR}/frames/o_${base}"
        label_image "$frame" "PATCHED" "${COMPARE_DIR}/frames/p_${base}"
        "${IM[@]}" "${COMPARE_DIR}/frames/o_${base}" "${COMPARE_DIR}/frames/p_${base}" \
            +append "${COMPARE_DIR}/frames/c_${base}"
    done
    if compgen -G "${COMPARE_DIR}/frames/c_${pattern}*.png" >/dev/null; then
        "${IM[@]}" -delay "$delay" -loop 0 "${COMPARE_DIR}"/frames/c_${pattern}*.png \
            "${COMPARE_DIR}/${gif}"
    fi
}

compare_pattern "review_orbit_" "turntable_compare.gif" 5
compare_pattern "review_elev_" "elevation_compare.gif" 8
compare_pattern "review_reload_0_" "reload_compare.gif" 8

"${MONTAGE[@]}" \
    "${ORIG_DIR}/frames/review_orbit_000.png" \
    "${ORIG_DIR}/frames/review_orbit_009.png" \
    "${ORIG_DIR}/frames/review_orbit_018.png" \
    "${PATCH_DIR}/frames/review_orbit_000.png" \
    "${PATCH_DIR}/frames/review_orbit_009.png" \
    "${PATCH_DIR}/frames/review_orbit_018.png" \
    -tile 3x2 -geometry 420x420+4+4 -background '#16181c' \
    "${COMPARE_DIR}/contact_sheet_compare.png" 2>/dev/null || true

cat > "${COMPARE_DIR}/README.md" <<EOF
# Weapon visual comparison: ${LABEL}

Top row: original model. Bottom row: patched model.
This is a human review aid, not a gate.

- \`turntable_compare.gif\` — 36 azimuth frames.
- \`elevation_compare.gif\` — front three-quarter from below to above.
- \`reload_compare.gif\` — staged reload at azimuth 0.
- \`contact_sheet_compare.png\` — three key turntable views.

Original run: \`${ORIG_DIR#${REPO_DIR}/}\`
Patched run: \`${PATCH_DIR#${REPO_DIR}/}\`
EOF

echo "[PASS] Comparison written to ${COMPARE_DIR}"
ls -lh "${COMPARE_DIR}"/*.gif "${COMPARE_DIR}"/*.png 2>/dev/null || true
