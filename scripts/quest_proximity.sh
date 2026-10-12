#!/usr/bin/env bash
# ==============================================================================
# Xash3D VR - Meta Quest Proximity Sensor & Power Management Tool
# ==============================================================================
# Controls headset proximity sensor simulation, display sleep, and stay-awake:
#   - disable: Bypasses proximity sensor, forces mounted state, disables sleep.
#   - enable:  Restores default proximity automation and normal sleep timers.
#   - status:  Displays current virtual proximity state, mount state, and locks.
# ==============================================================================

set -euo pipefail

ACTION="${1:-disable}"

if ! command -v adb >/dev/null 2>&1; then
    if [ -d "$HOME/Android/Sdk/platform-tools" ]; then
        export PATH="$HOME/Android/Sdk/platform-tools:$PATH"
    else
        echo "Error: adb not found in PATH." >&2
        exit 1
    fi
fi

resolve_device() {
    local devices
    devices=$(adb devices 2>/dev/null | awk 'NR>1 && $2=="device" {print $1}')
    local count
    count=$(echo "$devices" | grep -v '^$' | wc -l || true)

    if [ "$count" -eq 0 ]; then
        echo -e "\033[1;31m[ERROR]\033[0m No authorized Meta Quest device found in 'adb devices'." >&2
        exit 1
    fi

    TARGET_SERIAL=$(echo "$devices" | head -n1)
    ADB_CMD="adb -s $TARGET_SERIAL"
}

show_status() {
    resolve_device
    local dump
    dump=$($ADB_CMD shell dumpsys vrpowermanager 2>/dev/null | head -n 12 || true)

    local prox_state
    prox_state=$(echo "$dump" | awk -F': ' '/Virtual proximity state:/ {print $2}' | tr -d '\r' | head -n1)
    local hmd_state
    hmd_state=$(echo "$dump" | awk -F': ' '/^State:/ {print $2}' | tr -d '\r' | head -n1)
    local mount_locks
    mount_locks=$(echo "$dump" | awk -F': ' '/MountWakeLock count:/ {print $2}' | tr -d '\r' | head -n1)
    local screen_timeout
    screen_timeout=$($ADB_CMD shell settings get system screen_off_timeout 2>/dev/null | tr -d '\r')

    echo "=========================================================="
    echo "  🥽 Meta Quest Proximity & Power State ($TARGET_SERIAL)  "
    echo "=========================================================="
    echo "  Virtual Proximity: ${prox_state:-Unknown}"
    echo "  Headset State:     ${hmd_state:-Unknown}"
    echo "  Mount WakeLocks:   ${mount_locks:-0}"
    echo "  Screen Timeout:    $(( screen_timeout / 1000 ))s"
    echo "=========================================================="
}

disable_proximity() {
    resolve_device
    echo "Disabling Meta Quest proximity sensor and preventing sleep..."

    # Wake screen if off
    $ADB_CMD shell input keyevent 224 2>/dev/null || true
    $ADB_CMD shell input keyevent 82 2>/dev/null || true

    # Prevent Android display sleep
    $ADB_CMD shell svc power stayon true 2>/dev/null || true
    $ADB_CMD shell settings put system screen_off_timeout 86400000 2>/dev/null || true

    # Disable Oculus VR power manager proximity sensor automation
    $ADB_CMD shell am broadcast -a com.oculus.vrpowermanager.automation_disable >/dev/null 2>&1 || true
    $ADB_CMD shell am broadcast -a com.oculus.vrpowermanager.prox_automation_disable >/dev/null 2>&1 || true

    # Simulate headset mounted (close)
    $ADB_CMD shell am broadcast -a com.oculus.vrpowermanager.prox_close >/dev/null 2>&1 || true

    echo -e "\033[1;32m[OK]\033[0m Proximity sensor disabled and headset forced to MOUNTED (awake)."
    show_status
}

enable_proximity() {
    resolve_device
    echo "Restoring default Meta Quest proximity sensor automation..."

    $ADB_CMD shell svc power stayon false 2>/dev/null || true
    $ADB_CMD shell settings put system screen_off_timeout 15000 2>/dev/null || true

    $ADB_CMD shell am broadcast -a com.oculus.vrpowermanager.prox_far >/dev/null 2>&1 || true

    echo -e "\033[1;32m[OK]\033[0m Normal proximity automation restored."
    show_status
}

case "$ACTION" in
    disable|off)
        disable_proximity
        ;;
    enable|on)
        enable_proximity
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 [disable|enable|status]"
        exit 1
        ;;
esac
