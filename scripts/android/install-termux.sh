#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Web2API - Android (Termux) installer
# Turns an Android phone into a Web2API bridge server.
#
# Usage (inside Termux, from the repo root):
#   bash scripts/android/install-termux.sh [--with-ssh] [--boot]
#     --with-ssh  install OpenSSH so your laptop can reach the phone over SSH
#     --boot      auto-start the server when the phone boots (needs Termux:Boot app)
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

info() { echo -e "\033[1;34m[INFO]\033[0m $1"; }
ok()   { echo -e "\033[1;32m[ OK ]\033[0m $1"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }
die()  { echo -e "\033[1;31m[FAIL]\033[0m $1" >&2; exit 1; }

WITH_SSH=0
WITH_BOOT=0
for arg in "$@"; do
    case "$arg" in
        --with-ssh) WITH_SSH=1 ;;
        --boot) WITH_BOOT=1 ;;
        -h|--help) sed -n 2,11p "$0"; exit 0 ;;
        *) warn "Ignoring unknown option: $arg" ;;
    esac
done

if [ -z "${TERMUX_VERSION:-}" ] && [[ "${PREFIX:-}" != *"com.termux"* ]]; then
    die "This script must run inside Termux on Android (install Termux from F-Droid or GitHub, not the Play Store)."
fi

# ------------------------------------------------------------------------------
info "1/5 Installing Termux packages (python, openssl)..."
pkg update -y
pkg install -y python openssl
# Prebuilt pydantic-core avoids a long Rust compile on the phone when the repo has it.
pkg install -y python-pydantic-core >/dev/null 2>&1 \
    && ok "Using prebuilt python-pydantic-core from the Termux repo" \
    || info "No prebuilt pydantic-core package; pip will provide it"
if [ "$WITH_SSH" = 1 ]; then
    pkg install -y openssh
fi
ok "Termux packages installed"

# ------------------------------------------------------------------------------
info "2/5 Creating virtual environment (.venv)..."
# --system-site-packages lets the venv reuse pkg-installed pydantic-core.
python -m venv --system-site-packages .venv
PY_BIN="$ROOT_DIR/.venv/bin/python"
"$PY_BIN" -m pip install --upgrade pip >/dev/null

info "3/5 Installing server dependencies (requirements-server.txt)..."
if ! "$PY_BIN" -m pip install -r requirements-server.txt; then
    warn "Binary wheels unavailable - building pydantic-core from source (needs Rust, ~10-20 min on a phone)."
    pkg install -y rust binutils
    ANDROID_API_LEVEL="$(getprop ro.build.version.sdk)"
    export ANDROID_API_LEVEL
    "$PY_BIN" -m pip install -r requirements-server.txt || die "Dependency install failed. See docs/install-android.md#troubleshooting"
fi
"$PY_BIN" -c "import fastapi, uvicorn, pydantic, websockets" || die "Server dependencies did not import correctly"
ok "Server dependencies installed"

# ------------------------------------------------------------------------------
info "4/5 Generating this phone's private API keys..."
"$PY_BIN" web2api_keys.py generate
ok "Keys stored in $ROOT_DIR/api.txt (chmod 600)"

# ------------------------------------------------------------------------------
info "5/5 Optional extras..."
chmod +x scripts/android/*.sh
if [ "$WITH_SSH" = 1 ]; then
    mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
    touch "$HOME/.ssh/authorized_keys" && chmod 600 "$HOME/.ssh/authorized_keys"
    ok "OpenSSH installed. Add your laptop's public key to ~/.ssh/authorized_keys (see docs)."
fi
if [ "$WITH_BOOT" = 1 ]; then
    mkdir -p "$HOME/.termux/boot"
    sed "s|__WEB2API_ROOT__|$ROOT_DIR|" scripts/android/termux-boot.sh > "$HOME/.termux/boot/web2api"
    chmod +x "$HOME/.termux/boot/web2api"
    ok "Auto-start installed in ~/.termux/boot/web2api (open the Termux:Boot app once to enable it)"
fi

echo
ok "Web2API is installed on this phone."
echo
echo "Next steps:"
echo "  1. Start the server:      bash scripts/android/start-android.sh            (SSH mode, most private)"
echo "                       or:  WEB2API_MODE=tailscale bash scripts/android/start-android.sh"
echo "  2. Install the extension in Firefox for Android and paste the bridge URL printed by the server."
echo "  3. Check everything:      bash scripts/android/doctor.sh"
echo "  Full guide: docs/install-android.md"
