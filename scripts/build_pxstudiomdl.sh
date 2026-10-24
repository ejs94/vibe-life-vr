#!/bin/bash
# Build pxstudiomdl (GoldSrc MDL v10 compiler) from the PrimeXT sources.
#
# PrimeXT normally builds its utilities through vcpkg, which pulls cgltf, miniz,
# rapidjson and fmt. pxstudiomdl only needs cgltf (gltf_source.cpp) and an
# include path for miniz; this script compiles those sources directly with the
# host compiler, so no vcpkg bootstrap is required.
#
# Output: out/pxstudiomdl/pxstudiomdl (gitignored)
#
# Usage: scripts/build_pxstudiomdl.sh [--clean]
#
# Environment overrides:
#   PRIMEXT_DIR  path to the PrimeXT checkout (default: ../xash3d-upstream/PrimeXT)
#   CGLTF_HEADER path to cgltf.h
#   OUT_DIR      output directory (default: out/pxstudiomdl)
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PRIMEXT_DIR="${PRIMEXT_DIR:-${REPO_DIR}/../xash3d-upstream/PrimeXT}"
CGLTF_HEADER="${CGLTF_HEADER:-${REPO_DIR}/../other-vr-ports/black-mesa-vr/third_party/l4d2vr/thirdparty/cgltf/cgltf.h}"
OUT_DIR="${OUT_DIR:-${REPO_DIR}/out/pxstudiomdl}"
MINIZ_DIR="${REPO_DIR}/3rdparty/miniz"

CXX="${CXX:-g++}"
CC="${CC:-gcc}"
JOBS="$(nproc 2>/dev/null || echo 4)"

if [ "${1:-}" = "--clean" ]; then
    rm -rf "${OUT_DIR}"
fi

if [ ! -d "${PRIMEXT_DIR}/utils/pxstudiomdl" ]; then
    echo "error: PrimeXT not found at ${PRIMEXT_DIR}" >&2
    exit 1
fi
if [ ! -f "${CGLTF_HEADER}" ]; then
    echo "error: cgltf.h not found at ${CGLTF_HEADER}" >&2
    exit 1
fi

OBJ_DIR="${OUT_DIR}/obj"
GEN_DIR="${OUT_DIR}/gen"
INCLUDE_CGLTF_DIR="$(dirname "${CGLTF_HEADER}")"
mkdir -p "${OBJ_DIR}" "${OUT_DIR}" "${GEN_DIR}"

# PrimeXT's build_info.h needs a generated header (normally written by CMake).
BUILD_COMMIT="$(git -C "${PRIMEXT_DIR}" describe --always --dirty --abbrev=7 2>/dev/null || echo notset)"
BUILD_BRANCH="$(git -C "${PRIMEXT_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo notset)"
cat > "${GEN_DIR}/build_info_gen.h" <<EOF
#pragma once
#define XASH_BUILD_COMMIT "${BUILD_COMMIT}"
#define XASH_BUILD_BRANCH "${BUILD_BRANCH}"
EOF

# The GoldSrc target is 32-bit-era code but compiles cleanly as LP64.
COMMON_DEFS=(
    -DIGNORE_SEARCH_IN_WADS=1
    -D_LINUX=1 -DLINUX=1
    -Dstricmp=strcasecmp -Dstrnicmp=strncasecmp
    -D_snprintf=snprintf -D_vsnprintf=vsnprintf
)
BASE_CXXFLAGS=(
    -std=c++17 -O2 -w
    -fno-exceptions -fno-rtti -fvisibility=hidden
    "${COMMON_DEFS[@]}"
)

# pxstudiomdl: game_shared/mathlib.h must resolve first (see upstream CMakeLists).
MDL_FLAGS=(
    "${BASE_CXXFLAGS[@]}"
    -I"${GEN_DIR}"
    -I"${PRIMEXT_DIR}/utils/pxstudiomdl"
    -I"${PRIMEXT_DIR}/game_shared"
    -I"${PRIMEXT_DIR}/engine"
    -I"${PRIMEXT_DIR}/server"
    -I"${PRIMEXT_DIR}/public"
    -I"${PRIMEXT_DIR}/common"
    -I"${PRIMEXT_DIR}/utils/common"
    -I"${PRIMEXT_DIR}/utils/common/imagelib"
    -I"${PRIMEXT_DIR}/external/squish"
    -I"${INCLUDE_CGLTF_DIR}"
    -I"${MINIZ_DIR}"
)

# imagelib must NOT see game_shared/mathlib.h: it uses the compiler mathlib
# from utils/common (the upstream CMakeLists compiles it with PXBSP_COMPILING).
IMG_FLAGS=(
    "${BASE_CXXFLAGS[@]}"
    -DPXBSP_COMPILING=1
    -I"${GEN_DIR}"
    -I"${PRIMEXT_DIR}/utils/common/imagelib"
    -I"${PRIMEXT_DIR}/utils/common"
    -I"${PRIMEXT_DIR}/public"
    -I"${PRIMEXT_DIR}/common"
    -I"${PRIMEXT_DIR}/external/squish"
    -I"${MINIZ_DIR}"
)

SQ_FLAGS=(
    "${BASE_CXXFLAGS[@]}"
    -D_LIB=1 -msse2 -DSQUISH_USE_SSE=2
    -I"${PRIMEXT_DIR}/external/squish"
)
CFLAGS=( -O2 -w "${COMMON_DEFS[@]}" -I"${MINIZ_DIR}" )

