#!/bin/bash
# PUU Universal Hub - Run Script

set -euo pipefail

VENV_PATH="/home/aseps/MCP/.venv"
PYTHON_BIN="$VENV_PATH/bin/python3"
SRC_PATH="/home/aseps/MCP/korespondensi-server/src/main.py"
WIN_HEALTH_SCRIPT="/home/aseps/MCP/korespondensi-server/scripts/windows_network_health.ps1"
WEB_PORT="${WEB_PORT:-8082}"

# Enforce Env
export PYTHONPATH="/home/aseps/MCP/korespondensi-server"

echo "Checking environment..."
if [ ! -d "$VENV_PATH" ]; then
    echo "ERROR: Virtual environment not found at $VENV_PATH"
    exit 1
fi

# Run logic
# Default: web app
# Modes:
#   web      -> run web app
#   mcp      -> run MCP stdio server
#   doctor   -> run connectivity health-check only
MODE=${1:-web}
DOCTOR_FLAG="${2:-}"

run_doctor() {
    echo ""
    echo "=== Korespondensi Connectivity Doctor ==="
    echo "WSL/Linux IPv4:"
    hostname -I | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' || true
    echo ""
    echo "Local endpoint check:"
    if curl -fsS "http://127.0.0.1:${WEB_PORT}/" >/dev/null; then
        echo "  OK   http://127.0.0.1:${WEB_PORT}/"
    else
        echo "  FAIL http://127.0.0.1:${WEB_PORT}/"
    fi
    echo ""
    echo "Listening socket check:"
    ss -ltnp 2>/dev/null | grep -E ":${WEB_PORT}\b" || echo "  No process listening on :${WEB_PORT}"

    if command -v powershell.exe >/dev/null 2>&1 && [ -f "$WIN_HEALTH_SCRIPT" ]; then
        echo ""
        echo "Windows network health-check:"
        powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w "$WIN_HEALTH_SCRIPT")" -Port "$WEB_PORT" || true
    fi
    echo "=== End Doctor ==="
}

echo "Launching PUU Hub in MODE: $MODE"
case "$MODE" in
    web|mcp)
        if [ "$DOCTOR_FLAG" = "--doctor" ]; then
            run_doctor
        fi
        "$PYTHON_BIN" "$SRC_PATH" --mode "$MODE"
        ;;
    doctor)
        run_doctor
        ;;
    *)
        echo "ERROR: Unknown mode '$MODE'"
        echo "Usage:"
        echo "  ./run.sh web [--doctor]"
        echo "  ./run.sh mcp [--doctor]"
        echo "  ./run.sh doctor"
        exit 1
        ;;
esac
