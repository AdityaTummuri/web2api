#!/bin/bash

# Web2API Startup and Manager Script
# Implements robust environment verification and launcher utilities using uv.

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

# Find uv if available
UV_BIN="$(which uv 2>/dev/null || echo "/home/suzaykid/.local/bin/uv")"

# setup_env: create virtualenv and install deps with uv
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

    # Install playwright browser if needed
    if [ -f "$VENV_DIR/bin/playwright" ]; then
        "$VENV_DIR/bin/playwright" install chromium || true
    fi
}

# show_help: print usage information
show_help() {
    echo "Web2API Management CLI"
    echo "Usage:"
    echo "  $0 bridge         - Start the Web2API Firefox Extension Bridge Server (OpenAI REST + WebSocket)"
    echo "  $0 serve          - Start the Playwright Headless FastAPI server"
    echo "  $0 setup          - Initialize virtualenv with uv and install dependencies"
    echo "  $0 auth           - Launch headful browser to log in manually (Playwright mode)"
    echo "  $0 help           - Display this help message"
}

ensure_setup() {
    if [ ! -d "$VENV_DIR" ]; then
        log "Environment not initialized. Running setup with uv..."
        setup_env
    fi
}

COMMAND="${1:-help}"

case "$COMMAND" in
    setup)
        setup_env
        log "Setup complete! Run '$0 bridge' for Firefox extension mode or '$0 auth' for Playwright mode."
        ;;
    bridge)
        ensure_setup
        log "Starting Web2API Firefox Extension Bridge Server on http://127.0.0.1:8000..."
        exec "$VENV_DIR/bin/python3" bridge_server.py
        ;;
    serve)
        ensure_setup
        log "Starting Playwright FastAPI Server on http://127.0.0.1:8000..."
        exec "$VENV_DIR/bin/python3" server.py
        ;;
    auth)
        ensure_setup
        log "Starting authentication window..."
        exec "$VENV_DIR/bin/python3" setup_session.py
        ;;
    help|*)
        show_help
        ;;
esac
