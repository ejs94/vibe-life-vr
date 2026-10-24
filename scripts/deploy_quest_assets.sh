#!/bin/bash
# ==============================================================================
# Xash3D VR - Deploy VR overlay assets to a connected Meta Quest
# ==============================================================================
# The standalone APK bundles the VR overlay under the `valve_vr/` mod inside the
# APK, but the engine launches with the base `valve` gamedir. It does not mount
# `valve_vr` as a game directory (gameinfo lookup fails), so
# `models/v_hand.mdl` must exist inside the active gamedir for the standalone
# hands to load.
#
# This script pushes the standalone hand model and the declarative weapon
# profiles into `<basedir>/<gamedir>/models/` on the device, mirroring what
# scripts/setup_out_gamedir.sh does for the desktop build.
#
# Usage: scripts/deploy_quest_assets.sh [gamedir] [basedir]
#   gamedir  default: valve
#   basedir  default: /sdcard/xash
# ==============================================================================
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

GAMEDIR="${1:-valve}"
BASEDIR="${2:-/sdcard/xash}"

log_info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_ok()   { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_err()  { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; }

if ! command -v adb >/dev/null 2>&1; then
    log_err "adb not found in PATH."
    exit 1
fi

if [ "$(adb devices | awk 'NR>1 && $2=="device"' | wc -l)" -eq 0 ]; then
    log_err "No authorized Quest device detected via ADB."
    exit 1
fi

HAND_MDL="${REPO_DIR}/assets/valve_vr/models/v_hand.mdl"
PROFILES="${REPO_DIR}/assets/valve_vr/models/vr_weapons.json"

if [ ! -f "$HAND_MDL" ]; then
    log_err "Hand model missing: assets/valve_vr/models/v_hand.mdl"
    exit 1
fi

REMOTE_DIR="${BASEDIR}/${GAMEDIR}/models"
log_info "Deploying VR assets to ${REMOTE_DIR} ..."
adb shell "mkdir -p '${REMOTE_DIR}'"
adb push "$HAND_MDL" "${REMOTE_DIR}/v_hand.mdl" >/dev/null
log_ok "Pushed v_hand.mdl"

if [ -f "$PROFILES" ]; then
    adb push "$PROFILES" "${REMOTE_DIR}/vr_weapons.json" >/dev/null
    log_ok "Pushed vr_weapons.json"
fi

# Verify the deployed model matches the source byte for byte.
LOCAL_SHA="$(sha256sum "$HAND_MDL" | awk '{print $1}')"
REMOTE_SHA="$(adb shell "sha256sum '${REMOTE_DIR}/v_hand.mdl'" | awk '{print $1}')"
if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
    log_ok "Deployed v_hand.mdl matches the repository asset (sha256 ${LOCAL_SHA:0:12}...)"
else
    log_err "Deployed v_hand.mdl does not match the repository asset."
    exit 1
fi
