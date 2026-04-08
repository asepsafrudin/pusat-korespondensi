#!/bin/bash
# PUU Universal Hub - Run Script

VENV_PATH="/home/aseps/MCP/.venv"
PYTHON_BIN="$VENV_PATH/bin/python3"
SRC_PATH="/home/aseps/MCP/korespondensi-server/src/main.py"

# Enforce Env
export PYTHONPATH="/home/aseps/MCP/korespondensi-server"

echo "Checking environment..."
if [ ! -d "$VENV_PATH" ]; then
    echo "ERROR: Virtual environment not found at $VENV_PATH"
    exit 1
fi

# Run logic
# Default: web app
# Use 'mcp' argument to run mcp server
MODE=${1:-web}

echo "Launching PUU Hub in MODE: $MODE"
$PYTHON_BIN $SRC_PATH --mode $MODE
