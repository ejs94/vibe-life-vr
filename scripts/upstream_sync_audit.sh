#!/usr/bin/env bash
# ==============================================================================
# Upstream Synchronization & Evaluation Tool for Xash3D FWGS VR
# 
# Purpose:
#   Tracks, filters, inspects, and evaluates upstream commits from
#   https://github.com/FWGS/xash3d-fwgs.git without performing blind git merges
#   that could break OpenXR 6DoF, VR rendering (ref_gl_vr), or Meta Quest 3 builds.
#
# Usage:
#   ./scripts/upstream_sync_audit.sh status            # View sync status & recent upstream commits
#   ./scripts/upstream_sync_audit.sh fetch             # Fetch latest upstream commits
#   ./scripts/upstream_sync_audit.sh filter [days]     # Categorize commits within maturation window (default: 60 days)
#   ./scripts/upstream_sync_audit.sh inspect <hash>    # Inspect a specific upstream commit
#   ./scripts/upstream_sync_audit.sh test-pick <hash>  # Dry-run cherry-pick, build, and run Monado VR test suite
# ==============================================================================

set -euo pipefail

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

UPSTREAM_REMOTE="upstream"
UPSTREAM_URL="https://github.com/FWGS/xash3d-fwgs.git"

# Text styling
BOLD="\033[1m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
CYAN="\033[1;36m"
RED="\033[1;31m"
MAGENTA="\033[1;35m"
RESET="\033[0m"

ensure_upstream_remote() {
    if ! git -C "$REPO_DIR" remote | grep -q "^${UPSTREAM_REMOTE}$"; then
        echo -e "${YELLOW}[INFO] Adding upstream remote: ${UPSTREAM_URL}${RESET}"
        git -C "$REPO_DIR" remote add "$UPSTREAM_REMOTE" "$UPSTREAM_URL"
    else
        local current_url
        current_url=$(git -C "$REPO_DIR" remote get-url "$UPSTREAM_REMOTE")
        if [ "$current_url" != "$UPSTREAM_URL" ]; then
            echo -e "${YELLOW}[INFO] Updating upstream remote URL to: ${UPSTREAM_URL}${RESET}"
            git -C "$REPO_DIR" remote set-url "$UPSTREAM_REMOTE" "$UPSTREAM_URL"
        fi
    fi
}

cmd_fetch() {
    ensure_upstream_remote
    echo -e "${CYAN}[INFO] Fetching upstream updates from ${UPSTREAM_URL}...${RESET}"
    git -C "$REPO_DIR" fetch "$UPSTREAM_REMOTE" master --tags
    echo -e "${GREEN}[OK] Upstream fetch complete.${RESET}"
}

cmd_status() {
    ensure_upstream_remote
    local current_branch
    current_branch=$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD)
    local merge_base
    merge_base=$(git -C "$REPO_DIR" merge-base HEAD "${UPSTREAM_REMOTE}/master" 2>/dev/null || echo "unknown")

    echo -e "\n${BOLD}${MAGENTA}==========================================================${RESET}"
    echo -e "${BOLD}${MAGENTA}  XASH3D FWGS VR <-> UPSTREAM SYNC STATUS${RESET}"
    echo -e "${BOLD}${MAGENTA}==========================================================${RESET}"
    echo -e "Current Branch:     ${CYAN}${current_branch}${RESET}"
    echo -e "Upstream Remote:    ${CYAN}${UPSTREAM_REMOTE}/master${RESET} (${UPSTREAM_URL})"
    echo -e "Merge Base:         ${YELLOW}${merge_base}${RESET}"

    if [ "$merge_base" != "unknown" ]; then
        local ahead behind
        ahead=$(git -C "$REPO_DIR" rev-list --count "${merge_base}..HEAD")
        behind=$(git -C "$REPO_DIR" rev-list --count "${merge_base}..${UPSTREAM_REMOTE}/master")
        echo -e "Commits Ahead (VR): ${GREEN}${ahead}${RESET}"
        echo -e "Commits Behind:     ${YELLOW}${behind}${RESET}"

        if [ "$behind" -gt 0 ]; then
            echo -e "\n${BOLD}Recent Upstream Commits not in VR Fork:${RESET}"
            git -C "$REPO_DIR" log --oneline --color=always -n 15 "${merge_base}..${UPSTREAM_REMOTE}/master"
        else
            echo -e "\n${GREEN}[OK] Fork is fully up-to-date with upstream/master (0 commits behind).${RESET}"
        fi
    fi
    echo -e "${BOLD}${MAGENTA}==========================================================${RESET}\n"
}

