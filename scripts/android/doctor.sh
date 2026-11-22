#!/data/data/com.termux/files/usr/bin/bash
# Web2API Android health check: dependencies, keys, server, extension, memory.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR" || exit 1
PORT="${PORT:-8000}"
PY_BIN="$ROOT_DIR/.venv/bin/python"
[ -x "$PY_BIN" ] || PY_BIN="python"

pass() { echo -e "  \033[1;32m✔\033[0m $1"; }
fail() { echo -e "  \033[1;31m✘\033[0m $1"; FAILED=1; }
note() { echo -e "  \033[1;33m•\033[0m $1"; }
FAILED=0

echo "Web2API doctor"
if [ -n "${TERMUX_VERSION:-}" ]; then pass "Termux $TERMUX_VERSION"; else note "Not running inside Termux"; fi

if "$PY_BIN" -c "import fastapi, uvicorn, pydantic, websockets" 2>/dev/null; then
    pass "Server dependencies importable ($("$PY_BIN" --version 2>&1))"
else
    fail "Server dependencies missing - run: bash scripts/android/install-termux.sh"
fi

if KEY="$("$PY_BIN" web2api_keys.py show 2>/dev/null)"; then
    pass "API key configured (${KEY:0:14}...)"
else
    fail "No API key - run: python web2api_keys.py generate"
fi

HEALTH="$("$PY_BIN" - "$PORT" <<'PY' 2>/dev/null
import json, sys, urllib.request
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[1]}/health", timeout=3) as r:
        d = json.load(r)
    print("up", "connected" if d.get("extension_connected") else "disconnected", d.get("auth_required"))
except Exception:
    print("down")
PY
)"
case "$HEALTH" in
    up\ connected*) pass "Server running on port $PORT"; pass "Browser extension connected" ;;
    up\ disconnected*) pass "Server running on port $PORT"
        fail "Extension NOT connected - open Firefox, check the popup's bridge URL includes ?token=<key>" ;;
    *) fail "Server not reachable on 127.0.0.1:$PORT - run: bash scripts/android/start-android.sh" ;;
esac
case "$HEALTH" in *True) pass "API key enforced on all requests" ;; up*) fail "Server is running WITHOUT auth" ;; esac

if pgrep -x sshd >/dev/null 2>&1; then pass "sshd running (port 8022)"; else note "sshd not running (needed for SSH mode: run 'sshd')"; fi

if [ -r /proc/meminfo ]; then
    AVAIL_MB=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
    TOTAL_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
    if [ "${AVAIL_MB:-0}" -lt 400 ]; then
        fail "Low memory: ${AVAIL_MB} MB free of ${TOTAL_MB} MB - close other apps / extra browser tabs"
    else
        pass "Memory: ${AVAIL_MB} MB free of ${TOTAL_MB} MB"
    fi
fi

note "Reminder: disable battery optimisation for Termux AND Firefox, keep the phone charging."
exit $FAILED
