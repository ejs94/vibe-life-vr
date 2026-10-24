#!/bin/bash
# ==============================================================================
# Xash3D VR - Standalone Two-Hand Model Static Asset Gate
# ==============================================================================
# Offline integrity + orientation check for models/v_hand.mdl. Runs the
# decompiler and validates the two-bodygroup layout, the Valve bone naming
# convention and the rendered hand orientation (fingers forward, palms inward,
# thumbs up). No OpenXR runtime required.
# ==============================================================================
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODEL="${1:-${REPO_DIR}/assets/valve_vr/models/v_hand.mdl}"

exec python3 "${SCRIPT_DIR}/check_hand_asset.py" --model "${MODEL}"
