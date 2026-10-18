#!/usr/bin/env bash
# ==============================================================================
# Xash3D VR — Reference VR Model & Asset Pack Packager
# ==============================================================================
# Bundles the reference VR asset overlay (assets/valve_vr/) into:
#   1. A standalone installable directory (out/valve_vr/).
#   2. A distributable zip archive (out/xash3d-vr-models-valve.zip).
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ASSETS_DIR="${REPO_DIR}/assets/valve_vr"
OUT_DIR="${REPO_DIR}/out/valve_vr"
OUT_ZIP="${REPO_DIR}/out/xash3d-vr-models-valve.zip"

echo "=========================================================="
echo "  Xash3D VR: Packaging Reference VR Asset Overlay"
echo "=========================================================="

mkdir -p "${OUT_DIR}/models"

# 1. Copy gameinfo and configs
cp "${ASSETS_DIR}/gameinfo.txt" "${OUT_DIR}/"
cp "${ASSETS_DIR}/models/vr_weapons.json" "${OUT_DIR}/models/"

# 2. Copy any compiled .mdl models if present
if compgen -G "${ASSETS_DIR}/models/*.mdl" > /dev/null; then
    echo "[INFO] Copying compiled VR viewmodels..."
    cp "${ASSETS_DIR}/models/"*.mdl "${OUT_DIR}/models/"
else
    echo "[INFO] No precompiled binary .mdl in assets/valve_vr/models/. Packaging manifest & templates."
fi

# 3. Create zip distribution archive
mkdir -p "${REPO_DIR}/out"
python3 -c "
import shutil
shutil.make_archive('${REPO_DIR}/out/xash3d-vr-models-valve', 'zip', '${REPO_DIR}/out', 'valve_vr')
"

echo "[PASS] Reference VR Pack created at: ${OUT_DIR}"
echo "[PASS] Distribution zip created at: ${OUT_ZIP}"
echo "=========================================================="
