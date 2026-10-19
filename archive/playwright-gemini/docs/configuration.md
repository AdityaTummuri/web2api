# Configuration

Gemini Web2API is configured through environment variables. All are optional.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Network interface the server binds to. Set to `127.0.0.1` to expose only locally. |
| `PORT` | `8000` | TCP port the server listens on. |
| `HEADLESS` | `true` | Whether the Chromium browser runs headless (`true`/`1`/`yes`). The `auth` step always runs headful to allow manual login. |

### Usage examples

```bash
# Run on a custom host/port, headless
HOST=127.0.0.1 PORT=9000 HEADLESS=true ./start.sh serve
```

## Fixed settings

These are hard-coded in the source and not configurable without editing:

- **Session directory:** `.playwright_session/` (relative to project root).
- **Gemini URL:** `https://gemini.google.com/app`.
- **Browser viewport:** 1280x850.
- **Default prompt timeout:** 90s (configurable per-request via `timeout_sec`, range 10–180).
- **Response stabilization:** text must be unchanged for ~1.5s and the Stop button gone.
- **Log cap:** last 50 request entries kept in memory.
- **Playwright Chromium flags:** `--disable-blink-features=AutomationControlled`, `--no-sandbox`, `--disable-dev-shm-usage`.
- **Browser viewport:** 1280x850.

## Files that hold config

- `server.py` — reads `HOST`, `PORT`, `HEADLESS`; defines `BASE_DIR`, `TEMPLATES_DIR`, `SESSION_DIR`.
- `start.sh` — the CLI, defines venv location.
- `requirements.txt` — pinned dependency versions.

## Runtime data

- `.playwright_session/` — persistent browser profile with auth cookies (gitignored).
- `.venv/` — Python virtual environment (gitignored).
- `request_logs` — in-memory list in `server.py`, reset on restart.
