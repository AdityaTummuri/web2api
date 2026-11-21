#!/bin/bash

# Web2API Startup and Manager Script
# Implements robust environment verification, bridge launching, and harness utilities.

set -euo pipefail

# Work directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"

log() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1" >&2
}

# Resolve Python runner (venv if present, otherwise system python3)
if [ -f "$VENV_DIR/bin/python3" ]; then
    PY_BIN="$VENV_DIR/bin/python3"
else
    PY_BIN="python3"
fi

# Find uv if available
UV_BIN="$(which uv 2>/dev/null || echo "/home/suzaykid/.local/bin/uv")"

setup_env() {
    if [ -x "$UV_BIN" ]; then
        log "Using uv to initialize virtual environment..."
        "$UV_BIN" venv "$VENV_DIR"
        "$UV_BIN" pip install -r requirements.txt
    else
        log "uv not found, using python3 venv..."
        if [ ! -d "$VENV_DIR" ]; then
            python3 -m venv "$VENV_DIR"
        fi
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
        pip install --upgrade pip
        pip install -r requirements.txt
    fi

    if [ -f "$VENV_DIR/bin/playwright" ]; then
        "$VENV_DIR/bin/playwright" install chromium || true
    fi
}

show_help() {
    echo "Web2API Management CLI"
    echo "Usage:"
    echo "  $0 bridge         - Start the Web2API Extension Bridge Server (REST API + WebSocket)"
    echo "  $0 harness <cmd>  - Run test, mock, or agent connection harness (test, mock, chat, acp)"
    echo "  $0 mock           - Run standalone mock browser extension on WebSocket"
    echo "  $0 chat           - Interactive terminal chat with real-time SSE streaming"
    echo "  $0 serve          - Start the Playwright Headless FastAPI server"
    echo "  $0 setup          - Initialize virtualenv with uv and install dependencies"
    echo "  $0 help           - Display this help message"
}

COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
    setup)
        exec "$SCRIPT_DIR/install.sh"
        ;;
    bridge)
        log "Starting Web2API Firefox / Zen Bridge Server on http://127.0.0.1:8000..."
        exec "$PY_BIN" bridge_server.py
        ;;
    harness)
        exec "$PY_BIN" harness.py "$@"
        ;;
    mock)
        exec "$PY_BIN" harness.py mock "$@"
        ;;
    chat)
        exec "$PY_BIN" harness.py chat "$@"
        ;;
    serve)
        log "Starting Playwright FastAPI Server on http://127.0.0.1:8000..."
        exec "$PY_BIN" server.py
        ;;
    auth)
        log "Starting authentication window..."
        exec "$PY_BIN" setup_session.py
        ;;
    help|*)
        show_help
        ;;
esac
