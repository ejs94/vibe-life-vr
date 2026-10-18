#!/usr/bin/env bash
# ==============================================================================
# Xash3D VR — MCP & Codebase Intelligence Tooling Helper
# Bridges Repowise, Graphify, and Desloppify into the active VR port workflow.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MCP_TOOLS_ROOT="$(cd "${REPO_ROOT}/../mcp-tools" && pwd)"

REPOWISE_DIR="${MCP_TOOLS_ROOT}/repowise"
GRAPHIFY_DIR="${MCP_TOOLS_ROOT}/graphify"
DESLOPPIFY_DIR="${MCP_TOOLS_ROOT}/desloppify"
CLANGD_MCP_DIR="${MCP_TOOLS_ROOT}/clangd-mcp-server"
BLENDER_MCP_DIR="${MCP_TOOLS_ROOT}/blender-mcp"

UV_BIN="${HOME}/.local/bin/uv"
if ! command -v "${UV_BIN}" &>/dev/null; then
    UV_BIN="uv"
fi

# Ensure uv is available
if ! command -v "${UV_BIN}" &>/dev/null; then
    echo "[!] Error: 'uv' executable not found. Please install uv first."
    exit 1
fi

print_usage() {
    echo "Usage: ./scripts/mcp_tools.sh <command> [args...]"
    echo ""
    echo "Available commands:"
    echo "  status            Check status of MCP tools, virtualenvs, and data artifacts"
    echo "  graph             Extract AST knowledge graph with Graphify and generate graph.html"
    echo "  dead-code         Run Repowise live dead-code analysis across the codebase"
    echo "  health            Run Desloppify C/C++ code hygiene and technical debt scanner"
    echo "  init-repowise     Initialize Repowise index and database in .repowise/"
    echo "  repowise [args]   Run arbitrary Repowise CLI commands (e.g. repowise status --workspace)"
    echo "  serve             Start the Repowise web dashboard at http://localhost:3000"
    echo "  mcp-repowise      Start the Repowise stdio MCP server"
    echo "  mcp-graphify      Start the Graphify stdio MCP server"
    echo "  mcp-clangd        Start the Clangd C/C++ stdio MCP server"
    echo "  mcp-blender       Start the Blender Lab stdio MCP server"
    echo ""
}

cmd_status() {
    echo "=== Xash3D VR — MCP Tooling Environment Status ==="
    echo "Repository Root : ${REPO_ROOT}"
    echo "MCP Tools Root  : ${MCP_TOOLS_ROOT}"
    echo "UV Binary       : $("${UV_BIN}" --version)"
    echo ""

    echo "[*] Checking Tool Directories:"
    for tool_path in "${REPOWISE_DIR}" "${GRAPHIFY_DIR}" "${DESLOPPIFY_DIR}" "${CLANGD_MCP_DIR}" "${BLENDER_MCP_DIR}"; do
        if [ -d "${tool_path}" ]; then
            echo "  - $(basename "${tool_path}"): FOUND (${tool_path})"
        else
            echo "  - $(basename "${tool_path}"): MISSING"
        fi
    done
    echo ""

    echo "[*] Checking C/C++ Intelligence (Clangd & Compile Commands):"
    if [ -f "${REPO_ROOT}/compile_commands.json" ]; then
        echo "  - compile_commands.json: FOUND ($(du -h "${REPO_ROOT}/compile_commands.json" | cut -f1))"
    elif [ -f "${REPO_ROOT}/build/compile_commands.json" ]; then
        echo "  - compile_commands.json: FOUND in build/ (linking to root...)"
        ln -sf build/compile_commands.json "${REPO_ROOT}/compile_commands.json"
    else
        echo "  - compile_commands.json: NOT FOUND (build with waf or cmake first)"
    fi
    if command -v clangd &>/dev/null; then
        echo "  - clangd binary: $(command -v clangd) ($(clangd --version 2>&1 | head -n1))"
    else
        echo "  - clangd binary: NOT FOUND (install clangd for C/C++ LSP)"
    fi
    echo ""

    echo "[*] Checking MCP Configuration:"
    if [ -f "${REPO_ROOT}/.agents/mcp_config.json" ]; then
        echo "  - .agents/mcp_config.json: ACTIVE"
    else
        echo "  - .agents/mcp_config.json: NOT FOUND"
    fi

    echo "[*] Checking Knowledge Graph Artifacts:"
    if [ -f "${REPO_ROOT}/graphify-out/graph.json" ]; then
        echo "  - graph.json: FOUND ($(du -h "${REPO_ROOT}/graphify-out/graph.json" | cut -f1))"
    else
        echo "  - graph.json: NOT GENERATED (run './scripts/mcp_tools.sh graph')"
    fi
    if [ -f "${REPO_ROOT}/graphify-out/graph.html" ]; then
        echo "  - graph.html: FOUND ($(du -h "${REPO_ROOT}/graphify-out/graph.html" | cut -f1))"
    elif [ -f "${REPO_ROOT}/graph.html" ]; then
        echo "  - graph.html: FOUND ($(du -h "${REPO_ROOT}/graph.html" | cut -f1))"
    else
        echo "  - graph.html: NOT GENERATED (run './scripts/mcp_tools.sh graph')"
    fi
    echo ""

    echo "[*] Checking Repowise Store Artifacts:"
    if [ -f "${REPO_ROOT}/.repowise/wiki.db" ]; then
        echo "  - .repowise/wiki.db: FOUND ($(du -h "${REPO_ROOT}/.repowise/wiki.db" | cut -f1))"
    elif [ -d "${REPO_ROOT}/.repowise" ]; then
        echo "  - .repowise: DIRECTORY READY (run './scripts/mcp_tools.sh init-repowise' for full indexing)"
    else
        echo "  - .repowise: MISSING (run './scripts/mcp_tools.sh init-repowise')"
    fi
    echo ""
}