# Source groups mirror PrimeXT's CMake targets.
MAIN_SRCS=(
    "${PRIMEXT_DIR}/game_shared/mathlib.cpp"
    "${PRIMEXT_DIR}/game_shared/matrix.cpp"
    "${PRIMEXT_DIR}/utils/common/cmdlib.cpp"
    "${PRIMEXT_DIR}/utils/common/conprint.cpp"
    "${PRIMEXT_DIR}/utils/common/crashhandler.cpp"
    "${PRIMEXT_DIR}/utils/common/file_system.cpp"
    "${PRIMEXT_DIR}/utils/common/scriplib.cpp"
    "${PRIMEXT_DIR}/utils/common/stringlib.cpp"
    "${PRIMEXT_DIR}/utils/common/virtualfs.cpp"
    "${PRIMEXT_DIR}/utils/common/zone.cpp"
    "${PRIMEXT_DIR}/public/crclib.cpp"
    "${PRIMEXT_DIR}/utils/pxstudiomdl/gltf_source.cpp"
    "${PRIMEXT_DIR}/utils/pxstudiomdl/image_utils.cpp"
    "${PRIMEXT_DIR}/utils/pxstudiomdl/model_source.cpp"
    "${PRIMEXT_DIR}/utils/pxstudiomdl/optimize.cpp"
    "${PRIMEXT_DIR}/utils/pxstudiomdl/simpilfy.cpp"
    "${PRIMEXT_DIR}/utils/pxstudiomdl/skin.cpp"
    "${PRIMEXT_DIR}/utils/pxstudiomdl/smd_source.cpp"
    "${PRIMEXT_DIR}/utils/pxstudiomdl/studiomdl.cpp"
    "${PRIMEXT_DIR}/utils/pxstudiomdl/write.cpp"
)
IMAGELIB_SRCS=(
    "${PRIMEXT_DIR}/utils/common/imagelib/imagelib.cpp"
    "${PRIMEXT_DIR}/utils/common/imagelib/ddstex.cpp"
    "${PRIMEXT_DIR}/utils/common/imagelib/gamma.cpp"
    "${PRIMEXT_DIR}/utils/common/imagelib/quantizer.cpp"
)
SQUISH_SRCS=(
    "${PRIMEXT_DIR}/external/squish/alpha.cpp"
    "${PRIMEXT_DIR}/external/squish/clusterfit.cpp"
    "${PRIMEXT_DIR}/external/squish/colourblock.cpp"
    "${PRIMEXT_DIR}/external/squish/colourfit.cpp"
    "${PRIMEXT_DIR}/external/squish/colourset.cpp"
    "${PRIMEXT_DIR}/external/squish/maths.cpp"
    "${PRIMEXT_DIR}/external/squish/rangefit.cpp"
    "${PRIMEXT_DIR}/external/squish/singlecolourfit.cpp"
    "${PRIMEXT_DIR}/external/squish/squish.cpp"
)

obj_name() {
    # Unique, stable object name per source (path flattened + hash).
    local src="$1"
    local tag="${2:-x}"
    local base
    base="$(basename "${src}" .cpp)"
    local hash
    hash="$(printf '%s' "${src}" | cksum | cut -d' ' -f1)"
    echo "${OBJ_DIR}/${tag}_${base}_${hash}.o"
}

# compile_group <tag> <flag-array-name> <src>...
compile_group() {
    local tag="$1" flags_name="$2" ; shift 2
    local -n flags="${flags_name}"
    local objs=()
    local src obj
    for src in "$@"; do
        obj="$(obj_name "${src}" "${tag}")"
        objs+=("${obj}")
        echo "  CXX ${tag} $(basename "${src}")"
        "${CXX}" "${flags[@]}" -c "${src}" -o "${obj}" &
        while [ "$(jobs -rp | wc -l)" -ge "${JOBS}" ]; do wait -n || exit 1; done
    done
    wait
    for obj in "${objs[@]}"; do
        [ -f "${obj}" ] || { echo "error: missing object ${obj}" >&2; exit 1; }
    done
    printf '%s\n' "${objs[@]}" >> "${OBJ_DIR}/objects.list"
}

echo "PrimeXT:  ${PRIMEXT_DIR}"
echo "cgltf:    ${CGLTF_HEADER}"
echo "output:   ${OUT_DIR}/pxstudiomdl"

: > "${OBJ_DIR}/objects.list"
compile_group main MDL_FLAGS "${MAIN_SRCS[@]}"
compile_group img IMG_FLAGS "${IMAGELIB_SRCS[@]}"
compile_group sq SQ_FLAGS "${SQUISH_SRCS[@]}"

# miniz is only #included by imagelib; link the implementation so the symbol
# resolution is complete on every compiler.
if [ -f "${MINIZ_DIR}/miniz.c" ]; then
    echo "  CC miniz.c"
    "${CC}" "${CFLAGS[@]}" -c "${MINIZ_DIR}/miniz.c" -o "${OBJ_DIR}/miniz.o"
    echo "${OBJ_DIR}/miniz.o" >> "${OBJ_DIR}/objects.list"
fi

echo "  LD pxstudiomdl"
mapfile -t OBJECTS < "${OBJ_DIR}/objects.list"
"${CXX}" -o "${OUT_DIR}/pxstudiomdl" "${OBJECTS[@]}" -ldl

echo "built: ${OUT_DIR}/pxstudiomdl"
"${OUT_DIR}/pxstudiomdl" 2>&1 | head -3 || true
