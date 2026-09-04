# Gemini Web2API - Documentation Home

Welcome to the **Gemini Web2API** documentation. This project is a local, self-hosted REST API server that turns the free Google Gemini web interface into a programmatic API you can call from any application.

## What is this project?

Gemini Web2API automates a **headless Chromium browser** (via Playwright) to interact with `gemini.google.com`. Instead of sending prompts through the paid official Gemini API, it types your prompts into the actual web chat, waits for Gemini to stream back an answer, and returns the result as clean JSON over HTTP.

This gives developers a **free, self-hosted API endpoint** for Google Gemini — no API keys, no billing required.

## Repository overview

| | |
|---|---|
| **Language** | Python 3.8+ |
| **Web framework** | FastAPI (async) |
| **Browser automation** | Playwright (Chromium) |
| **Anti-bot detection** | `playwright-stealth` |
| **Frontend** | Vanilla HTML/CSS/JS (admin dashboard) |
| **Protocols** | REST API + Server-Sent Events (SSE) for streaming |

## Documentation sections

1. [Architecture & Project Structure](architecture.md) — how the components fit together, directory layout, and request flow.
2. [Setup & First Run](setup.md) — prerequisites, installation, authentication, and starting the server.
3. [API Reference](API.md) — every endpoint, its request/response schema, and status codes.
4. [Configuration](configuration.md) — environment variables and settings.
5. [Troubleshooting](troubleshooting.md) — common issues and fixes.

## Quick start

```bash
# 1. Install dependencies and Chromium
./start.sh setup

# 2. Log into your Google account (opens a visible browser window)
./start.sh auth

# 3. Start the API server
./start.sh serve
```

Then call the API:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain Quantum Computing in one simple sentence."}'
```

Open the admin dashboard at `http://localhost:8000`.

> **⚠️ Legal note:** This tool interacts with the Gemini web interface. Please review Google's Terms of Service before using it for anything other than personal/educational purposes, and be mindful of Google's rate limits.

## Useful CLI commands

| Command | Description |
|---|---|
| `./start.sh setup` | Create venv, install deps & Chromium |
| `./start.sh auth` | Open headful browser to log in |
| `./start.sh serve` | Start the API server |
| `./ask-gemini.sh <prompt>` | Quick CLI query against the running server |
