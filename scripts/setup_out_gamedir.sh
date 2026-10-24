#!/bin/bash
# Build a writable, non-destructive game directory at out/valve.
#
# Historically out/valve was a symlink to the real Steam Half-Life "valve"
# directory, so every test script that copied v_hand.mdl / *.cfg into it
# silently clobbered the user's game installation. This script replaces that
# symlink with a real directory:
#
#   * read-only content (maps, sound, sprites, ...) is symlinked from Steam;
#   * models/ is a real directory containing one symlink per vanilla model,
#     so an override (v_hand.mdl, ...) is written HERE and never in Steam;
#   * engine-generated files (config.cfg, saves/, logs/) are created locally.
#
# Idempotent: safe to re-run after the engine or a test wrote overrides.
#
# Usage: scripts/setup_out_gamedir.sh [path-to-valve-dir]
#
# The default Steam path can be overridden with $STEAM_HL_VALVE.
set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

STEAM_VALVE="${1:-${STEAM_HL_VALVE:-${HOME}/.local/share/Steam/steamapps/common/Half-Life/valve}}"
OUT_VALVE="${REPO_DIR}/out/valve"

if [ ! -d "${STEAM_VALVE}" ]; then
    echo "error: Steam valve dir not found: ${STEAM_VALVE}" >&2
    echo "       pass the path as arg 1 or set STEAM_HL_VALVE" >&2
    exit 1
fi

mkdir -p "${REPO_DIR}/out"

# 1. If out/valve is still the legacy symlink, replace it with a real dir.
if [ -L "${OUT_VALVE}" ]; then
    echo "removing legacy symlink: ${OUT_VALVE} -> $(readlink "${OUT_VALVE}")"
    rm -f "${OUT_VALVE}"
fi
mkdir -p "${OUT_VALVE}"

# 2. Names that must stay local (engine runtime state / our overrides).
#    Symlinking these would send writes back into the Steam installation.
is_local_name() {
    case "$1" in
        models|saves|save|downloads|custom|logs|config.cfg|config.cfg.bak|\
        opengl.cfg|opengl.cfg.bak|video.cfg|video.cfg.bak|*.log|.xash_id|\
        voice_ban.dt|*.dt) return 0 ;;
        *) return 1 ;;
    esac
}

# 3. Link every other top-level entry from the Steam install.
shopt -s nullglob
for entry in "${STEAM_VALVE}"/* "${STEAM_VALVE}"/.*; do
    base="$(basename "${entry}")"
    [ "${base}" = "." ] || [ "${base}" = ".." ] && continue
    if is_local_name "${base}"; then
        continue
    fi
    ln -sfn "${entry}" "${OUT_VALVE}/${base}"
done

# 4. models/ : real dir, one symlink per vanilla model (keeps overrides local).
mkdir -p "${OUT_VALVE}/models"
if [ -d "${STEAM_VALVE}/models" ]; then
    for mdl in "${STEAM_VALVE}/models"/*; do
        base="$(basename "${mdl}")"
        [ -e "${OUT_VALVE}/models/${base}" ] && [ ! -L "${OUT_VALVE}/models/${base}" ] && continue
        ln -sfn "${mdl}" "${OUT_VALVE}/models/${base}"
    done
fi

# 5. Install the repo's declarative weapon profiles locally (the engine looks
#    for models/vr_weapons.json inside the game dir; never write it to Steam).
PROFILES="${REPO_DIR}/assets/valve_vr/models/vr_weapons.json"
if [ -f "${PROFILES}" ]; then
    cp -f "${PROFILES}" "${OUT_VALVE}/models/vr_weapons.json"
fi

echo "out/valve ready (real dir, read-only symlinks to ${STEAM_VALVE})"
echo "  top-level symlinks: $(find "${OUT_VALVE}" -maxdepth 1 -type l | wc -l)"
echo "  model symlinks:     $(find "${OUT_VALVE}/models" -maxdepth 1 -type l | wc -l)"
echo "  local overrides:    $(find "${OUT_VALVE}/models" -maxdepth 1 -type f | wc -l)"
