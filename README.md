# Gemini Web2API Server

A local REST API server that wraps the web interface of Google Gemini (`gemini.google.com`). This project enables developers to query Gemini programmatically for custom applications using a local, cost-free endpoint, effectively routing prompts through a persistent, automated browser session.

## Table of Contents

- [Motivation](#motivation)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Prerequisites](#prerequisites)
- [Installation & Quick Start](#installation--quick-start)
  - [Step 1: Environment Setup](#step-1-environment-setup)
  - [Step 2: Manual Authentication](#step-2-manual-authentication)
  - [Step 3: Serve the API](#step-3-serve-the-api)
- [REST API Reference](#rest-api-reference)
  - [1. Chat Generation](#1-chat-generation)
  - [2. Streaming Chat Generation](#2-streaming-chat-generation)
  - [3. Reset Conversation Thread](#3-reset-conversation-thread)
  - [4. System Status](#4-system-status)
  - [5. Browser Screenshot](#5-browser-screenshot)
  - [6. Execution Logs](#6-execution-logs)
  - [7. Restart Browser](#7-restart-browser)
- [Administrative Dashboard](#administrative-dashboard)
- [Integration Examples](#integration-examples)
  - [Curl (CLI)](#curl-cli)
  - [Python (requests)](#python-requests)
  - [Node.js (Fetch)](#nodejs-fetch)
  - [Bash CLI Client](#bash-cli-client)
- [Configuration](#configuration)
- [Troubleshooting & Maintenance](#troubleshooting--maintenance)
- [Terms of Service Warning](#terms-of-service-warning)

---

## Motivation

Google Gemini's official API can be expensive or subject to low credit limits. The web interface at `gemini.google.com` is free to use but lacks an API. This project solves that by bridging the two: it starts a headless browser in the background, inputs your prompt, waits for the response stream to stabilize, and returns the generated text as clean JSON.

---

## Key Features

- **FastAPI Backend**: Fast, asynchronous, and robust backend providing JSON endpoints.
- **Persistent Playwright Session**: Saves cookies, localStorage, and browser profile state locally. You only log in manually **once**.
- **Self-Healing Automation**: Automatically detects browser crashes or tab closures and starts a fresh browser instance.
- **Text Stabilization Detection**: Checks the streaming response container every 500ms. When the text content stops changing for 1.5 seconds, it returns, ensuring complete responses.
- **Concurrent Request Queuing**: Uses an `asyncio.Lock` to process requests sequentially, avoiding bot detection flags.
- **Administrative Dashboard**: A premium, responsive glassmorphic dark UI.
- **Live View Diagnostician**: Displays real-time screenshots of the headless browser directly in the dashboard, making it easy to see if a CAPTCHA or prompt is blocking the script.

---

## System Architecture

```
                    ┌────────────────────────┐
                    │  API Clients (curl...) │
                    └───────────┬────────────┘
                                │ POST /api/chat
                                ▼
                    ┌────────────────────────┐
                    │     FastAPI Server     │◄───────┐
                    └───────────┬────────────┘        │
                                │                     │ Status /
                                ▼                     │ Screenshots
                    ┌────────────────────────┐        │
                    │   asyncio.Lock Queue   │        │
                    └───────────┬────────────┘        │
                                │                     │
                                ▼                     │
  ┌────────┐        ┌────────────────────────┐        │
  │ Cookies│◄───────┤ Playwright Session Mgr ├────────┘
  └────────┘        └───────────┬────────────┘
                                │ Automates input
                                ▼
                    ┌────────────────────────┐
                    │   Headless Chromium    │
                    └───────────┬────────────┘
                                │ Fetches page
                                ▼
                    ┌────────────────────────┐
                    │   gemini.google.com    │
                    └────────────────────────┘
```

---

## Prerequisites

- Linux, macOS, or Windows
- **Python 3.8+**
- **pip** and **virtualenv**

---

## Installation & Quick Start

### Step 1: Environment Setup

Clone or place the project files in a folder, then initialize the Python virtual environment and download the Playwright Chromium browser binaries:

```bash
# Set up environment
./start.sh setup
```

This will automatically create a `.venv` directory, install all required dependencies (FastAPI, Playwright, Jinja2, etc.), and download Chromium.

### Step 2: Manual Authentication

Google login uses advanced anti-bot measures (device prompt verification, CAPTCHAs, MFA) which are extremely difficult to bypass programmatically. 

To solve this, run the authentication launcher:

```bash
./start.sh auth
```

1. A visible (headful) Chromium browser window will open.
2. Navigate through the Google Login flow and **authenticate with your Google Account**.
3. Complete any MFA/2FA steps.
4. Once you are redirected to the main Gemini chat page and see the text input box (`"Enter a prompt here..."`), return to your terminal.
5. In your terminal, type **`y`** and press **Enter** to verify the input box detection, close the browser, and save the session.

All cookies and session files are safely stored inside the `.playwright_session` folder.

### Step 3: Serve the API

Start the local server:

```bash
./start.sh serve
```

The API server and the administrative dashboard will now be active at **`http://localhost:8000`**.

---

## REST API Reference

### 1. Chat Generation

Sends a text prompt to Gemini, waits for completion, and returns the response.

- **URL**: `/api/chat`
- **Method**: `POST`
- **Headers**:
  - `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "prompt": "Write a 3-word slogan for a bakery.",
    "timeout_sec": 90
  }
  ```
- **Response Schema** (`200 OK`):
  ```json
  {
    "response": "Flour, love, oven.",
    "latency_ms": 7824.50,
    "status": "Success"
  }
  ```
- **Status Codes**:
  - `200 OK`: Request succeeded.
  - `401 Unauthorized`: Session not logged in. Re-run `./start.sh auth`.
  - `503 Service Unavailable`: Browser automation context is initializing or offline.
  - `500 Internal Server Error`: Playwright timed out or failed to parse the page.

---

### 2. Streaming Chat Generation

Streams text generation deltas in real-time as Server-Sent Events (SSE).

- **URL**: `/api/chat/stream`
- **Method**: `POST`
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "prompt": "Tell me a short joke."
  }
  ```
- **Response Format**: `text/event-stream` returning data chunks:
  ```text
  data: Why did the computer...

  data:  go to the doctor?

  data:  Because it had a virus!

  data: [DONE]
  ```

---

### 3. Reset Conversation Thread

Clears the active conversation context in Gemini and starts a fresh chat thread.

- **URL**: `/api/chat/reset`
- **Method**: `POST`
- **Response Schema** (`200 OK`):
  ```json
  {
    "status": "New conversation thread initialized successfully."
  }
  ```

---

### 4. System Status

Returns diagnostic indicators of the active browser context and historical request telemetry.

- **URL**: `/api/status`
- **Method**: `GET`
- **Response Schema** (`200 OK`):
  ```json
  {
    "status": "Connected & Ready",
    "is_connected": true,
    "session_exists": true,
    "headless": true,
    "last_error": null,
    "last_activity": "2026-06-28 14:02:11",
    "total_requests": 14,
    "total_success": 14,
    "avg_latency_ms": 6824.12
  }
  ```

---

### 5. Browser Screenshot

Returns the current page snapshot of the background Chromium browser. Excellent for identifying if the scraper is stuck on a CAPTCHA or pop-up.

- **URL**: `/api/screenshot`
- **Method**: `GET`
- **Response Schema** (`200 OK`):
  ```json
  {
    "screenshot": "iVBORw0KGgoAAAANS..." // Base64 encoded PNG string
  }
  ```

---

### 6. Execution Logs

Returns the 50 most recent API calls processed by the server instance.

- **URL**: `/api/logs`
- **Method**: `GET`
- **Response Schema** (`200 OK`):
  ```json
  [
    {
      "id": 1,
      "timestamp": "2026-06-28 14:05:12",
      "prompt": "Explain gravity simply...",
      "response": "Gravity is the invisible force that pulls objects toward each other...",
      "latency_ms": 7210.15,
      "status": "Success"
    }
  ]
  ```

---

### 7. Restart Browser

Safely terminates the background browser context and launches a new one. Useful if the browser gets stuck or runs out of memory.

- **URL**: `/api/reconnect`
- **Method**: `POST`
- **Response Schema** (`200 OK`):
  ```json
  {
    "status": "Reconnect command initiated."
  }
  ```


---

## Administrative Dashboard

When you open `http://localhost:8000` in your web browser, you will see a dark-themed admin dashboard:

1. **System Health Widgets**: Displays live request counts, successful calls, and average latencies.
2. **Live Browser Viewport**: Displays a screenshot of the headless browser that refreshes every 5 seconds.
3. **Prompt Playground**: An interactive chat window to test prompts and inspect outputs immediately.
4. **Interactive Log Auditor**: Audit timestamps, latencies, status codes, and prompt snippets.
5. **Code Snippets Panel**: Quick integration examples for copy-pasting.

---

## Integration Examples

### Curl (CLI)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the capital of France?"}'
```

### Python (requests)

```python
import requests

url = "http://localhost:8000/api/chat"
payload = {
    "prompt": "Translate 'Hello, world' to Japanese.",
    "timeout_sec": 60
}

response = requests.post(url, json=payload)
if response.status_code == 200:
    data = response.json()
    print("Response:", data["response"])
    print(f"Latency: {data['latency_ms'] / 1000:.2f} seconds")
else:
    print(f"Error {response.status_code}: {response.text}")
```

### Node.js (Fetch)

```javascript
const url = 'http://localhost:8000/api/chat';
const payload = {
  prompt: 'Write a short one-sentence motivational quote.',
  timeout_sec: 90
};

fetch(url, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
})
  .then(res => res.json())
  .then(data => {
    console.log('Response:', data.response);
    console.log(`Latency: ${(data.latency_ms / 1000).toFixed(2)}s`);
  })
  .catch(err => console.error('Request failed:', err));
```

### Bash CLI Client

You can save this script as `ask-gemini.sh` and make it executable:

```bash
#!/bin/bash
PROMPT="$*"
if [ -z "$PROMPT" ]; then
    echo "Usage: $0 <your prompt query>"
    exit 1
fi

RESPONSE=$(curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"$PROMPT\"}")

# Pretty-print using python's json tool (or jq if installed)
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
```

---

## Configuration

You can customize execution parameters by passing environment variables when starting the server:

| Environment Variable | Description | Default |
| :--- | :--- | :--- |
| `PORT` | The port the FastAPI server listens on | `8000` |
| `HOST` | The server bind IP address | `0.0.0.0` |
| `HEADLESS` | Whether to run browser context headlessly | `true` |

For example, to run the server on port `8080` in non-headless mode:

```bash
PORT=8080 HEADLESS=false ./start.sh serve
```

---

## Troubleshooting & Maintenance

### Browser Stuck / Screen Frozen
If you look at the "Live Headless View" on the dashboard and notice the page is frozen, showing an error, or asking for verification:
1. Click **Reconnect Browser** on the top right. This will restart Chromium in the background.
2. If it continues to fail, Google may have invalidated your cookies. Run `./start.sh auth` to re-login manually.

### Request Times Out
If prompts return a `500 Internal Server Error` or time out:
- Check if your internet connection is active.
- Increase the `timeout_sec` field in your JSON request body (default is 90 seconds).
- Check the dashboard screenshot. If Gemini has popped up a "What's new" notification window, it may be blocking the textbox. Run `./start.sh auth` to click through any popup disclosures.

---

## Terms of Service Warning

> [!WARNING]
> **Important Legal Disclaimer:**
> Routing automated requests through a personal Google account via browser emulation violates Google's Terms of Service. This tool is meant for personal development, research, and debugging. Using this server aggressively may lead to your Google Account being flagged, CAPTCHA-challenged, or temporarily restricted. It is highly recommended to run this automation using a dedicated, non-critical throwaway Google Account.
