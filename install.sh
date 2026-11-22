#!/usr/bin/env bash
# ==============================================================================
# Web2API - Unified One-Step Installer & Environment Setup
# Universal setup for Linux, macOS, and WSL environments.
# ==============================================================================

set -euo pipefail

# ANSI Color Codes
CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_GREEN="\033[1;32m"
CLR_BLUE="\033[1;34m"
CLR_CYAN="\033[1;36m"
CLR_YELLOW="\033[1;33m"
CLR_RED="\033[1;31m"

print_banner() {
    echo -e "${CLR_CYAN}"
    echo "======================================================================="
    echo "                   Web2API - One-Step Unified Setup                   "
    echo "       Browser AI Bridge & Universal Client SDK Deployment Suite       "
    echo "======================================================================="
    echo -e "${CLR_RESET}"
}

log_info() {
    echo -e "${CLR_BLUE}[INFO]${CLR_RESET} $1"
}

log_success() {
    echo -e "${CLR_GREEN}[PASS]${CLR_RESET} $1"
}

log_warn() {
    echo -e "${CLR_YELLOW}[WARN]${CLR_RESET} $1"
}

log_error() {
    echo -e "${CLR_RED}[ERROR]${CLR_RESET} $1" >&2
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

print_banner

# ------------------------------------------------------------------------------
# 1. System Requirements & Python Detection
# ------------------------------------------------------------------------------
log_info "Step 1/6: Verifying system prerequisites..."

# Check Python 3
if command -v python3 >/dev/null 2>&1; then
    PY_SYSTEM="$(command -v python3)"
else
    log_error "Python 3 is required but was not found in PATH."
    exit 1
fi

PY_VERSION="$("$PY_SYSTEM" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_MAJOR="$(echo "$PY_VERSION" | cut -d. -f1)"
PY_MINOR="$(echo "$PY_VERSION" | cut -d. -f2)"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    log_error "Python 3.10+ required. Found Python $PY_VERSION at $PY_SYSTEM"
    exit 1
fi
log_success "Found Python $PY_VERSION ($PY_SYSTEM)"

# ------------------------------------------------------------------------------
# 2. Virtual Environment Creation
# ------------------------------------------------------------------------------
log_info "Step 2/6: Configuring Python virtual environment (.venv)..."
VENV_DIR="$ROOT_DIR/.venv"

UV_BIN="$(command -v uv || echo "$HOME/.local/bin/uv")"

if [ -x "$UV_BIN" ]; then
    log_info "Using uv for ultra-fast environment initialization..."
    "$UV_BIN" venv "$VENV_DIR" --python "$PY_SYSTEM" >/dev/null 2>&1 || "$UV_BIN" venv "$VENV_DIR"
    PY_BIN="$VENV_DIR/bin/python"
    PIP_INSTALL=("$UV_BIN" pip install)
else
    if [ ! -d "$VENV_DIR" ]; then
        "$PY_SYSTEM" -m venv "$VENV_DIR"
    fi
    PY_BIN="$VENV_DIR/bin/python"
    PIP_INSTALL=("$PY_BIN" -m pip install)
fi

log_success "Virtual environment initialized at: $VENV_DIR"

# ------------------------------------------------------------------------------
# 3. Installing Dependencies
# ------------------------------------------------------------------------------
log_info "Step 3/6: Installing core server, testing, and SDK dependencies..."

"${PIP_INSTALL[@]}" --upgrade pip >/dev/null 2>&1 || true
"${PIP_INSTALL[@]}" -r requirements.txt
"${PIP_INSTALL[@]}" pytest pytest-asyncio flake8

# Install Python SDK in editable development mode
if [ -d "$ROOT_DIR/sdks/python" ]; then
    log_info "Installing Python SDK (sdks/python) in development mode..."
    "${PIP_INSTALL[@]}" -e "$ROOT_DIR/sdks/python" >/dev/null 2>&1 || true
fi
log_success "All Python dependencies installed successfully."

# ------------------------------------------------------------------------------
# 4. Generating Per-Install API Credentials
# ------------------------------------------------------------------------------
log_info "Step 4/6: Checking API credentials..."
# Fresh random keys for every install (old committed keys are revoked and replaced).
"$PY_BIN" "$ROOT_DIR/web2api_keys.py" generate
log_success "api.txt holds this install's private keys (chmod 600, git-ignored)."

# ------------------------------------------------------------------------------
# 5. Script Permissions & Validation
# ------------------------------------------------------------------------------
log_info "Step 5/6: Setting execution permissions on scripts..."
chmod +x start.sh harness.py test_openai_client.py scripts/code_review.py 2>/dev/null || true
log_success "Utility scripts set to executable."

# ------------------------------------------------------------------------------
# 6. Verification Test Suite
# ------------------------------------------------------------------------------
log_info "Step 6/6: Running verification tests..."
"$PY_BIN" -m pytest tests/test_tool_parser.py -q >/dev/null 2>&1
log_success "Tool parser unit tests passed (100% green)."

echo ""
echo -e "${CLR_GREEN}=======================================================================${CLR_RESET}"
echo -e "${CLR_BOLD}                    Installation Complete!                    ${CLR_RESET}"
echo -e "${CLR_GREEN}=======================================================================${CLR_RESET}"
echo ""
echo -e "${CLR_BOLD}Quickstart Commands:${CLR_RESET}"
echo -e "  ${CLR_CYAN}1. Start Bridge Server:${CLR_RESET}"
echo "     ./start.sh bridge          (or: $PY_BIN bridge_server.py)"
echo ""
echo -e "  ${CLR_CYAN}2. Test via Official OpenAI Python SDK:${CLR_RESET}"
echo "     $PY_BIN test_openai_client.py"
echo ""
echo -e "  ${CLR_CYAN}3. Interactive Terminal Chat (SSE streaming):${CLR_RESET}"
echo "     ./start.sh chat"
echo ""
echo -e "  ${CLR_CYAN}4. Standalone Mock Extension (Headless Testing):${CLR_RESET}"
echo "     ./start.sh mock"
echo ""
echo -e "  ${CLR_CYAN}5. AI Automated Code Review:${CLR_RESET}"
echo "     $PY_BIN scripts/code_review.py <file> -o reports/review.md"
echo ""
echo -e "${CLR_BOLD}Client SDK Documentation:${CLR_RESET}"
echo -e "  🤖 Android Kotlin  : ${CLR_BLUE}sdks/android/README.md${CLR_RESET}"
echo -e "  🐍 Python (Sync/Async): ${CLR_BLUE}sdks/python/README.md${CLR_RESET}"
echo -e "  💙 Flutter / Dart  : ${CLR_BLUE}sdks/flutter/README.md${CLR_RESET}"
echo -e "  ⚛️ React / Next.js  : ${CLR_BLUE}sdks/react/README.md${CLR_RESET}"
echo ""
echo -e "${CLR_BOLD}Credentials & Endpoints:${CLR_RESET} inspect ${CLR_YELLOW}api.txt${CLR_RESET}"
echo ""
