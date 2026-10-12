#!/bin/bash
# ==============================================================================
# Xash3D VR - One-Click Launcher for Meta Quest via WiVRn (Linux PCVR)
# ==============================================================================
# Supports automated WiVRn server management and ADB auto-launch of the WiVRn
# client on connected Meta Quest headsets (USB and Wi-Fi).
# ==============================================================================

set -e

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${REAL_SCRIPT}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ ! -d "${REPO_DIR}/out" ]; then
    echo "Error: '${REPO_DIR}/out' does not exist. Please build PCVR first." >&2
    exit 1
fi

# Ensure ADB path is available if in default Android SDK location
if ! command -v adb >/dev/null 2>&1; then
    if [ -d "$HOME/Android/Sdk/platform-tools" ]; then
        export PATH="$HOME/Android/Sdk/platform-tools:$PATH"
    fi
fi

# 1. Start WiVRn server on host PC if not already active
if ! pgrep -fa "wivrn-server" >/dev/null 2>&1; then
    echo ">> [WiVRn] Starting WiVRn server service..."
    if command -v systemctl >/dev/null 2>&1 && systemctl --user list-unit-files | grep -q "wivrn.service"; then
        systemctl --user start wivrn || true
    fi
    if ! pgrep -fa "wivrn-server" >/dev/null 2>&1; then
        if command -v wivrn-server >/dev/null 2>&1; then
            wivrn-server &
            sleep 1
        fi
    fi
fi

# 2. Check if Meta Quest is connected via ADB and auto-start client
if command -v adb >/dev/null 2>&1; then
    DEV_COUNT=$(adb devices 2>/dev/null | awk 'NR>1 && $2=="device"' | wc -l || true)
    if [ "$DEV_COUNT" -gt 0 ]; then
        echo ">> [ADB] Quest headset detected ($DEV_COUNT authorized device(s))."
        
        # Display battery & thermals
        if [ -f "${SCRIPT_DIR}/quest_battery.sh" ]; then
            "${SCRIPT_DIR}/quest_battery.sh" display || true
        fi
        
        # Configure USB reverse port forwarding for WiVRn control & stream
        echo ">> [ADB] Configuring WiVRn port forwarding (reverse tcp:9757)..."
        adb reverse tcp:9757 tcp:9757 2>/dev/null || true
        
        # Check if WiVRn is already running on the headset
        if ! adb shell pidof org.meumeu.wivrn >/dev/null 2>&1; then
            echo ">> [ADB] Launching WiVRn client (org.meumeu.wivrn) on headset..."
            # Try intent with localhost (works seamlessly with adb reverse)
            adb shell am start -a android.intent.action.VIEW -d "wivrn://localhost" org.meumeu.wivrn >/dev/null 2>&1 || \
            adb shell am start -n org.meumeu.wivrn/.MainActivity >/dev/null 2>&1 || true
            sleep 2
            echo ">> [ADB] WiVRn client signaled."
        else
            echo ">> [ADB] WiVRn client is already active on headset."
        fi
    else
        echo ">> [ADB] No headset detected in adb devices (assuming wireless streaming or headset already running)."
    fi
fi

cd "${REPO_DIR}/out"

# 3. Point Khronos OpenXR loader to WiVRn runtime
if [ -f "/usr/share/openxr/1/openxr_wivrn.json" ]; then
    export XR_RUNTIME_JSON="/usr/share/openxr/1/openxr_wivrn.json"
    echo ">> [OpenXR] Using WiVRn runtime: ${XR_RUNTIME_JSON}"
elif [ -f "$HOME/.config/openxr/1/active_runtime.json" ]; then
    export XR_RUNTIME_JSON="$HOME/.config/openxr/1/active_runtime.json"
    echo ">> [OpenXR] Using active user runtime: ${XR_RUNTIME_JSON}"
fi

export LD_LIBRARY_PATH=".:${LD_LIBRARY_PATH}"
export SDL_VIDEODRIVER=x11

PRIME_CMD=""
if command -v prime-run >/dev/null 2>&1; then
    PRIME_CMD="prime-run"
    echo ">> [GPU] Using NVIDIA dGPU via prime-run"
fi

TARGET_MAP="${1:-crossfire}"

GAME_PID=""
cleanup_game() {
    if [ -n "$GAME_PID" ] && kill -0 "$GAME_PID" 2>/dev/null; then
        echo ">> [Process] Terminating Xash3D VR engine (PID $GAME_PID)..."
        kill -TERM "$GAME_PID" 2>/dev/null || true
        sleep 0.5
        if kill -0 "$GAME_PID" 2>/dev/null; then
            kill -KILL "$GAME_PID" 2>/dev/null || true
        fi
    fi
}
trap cleanup_game EXIT INT TERM

echo "=========================================================="
echo "  Starting Xash3D VR -> Streaming to Meta Quest via WiVRn "
if [ -n "$TARGET_MAP" ] && [ "$TARGET_MAP" != "menu" ]; then
    echo "  Map: ${TARGET_MAP} | Renderer: gl_vr (libref_gl_vr.so)  "
    echo "=========================================================="
    $PRIME_CMD ./xash3d -dev 1 -condebug -ref gl_vr +cl_confirmquit 0 +map "${TARGET_MAP}" &
    GAME_PID=$!
    wait "$GAME_PID" || true
else
    echo "  Starting at Main Menu | Renderer: gl_vr (libref_gl_vr.so)  "
    echo "=========================================================="
    $PRIME_CMD ./xash3d -dev 1 -condebug -ref gl_vr +cl_confirmquit 0 &
    GAME_PID=$!
    wait "$GAME_PID" || true
fi
