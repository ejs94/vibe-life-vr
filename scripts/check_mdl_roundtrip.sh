#!/bin/bash
# Verify that a GoldSrc viewmodel survives mdldec -> pxstudiomdl unchanged.
#
# This is the pilot gate for asset work: if the compiler cannot reproduce the
# original bones, sequences, events, bodygroups and attachments, stop before
# editing any mesh. The script works on copies under out/viewmodel_work and
# never touches the source asset.
#
# Usage:
#   scripts/check_mdl_roundtrip.sh assets/valve_vr/models/v_crossbow.mdl
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODEL="${1:-${REPO_DIR}/assets/valve_vr/models/v_crossbow.mdl}"
MODEL_NAME="$(basename "${MODEL}" .mdl)"
WORK_DIR="${REPO_DIR}/out/viewmodel_work/roundtrip/${MODEL_NAME}"
DECOMPILED="${WORK_DIR}/decompiled"
RECOMPILED="${WORK_DIR}/recompiled"
STUDIOMDL="${REPO_DIR}/out/pxstudiomdl/pxstudiomdl"

if [ ! -f "${MODEL}" ]; then
    echo "[FAIL] model not found: ${MODEL}" >&2
    exit 1
fi
if [ ! -x "${STUDIOMDL}" ]; then
    echo "[FAIL] pxstudiomdl not found: ${STUDIOMDL}" >&2
    echo "       run scripts/build_pxstudiomdl.sh first" >&2
    exit 1
fi

rm -rf "${DECOMPILED}" "${RECOMPILED}"
mkdir -p "${DECOMPILED}" "${RECOMPILED}"

echo "[1/4] Decompiling ${MODEL}"
"${SCRIPT_DIR}/mdldec.sh" "${MODEL}" "${DECOMPILED}" >/dev/null

QC="${DECOMPILED}/${MODEL_NAME}.qc"
if [ ! -f "${QC}" ]; then
    echo "[FAIL] decompiler did not produce ${QC}" >&2
    exit 1
fi

echo "[2/4] Recompiling with pxstudiomdl"
(
    cd "${DECOMPILED}"
    "${STUDIOMDL}" "${MODEL_NAME}.qc" >"${WORK_DIR}/compile.log" 2>&1
)

BUILT="${DECOMPILED}/${MODEL_NAME}.mdl"
if [ ! -f "${BUILT}" ]; then
    echo "[FAIL] compiler did not produce ${BUILT}" >&2
    tail -40 "${WORK_DIR}/compile.log" >&2 || true
    exit 1
fi

echo "[3/4] Decompiling the rebuilt model"
"${SCRIPT_DIR}/mdldec.sh" "${BUILT}" "${RECOMPILED}" >/dev/null

REBUILT_QC="${RECOMPILED}/${MODEL_NAME}.qc"
if [ ! -f "${REBUILT_QC}" ]; then
    echo "[FAIL] decompiler did not produce ${REBUILT_QC}" >&2
    exit 1
fi

echo "[4/4] Comparing decompiled QC structure"
# The internal model name is metadata and the compiler may emit -0.0; neither
# affects bones, sequences, events, bodygroups or attachments.
normalize() {
    sed -E \
        -e 's/^"v_[^"]+\.mdl"$/"<internal-name>"/' \
        -e 's/^"v_.*\(pxstudiomdl.*\)"$/"<internal-name>"/' \
        -e 's/studio "_1"/studio "<blank>"/' \
        -e 's/studio "MDLDEC_Model[0-9]+"/studio "<blank>"/' \
        -e 's/^-0\.000000/0.000000/g' \
        -e 's/-0\.000000/0.000000/g' \
        "$1"
}

if diff -u <(normalize "${QC}") <(normalize "${REBUILT_QC}") >"${WORK_DIR}/qc.diff"; then
    echo "[PASS] ${MODEL_NAME}: round-trip preserved bones, sequences, events, bodygroups and attachments"
    echo "       work dir: ${WORK_DIR}"
    exit 0
fi

echo "[FAIL] ${MODEL_NAME}: round-trip changed the QC structure" >&2
cat "${WORK_DIR}/qc.diff" >&2
exit 1