cmd_init_repowise() {
    echo "[*] Initializing Repowise index on ${REPO_ROOT}..."
    mkdir -p "${REPO_ROOT}/.repowise"
    "${UV_BIN}" run --python 3.12 --project "${REPOWISE_DIR}" repowise init "${REPO_ROOT}" --yes --no-claude-md "$@"
}

cmd_graph() {
    echo "[*] Extracting AST Knowledge Graph via Graphify (code-only mode)..."
    "${UV_BIN}" run --python 3.12 --project "${GRAPHIFY_DIR}" graphify extract "${REPO_ROOT}" --code-only --out "${REPO_ROOT}"
    echo "[*] Exporting interactive HTML graph visualization..."
    "${UV_BIN}" run --python 3.12 --project "${GRAPHIFY_DIR}" graphify export html --graph "${REPO_ROOT}/graphify-out/graph.json"
    echo "[+] Graph extracted successfully to ${REPO_ROOT}/graph.html"
}

cmd_dead_code() {
    echo "[*] Running Repowise dead-code analysis on ${REPO_ROOT}..."
    "${UV_BIN}" run --python 3.12 --project "${REPOWISE_DIR}" repowise dead-code "${REPO_ROOT}" "$@"
}

cmd_health() {
    echo "[*] Running Desloppify C/C++ static hygiene and code debt scan..."
    "${UV_BIN}" run --python 3.12 --project "${DESLOPPIFY_DIR}" desloppify \
        --lang cxx \
        --exclude "3rdparty" \
        --exclude "build" \
        --exclude "android" \
        scan \
        --path "${REPO_ROOT}" \
        --skip-slow \
        --profile ci "$@"
}

cmd_mcp_repowise() {
    mkdir -p "${REPO_ROOT}/.repowise"
    exec "${UV_BIN}" run --python 3.12 --project "${REPOWISE_DIR}" repowise mcp "${REPO_ROOT}" --transport stdio
}

cmd_mcp_graphify() {
    local graph_file="${REPO_ROOT}/graphify-out/graph.json"
    if [ ! -f "${graph_file}" ]; then
        echo "[!] graph.json not found. Generating initial graph first..."
        cmd_graph
    fi
    exec "${UV_BIN}" run --python 3.12 --project "${GRAPHIFY_DIR}" --extra mcp graphify-mcp --graph "${graph_file}" --transport stdio
}

cmd_mcp_clangd() {
    export PROJECT_ROOT="${REPO_ROOT}"
    export COMPILE_COMMANDS_DIR="${REPO_ROOT}/build"
    export CLANGD_PATH="$(command -v clangd || echo "/usr/bin/clangd")"
    export CLANGD_ARGS="--background-index"
    echo "[*] Launching Clangd MCP Server on stdio (PROJECT_ROOT=${PROJECT_ROOT})..." >&2
    exec node "${CLANGD_MCP_DIR}/dist/index.js"
}

cmd_mcp_blender() {
    echo "[*] Launching Blender Lab MCP Server on stdio..." >&2
    exec "${UV_BIN}" run --python 3.12 --project "${BLENDER_MCP_DIR}/mcp" blender-mcp "$@"
}

cmd_repowise() {
    "${UV_BIN}" run --python 3.12 --project "${REPOWISE_DIR}" repowise "$@"
}

# Main dispatcher
if [ $# -lt 1 ]; then
    print_usage
    exit 0
fi

case "$1" in
    status)
        cmd_status
        ;;
    graph)
        shift
        cmd_graph "$@"
        ;;
    dead-code)
        shift
        cmd_dead_code "$@"
        ;;
    health|scan)
        shift
        cmd_health "$@"
        ;;
    init-repowise)
        shift
        cmd_init_repowise "$@"
        ;;
    repowise)
        shift
        cmd_repowise "$@"
        ;;
    serve)
        shift
        cmd_repowise serve "$@"
        ;;
    mcp-repowise)
        cmd_mcp_repowise
        ;;
    mcp-graphify)
        cmd_mcp_graphify
        ;;
    mcp-clangd)
        cmd_mcp_clangd
        ;;
    mcp-blender)
        shift
        cmd_mcp_blender "$@"
        ;;
    *)
        echo "[!] Unknown command: $1"
        print_usage
        exit 1
        ;;
esac
