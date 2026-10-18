#!/usr/bin/env bash
# ==============================================================================
# Xash3D VR - Meta Quest Battery & Thermal Health Inspector
# ==============================================================================
# Queries battery percentage, charging state, voltage, and thermals via ADB.
# Supports raw output, visual progress bars, low-battery alerts, and watch mode.
# ==============================================================================

set -euo pipefail

MODE="${1:-display}" # display | raw | json | watch

# Ensure ADB is available
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
        if [ "$MODE" = "raw" ]; then
            echo "-1"
        else
            echo -e "\033[1;31m[ERROR]\033[0m No authorized Meta Quest device found in 'adb devices'." >&2
        fi
        exit 1
    fi

    TARGET_SERIAL=$(echo "$devices" | head -n1)
    ADB_CMD="adb -s $TARGET_SERIAL"
}

get_battery_data() {
    local raw_info
    raw_info=$($ADB_CMD shell dumpsys battery 2>/dev/null || true)
    
    LEVEL=$(echo "$raw_info" | awk '$1 == "level:" {print $2}' | tr -d '\r')
    SCALE=$(echo "$raw_info" | awk '$1 == "scale:" {print $2}' | tr -d '\r')
    STATUS_CODE=$(echo "$raw_info" | awk '$1 == "status:" {print $2}' | tr -d '\r')
    HEALTH_CODE=$(echo "$raw_info" | awk '$1 == "health:" {print $2}' | tr -d '\r')
    TEMP_RAW=$(echo "$raw_info" | awk '$1 == "temperature:" {print $2}' | tr -d '\r')
    VOLTAGE_RAW=$(echo "$raw_info" | awk '$1 == "voltage:" {print $2}' | tr -d '\r')
    USB_POWERED=$(echo "$raw_info" | awk '$1 == "USB" && $2 == "powered:" {print $3}' | tr -d '\r')
    AC_POWERED=$(echo "$raw_info" | awk '$1 == "AC" && $2 == "powered:" {print $3}' | tr -d '\r')

    LEVEL="${LEVEL:-0}"
    SCALE="${SCALE:-100}"
    STATUS_CODE="${STATUS_CODE:-1}"
    TEMP_RAW="${TEMP_RAW:-0}"
    VOLTAGE_RAW="${VOLTAGE_RAW:-0}"

    TEMP_C=$(awk "BEGIN {printf \"%.1f\", $TEMP_RAW / 10}")
    VOLT_V=$(awk "BEGIN {printf \"%.2f\", $VOLTAGE_RAW / 1000}")

    case "$STATUS_CODE" in
        2) STATUS_STR="Charging ⚡" ;;
        3) STATUS_STR="Discharging 🔋" ;;
        4) STATUS_STR="Not charging" ;;
        5) STATUS_STR="Full 🔌" ;;
        *) STATUS_STR="Unknown" ;;
    esac

    POWER_SOURCE="Battery"
    if [ "$USB_POWERED" = "true" ]; then
        POWER_SOURCE="USB"
    elif [ "$AC_POWERED" = "true" ]; then
        POWER_SOURCE="AC Wall Charger"
    fi
}

render_progress_bar() {
    local pct=$1
    local width=20
    local filled=$(( (pct * width) / 100 ))
    local empty=$(( width - filled ))
    local bar=""
    local color="\033[1;32m" # Green

    if [ "$pct" -le 20 ]; then
        color="\033[1;31m" # Red
    elif [ "$pct" -le 45 ]; then
        color="\033[1;33m" # Yellow
    fi

    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done

    echo -e "${color}[${bar}] ${pct}%\033[0m"
}

show_status() {
    resolve_device
    get_battery_data

    local model
    model=$($ADB_CMD shell getprop ro.product.model 2>/dev/null | tr -d '\r')
    model=$(echo "$model" | sed -e 's/Quest_3S/Quest 3/g' -e 's/Quest 3S/Quest 3/g')

    echo "=========================================================="
    echo "  🥽 Meta Quest Battery & Thermal Health Monitor          "
    echo "=========================================================="
    echo "  Device:       $model ($TARGET_SERIAL)"
    echo -n "  Battery:      "
    render_progress_bar "$LEVEL"
    echo "  Status:       $STATUS_STR (Source: $POWER_SOURCE)"
    echo "  Temperature:  $TEMP_C °C"
    echo "  Voltage:      $VOLT_V V"
    echo "=========================================================="

    if [ "$LEVEL" -le 15 ]; then
        echo -e "\033[1;31m  [CRITICAL ALERT] Battery is critically low (${LEVEL}%)!\033[0m"
        echo "  Connect headset to a high-power charger before starting tests."
        echo "=========================================================="
        return 2
    elif [ "$LEVEL" -le 30 ]; then
        echo -e "\033[1;33m  [WARNING] Battery below 30% (${LEVEL}%). Long tests may discharge.\033[0m"
        echo "=========================================================="
        return 0
    fi
    return 0
}

case "$MODE" in
    raw)
        resolve_device
        get_battery_data
        echo "$LEVEL"
        ;;
    json)
        resolve_device
        get_battery_data
        echo "{\"level\":$LEVEL,\"status\":\"$STATUS_STR\",\"source\":\"$POWER_SOURCE\",\"temp_c\":$TEMP_C,\"voltage_v\":$VOLT_V,\"serial\":\"$TARGET_SERIAL\"}"
        ;;
    watch|-w|--watch)
        INTERVAL="${2:-5}"
        echo "Watching Meta Quest battery every ${INTERVAL}s (Press Ctrl+C to stop)..."
        while true; do
            clear || true
            show_status || true
            sleep "$INTERVAL"
        done
        ;;
    display|*)
        show_status
        ;;
esac
