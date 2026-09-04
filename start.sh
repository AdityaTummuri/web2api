#!/bin/bash

# Web2API Startup and Manager Script
# Implements robust environment verification and launcher utilities.
# This is the single entry point for: setting up the environment, authenticating,
# and serving the API. See docs/ for details.

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

# setup_env: create the virtualenv (if missing), install deps, install Chromium
setup_env() {
    if [ ! -d "$VENV_DIR" ]; then
        log "Creating virtual environment in $VENV_DIR..."
        python3 -m venv "$VENV_DIR"
    fi

    log "Activating virtual environment..."
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"

    log "Upgrading pip..."
    pip install --upgrade pip

    log "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt

    log "Installing Playwright Chromium browser..."
    playwright install chromium
}

# show_help: print usage information
show_help() {
    echo "Web2API Management CLI"
    echo "Usage:"
    echo "  $0 setup          - Initialize virtualenv and install dependencies"
    echo "  $0 auth           - Launch headful browser to log in manually"
    echo "  $0 serve          - Start the FastAPI server with administrative dashboard"
    echo "  $0 help           - Display this help message"
}

# ensure_setup: make sure the environment exists (auto-run setup if missing)
ensure_setup() {
    if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/playwright" ]; then
        log "Environment not initialized. Running setup..."
        setup_env
    else
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
    fi
}

# Parse the first arg as the subcommand (default: help)
COMMAND="${1:-help}"

case "$COMMAND" in
    setup)
        setup_env
        log "Setup complete! Run '$0 auth' to log into Gemini."
        ;;
    auth)
        ensure_setup
        log "Starting authentication window..."
        python3 setup_session.py
        ;;
    serve)
        ensure_setup
        log "Starting FastAPI Server..."
        # Run server using uvicorn
        python3 server.py
        ;;
    help|*)
        show_help
        ;;
esac
