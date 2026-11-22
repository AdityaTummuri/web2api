#!/usr/bin/env bash
# ==============================================================================
# Run on your LAPTOP: open an SSH tunnel to the Web2API server on your phone.
#
#   scripts/android/connect-from-laptop.sh <phone-host> [ssh-user] [port]
#
#   <phone-host>  Tailscale name/IP (e.g. my-phone or 100.x.y.z) or LAN IP
#   ssh-user      Termux user (run 'whoami' in Termux, looks like u0_a123)
#
# After it connects, use http://127.0.0.1:<port>/v1 with the key from the phone's api.txt.
# ==============================================================================
set -euo pipefail

PHONE="${1:-}"
SSH_USER="${2:-}"
PORT="${3:-${PORT:-8000}}"
SSH_PORT="${SSH_PORT:-8022}"
REMOTE_DIR="${WEB2API_REMOTE_DIR:-web2api}"

if [ -z "$PHONE" ]; then
    sed -n 3,11p "$0"
    exit 1
fi
TARGET="${SSH_USER:+$SSH_USER@}$PHONE"

echo "[INFO] Tunnel: laptop 127.0.0.1:$PORT  ->  $TARGET:$SSH_PORT  ->  phone 127.0.0.1:$PORT"
ssh -f -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
    -p "$SSH_PORT" -L "$PORT:127.0.0.1:$PORT" "$TARGET"

if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "[ OK ] Phone server reachable at http://127.0.0.1:$PORT/v1"
else
    echo "[WARN] Tunnel is up but the server did not answer - is start-android.sh running on the phone?"
fi

echo "[INFO] Fetch your key:  ssh -p $SSH_PORT $TARGET 'cd $REMOTE_DIR && .venv/bin/python web2api_keys.py show'"
echo "[INFO] Close tunnel:    pkill -f 'ssh -f -N .* -L $PORT:127.0.0.1:$PORT'"
