#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Show the extension bridge URL (with your key) on a page that only this phone
# can open, so you can copy-paste it into Firefox instead of typing a long key.
#
#   bash scripts/android/show-bridge-url.sh        # then open http://127.0.0.1:8001 in Firefox
#
# The page listens on 127.0.0.1 only and shuts down after 5 minutes (WEB2API_URL_PAGE_SECS).
# ==============================================================================
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
PORT="${PORT:-8000}"
PAGE_PORT="${WEB2API_URL_PAGE_PORT:-8001}"
SECS="${WEB2API_URL_PAGE_SECS:-300}"
PY_BIN="$ROOT_DIR/.venv/bin/python"
[ -x "$PY_BIN" ] || PY_BIN="python"

KEY="$("$PY_BIN" web2api_keys.py show)" || exit 1
DIR="$(mktemp -d)"
chmod 700 "$DIR"
trap 'rm -rf "$DIR"' EXIT
cat > "$DIR/index.html" <<HTML
<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><title>Web2API bridge URL</title>
<body style="font:18px sans-serif;padding:16px">
<h3>Web2API bridge URL</h3>
<p>Tap <b>Copy</b>, then open the Web2API extension popup, paste it into <i>Bridge URL</i> and tap <b>Connect</b>.</p>
<textarea id=u rows=4 style="width:100%;font:15px monospace" readonly>ws://127.0.0.1:$PORT/ws?token=$KEY</textarea>
<p><button id=b style="font-size:20px;padding:10px 24px">Copy</button></p>
<script>b.onclick=()=>{u.select();try{document.execCommand("copy")}catch(e){};b.textContent="Copied!"}</script>
</body>
HTML

echo "Open  http://127.0.0.1:$PAGE_PORT  in Firefox on this phone (closes in $((SECS / 60)) min, Ctrl+C to stop now)."
cd "$DIR"
"$PY_BIN" -c "
import http.server, socketserver, threading, sys
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
with socketserver.TCPServer(('127.0.0.1', int(sys.argv[1])), Quiet) as srv:
    threading.Timer(int(sys.argv[2]), srv.shutdown).start()
    srv.serve_forever()
" "$PAGE_PORT" "$SECS"
