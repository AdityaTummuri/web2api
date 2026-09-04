# Setup & First Run

This guide walks through installing and running Gemini Web2API from scratch.

## Prerequisites

- **Python 3.8+** and `pip`
- A **Google account** that can access Gemini (gemini.google.com)
- **Linux / macOS** (Windows may work with WSL)
- Internet connection (the server uses the real web interface)

## Step 1: Install dependencies

```bash
./start.sh setup
```

This command:
1. Creates a Python virtual environment in `.venv/`.
2. Upgrades `pip`.
3. Installs the packages from `requirements.txt`.
4. Installs the Playwright **Chromium** browser.

## Step 2: Authenticate with Google

```bash
./start.sh auth
```

This launches a **visible (headful)** Chromium window. Do the following:
1. Log in to your Google account.
2. Solve any CAPTCHAs or two-factor authentication prompts.
3. Wait until you see the Gemini chat page with the "Enter a prompt here..." input box.
4. Return to the terminal and type `y` when prompted.

The script verifies the prompt input box exists, then saves your session (cookies, localStorage, profile) to `.playwright_session/`. **This directory is gitignored because it contains sensitive credentials.**

> You only need to authenticate once. The saved session is reused on every server start.

## Step 3: Start the server

```bash
./start.sh serve
```

The FastAPI server starts (default `http://0.0.0.0:8000`). On startup it:
1. Launches a **headless** Chromium using your saved session.
2. Navigates to `gemini.google.com/app`.
3. Verifies authentication (looks for the prompt input box).

If no `.playwright_session/` directory exists, the server starts but reports `Awaiting Authentication` — you need to run `./start.sh auth` first.

## Verify it works

Open the admin dashboard:

```
http://localhost:8000
```

Or make a test API call:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Say hello in 5 words."}'
```

Or use the included CLI helper:

```bash
./ask-gemini.sh What is the capital of France?
```

## Startup sequence detail

```
./start.sh serve
        │
        ▼
server.py (FastAPI lifespan startup)
        │
        ├── session folder exists?  ── No ──► status = "Awaiting Authentication"
        │                                    (run ./start.sh auth)
        └── Yes
              │
              ▼
        asyncio.create_task(start_browser_background())
              │
              ▼
        GeminiSessionManager.start()
              │  launch_persistent_context(.playwright_session/, headless=True)
              │  navigate to gemini.google.com/app
              │  verify_authentication() (input box present?)
              ▼
        status = "Connected & Ready"
```
