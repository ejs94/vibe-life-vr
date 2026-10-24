#!/bin/bash
# Wrapper around utils/mdldec/mdldec.
#
# mdldec resolves activities.txt through $MDLDEC_ACT_PATH, which must be the
# directory containing the file (not the file itself).
#
# Usage: scripts/mdldec.sh <model.mdl> [target-directory]
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

export MDLDEC_ACT_PATH="${REPO_DIR}/utils/mdldec/res"
exec "${REPO_DIR}/utils/mdldec/mdldec" "$@"
