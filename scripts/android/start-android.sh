#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Web2API - start the bridge server on an Android phone (Termux)
#
# Modes (WEB2API_MODE):
#   ssh        (default) bind 127.0.0.1 only. Your laptop reaches it through an
#              SSH tunnel: nothing is exposed to any network. Also starts sshd.
#   tailscale  bind 0.0.0.0 so laptops on your tailnet can call it directly
#              (API key always required). Prints the phone's Tailscale address.
#
# Env: PORT (default 8000)
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

MODE="${WEB2API_MODE:-ssh}"
PORT="${PORT:-8000}"
PY_BIN="$ROOT_DIR/.venv/bin/python"
[ -x "$PY_BIN" ] || PY_BIN="python"

info() { echo -e "\033[1;34m[INFO]\033[0m $1"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }
die()  { echo -e "\033[1;31m[FAIL]\033[0m $1" >&2; exit 1; }

KEY="$("$PY_BIN" web2api_keys.py show 2>/dev/null)" || die "No API key found. Run: python web2api_keys.py generate"

# Keep the CPU awake while the screen is off, otherwise Android suspends the server.
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock && info "Wake lock acquired (release with: termux-wake-unlock)"
fi

# Best-effort Tailscale address detection: a UDP 'connect' reveals which local IP
# routes to the tailnet, with no special permissions and no packets sent.
TS_IP="$("$PY_BIN" - <<'PY' 2>/dev/null || true
import ipaddress, socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("100.100.100.100", 53))
    ip = s.getsockname()[0]
    print(ip if ipaddress.ip_address(ip) in ipaddress.ip_network("100.64.0.0/10") else "")
finally:
    s.close()
PY
)"

case "$MODE" in
    ssh)
        HOST="127.0.0.1"
        if command -v sshd >/dev/null 2>&1; then
            pgrep -x sshd >/dev/null 2>&1 || sshd
            info "sshd running on port 8022 (user: $(whoami))"
        else
            warn "OpenSSH not installed - run: pkg install openssh   (or use WEB2API_MODE=tailscale)"
        fi
        ;;
    tailscale)
        HOST="0.0.0.0"
        [ -n "$TS_IP" ] || warn "Tailscale address not detected - is the Tailscale app connected on this phone?"
        ;;
    *)
        die "Unknown WEB2API_MODE '$MODE' (use: ssh | tailscale)"
        ;;
esac

PHONE_ADDR="${TS_IP:-<phone-ip-or-tailscale-name>}"
echo
echo "================================================================================"
echo " Web2API on Android  -  mode: $MODE"
echo "================================================================================"
echo " 1) In Firefox on THIS phone, open the Web2API extension popup and set Bridge URL:"
echo "      ws://127.0.0.1:$PORT/ws?token=$KEY"
echo
echo " 2) On your laptop:"
if [ "$MODE" = "ssh" ]; then
    echo "      ssh -N -p 8022 -L $PORT:127.0.0.1:$PORT $(whoami)@$PHONE_ADDR"
    echo "      (or: scripts/android/connect-from-laptop.sh $PHONE_ADDR)"
    echo "    then use base URL http://127.0.0.1:$PORT/v1"
else
    echo "      base URL http://$PHONE_ADDR:$PORT/v1"
fi
echo "    API key: see api.txt on the phone (cat $ROOT_DIR/api.txt)"
echo "================================================================================"
echo

export HOST PORT
exec "$PY_BIN" bridge_server.py
