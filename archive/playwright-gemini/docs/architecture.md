# Architecture & Project Structure

This document explains how Gemini Web2API is organized and how a request flows through the system.

## High-level diagram

```
 User/Client (curl, Python, Node, dashboard)
      │
      │  POST /api/chat            GET / (dashboard HTML)
      ▼                            ▼
 ┌──────────────┐           ┌───────────────┐
 │  FastAPI     │           │  Jinja2       │
 │  (server.py) │           │  index.html   │
 └──────┬───────┘           └───────────────┘
        │  asyncio.Lock (serializes all requests)
        ▼
 ┌──────────────────────────────┐
 │  GeminiSessionManager        │
 │  (session_manager.py)        │
 │  • check_and_recover()       │  self-healing
 │  • verify_authentication()   │  login check
 │  • fill input / click send   │  prompt submission
 │  • poll response element     │  wait for stabilization
 └──────┬───────────────────────┘
        │  Playwright (headless Chromium)
        ▼
        gemini.google.com
```

## File-by-file breakdown

### `start.sh`
Management CLI — the single entry point. Subcommands:
- `setup` — creates `.venv/`, installs pip dependencies, installs Playwright Chromium.
- `auth` — runs `setup_session.py` for manual Google login.
- `serve` — starts the FastAPI server.
- `help` — prints usage.

Uses `set -euo pipefail` for strict error handling and auto-runs setup if the environment isn't initialized.

### `setup_session.py`
One-time **interactive authentication** script. Launches a **visible (headful)** Chromium window so you can:
1. Log into your Google account.
2. Solve any CAPTCHAs / 2FA prompts.
3. Confirm the Gemini chat page loaded.

It persists cookies, localStorage, and profile state into `.playwright_session/`, which is later reused by the headless server.

### `session_manager.py`
The **core browser automation engine** (`GeminiSessionManager` class). Responsibilities:

| Method | Purpose |
|---|---|
| `start()` | Launch persistent Chromium context, navigate to Gemini, verify login. |
| `stop()` | Gracefully shut down the browser. |
| `verify_authentication()` | Ensure the prompt input box exists; raise if redirected to login. |
| `check_and_recover()` | Self-heal: if the page is dead, restart the browser. |
| `send_prompt()` | Submit a prompt and return the stabilized final text. |
| `send_prompt_stream()` | Async generator that yields text deltas (used for SSE). |
| `new_chat()` | Reset the conversation thread. |
| `take_screenshot_base64()` | Capture current page as base64 PNG (for the dashboard). |

**Key technique — stabilization:** After sending a prompt, the manager polls the response element every 500ms. It considers generation complete when the text has not changed for 1.5 seconds (3 consecutive identical polls) AND the "Stop" button is no longer visible.

### `server.py`
The FastAPI application. Defines all HTTP routes, Pydantic schemas, and diagnostic logging. See [API.md](API.md) for the full endpoint reference.

### `templates/index.html`
A single-page **admin dashboard** (glassmorphic dark UI) rendered by Jinja2. It polls the API on intervals to show:
- Live connection status (green/amber/red badge) — every 3s.
- Live headless browser screenshot — every 5s.
- Recent request logs table — every 4s.
- An interactive chat playground and an API integration guide with copy-paste snippets.

### `ask-gemini.sh`
A tiny Bash CLI client that posts a prompt to `http://localhost:8000/api/chat` via curl and pretty-prints the JSON.

### `requirements.txt`
Pinned Python dependencies: `fastapi`, `uvicorn`, `playwright`, `playwright-stealth`, `jinja2`, `pydantic`.

## How a chat request flows (step by step)

1. The client `POST`s JSON `{ "prompt": "...", "timeout_sec": 90 }` to `/api/chat`.
2. `server.py` checks `manager.is_connected` — returns `401` if unauthenticated, or `503` if the browser is offline.
3. It acquires the global `asyncio.Lock` (ensures only one browser interaction at a time, avoiding bot detection).
4. `send_prompt()` runs:
   - `check_and_recover()` — restarts the browser if it crashed.
   - `verify_authentication()` — confirms the prompt input box exists.
   - Counts existing message elements to locate where the new response will appear.
   - Fills the contenteditable input box and clicks Send (falls back to pressing Enter).
   - Waits up to 10s for a new response element to appear.
   - Polls every 500ms until the text stabilizes for 1.5s and the Stop button disappears.
5. The response latency and log entry are recorded, and the JSON result is returned.

## Streaming (SSE)

`/api/chat/stream` uses the same prompt-submission logic but yields new text **deltas** as they appear (polling every 400ms). FastAPI wraps this in a `StreamingResponse` with `text/event-stream` media type. The client receives `data: <delta>` events followed by a final `data: [DONE]`.

## Self-healing

The browser can crash or the tab can close during long periods of idle. `check_and_recover()` is invoked before every request:
1. It runs `page.evaluate("1 + 1")` to test if the page is still alive.
2. If not healthy, it stops the browser and starts a fresh session using the persistent profile.