cmd_filter() {
    ensure_upstream_remote
    local min_age_days="${1:-60}"
    local merge_base
    merge_base=$(git -C "$REPO_DIR" merge-base HEAD "${UPSTREAM_REMOTE}/master")

    echo -e "\n${BOLD}${CYAN}==========================================================${RESET}"
    echo -e "${BOLD}${CYAN}  UPSTREAM COMMITS EVALUATION (Maturation >= ${min_age_days} days)${RESET}"
    echo -e "${BOLD}${CYAN}==========================================================${RESET}"

    local cutoff_date
    cutoff_date=$(date -d "${min_age_days} days ago" +%s)

    local unmerged_commits
    unmerged_commits=$(git -C "$REPO_DIR" log --format="%H|%at|%ad|%an|%s" --date=short "${merge_base}..${UPSTREAM_REMOTE}/master")

    if [ -z "$unmerged_commits" ]; then
        echo -e "${GREEN}No pending upstream commits to evaluate.${RESET}\n"
        return 0
    fi

    local count_eval=0
    local count_cooling=0

    while IFS="|" read -r hash timestamp date author summary; do
        if [ "$timestamp" -gt "$cutoff_date" ]; then
            # Still in cooling / stabilization window
            ((count_cooling++)) || true
            continue
        fi

        ((count_eval++)) || true

        # Categorize by commit subject / affected subsystems
        local category="[NEUTRAL]"
        local color="$YELLOW"

        if [[ "$summary" =~ (touch|TOUCH|stick|analog|cutout|safearea) ]]; then
            category="[SKIP: Touch/2D UI]"
            color="$RED"
        elif [[ "$summary" =~ (network|net_|socket|protocol|delta|sv_pmove|filesystem|fs_|sound|s_main|wav) ]]; then
            category="[RECOMMENDED: Core/Audio/Net]"
            color="$GREEN"
        elif [[ "$summary" =~ (ref_|gl_|studio|renderer|model) ]]; then
            category="[CAUTION: Renderer/Studio]"
            color="$YELLOW"
        fi

        echo -e "${color}${category}${RESET} ${BOLD}${hash:0:8}${RESET} (${date}) ${author}: ${summary}"
    done <<< "$unmerged_commits"

    echo -e "\n${CYAN}Summary:${RESET}"
    echo -e "  - Matured Commits (Ready for Review): ${count_eval}"
    echo -e "  - Commits in Cooling Window (< ${min_age_days} days): ${count_cooling}"
    echo -e "${BOLD}${CYAN}==========================================================${RESET}\n"
}

cmd_inspect() {
    local hash="${1:-}"
    if [ -z "$hash" ]; then
        echo -e "${RED}[ERROR] Please provide a commit hash: $0 inspect <commit-hash>${RESET}"
        exit 1
    fi

    echo -e "\n${BOLD}${CYAN}=== Commit Information: ${hash} ===${RESET}"
    git -C "$REPO_DIR" show --stat --color=always "$hash"
}

cmd_test_pick() {
    local hash="${1:-}"
    if [ -z "$hash" ]; then
        echo -e "${RED}[ERROR] Please provide a commit hash: $0 test-pick <commit-hash>${RESET}"
        exit 1
    fi

    local temp_branch="upstream-dryrun-$(date +%s)"
    echo -e "\n${YELLOW}[INFO] Creating isolated testing branch: ${temp_branch}${RESET}"
    git -C "$REPO_DIR" checkout -b "$temp_branch"

    echo -e "${CYAN}[INFO] Attempting cherry-pick of commit ${hash}...${RESET}"
    if ! git -C "$REPO_DIR" cherry-pick "$hash"; then
        echo -e "${RED}[FAIL] Cherry-pick failed with conflicts. Aborting test.${RESET}"
        git -C "$REPO_DIR" cherry-pick --abort || true
        git -C "$REPO_DIR" checkout -
        git -C "$REPO_DIR" branch -D "$temp_branch"
        exit 1
    fi

    echo -e "${GREEN}[OK] Cherry-pick applied cleanly.${RESET}"
    echo -e "${CYAN}[INFO] Testing build compilation with ./waf build...${RESET}"
    if ! (cd "$REPO_DIR" && ./waf build && ./waf install --destdir=./out); then
        echo -e "${RED}[FAIL] Compilation failed after applying commit ${hash}.${RESET}"
        git -C "$REPO_DIR" checkout -
        git -C "$REPO_DIR" branch -D "$temp_branch"
        exit 1
    fi

    echo -e "${GREEN}[OK] Compilation passed! Running Monado VR regression test suite...${RESET}"
    if (cd "$REPO_DIR" && ./scripts/test_simulated_monado.sh); then
        echo -e "\n${GREEN}${BOLD}[SUCCESS] Commit ${hash} passed all 23 VR unit tests without regressions!${RESET}"
        echo -e "To permanently apply to your working branch:"
        echo -e "  git checkout feature/openxr-vr && git cherry-pick ${hash}\n"
    else
        echo -e "\n${RED}${BOLD}[FAIL] Commit ${hash} caused VR test regressions.${RESET}\n"
    fi

    echo -e "${CYAN}[INFO] Cleaning up test branch...${RESET}"
    git -C "$REPO_DIR" checkout -
    git -C "$REPO_DIR" branch -D "$temp_branch"
}

case "${1:-status}" in
    fetch)
        cmd_fetch
        ;;
    status)
        cmd_status
        ;;
    filter)
        cmd_filter "${2:-60}"
        ;;
    inspect)
        cmd_inspect "${2:-}"
        ;;
    test-pick)
        cmd_test_pick "${2:-}"
        ;;
    *)
        echo "Usage: $0 {fetch|status|filter [days]|inspect <hash>|test-pick <hash>}"
        exit 1
        ;;
esac
