# API Reference

All endpoints are served by FastAPI on the configured host/port (default `http://0.0.0.0:8000`).

---

## `POST /api/chat`

Send a prompt and receive the full Gemini response as JSON.

### Request body (`application/json`)

| Field | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `prompt` | string | — | min 1 char (required) | The prompt to send to Gemini. |
| `timeout_sec` | int | 90 | 10 – 180 | Max seconds to wait for generation. |

### Example
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain Quantum Computing in one simple sentence.", "timeout_sec": 90}'
```

### Response (`200 OK`)
```json
{
  "response": "… the full generated text …",
  "latency_ms": 5230.4,
  "status": "Success"
}
```

| Field | Type | Description |
|---|---|---|
| `response` | string | The finalized Gemini output. |
| `latency_ms` | float | Total time for the request in milliseconds. |
| `status` | string | Always `"Success"` on `200`. |

### Error responses

| Status | Condition | Detail |
|---|---|---|
| `401` | Server not authenticated | Run `./start.sh auth` first. |
| `401` | Session lost / redirected to login | Handle authentication error. |
| `503` | Browser not connected | Server still booting or crashed. |
| `500` | Generic failure / timeout | Prompt processing failed. |

---

## `POST /api/chat/stream`

Streaming version of `/api/chat` using **Server-Sent Events (SSE)**, media type `text/event-stream`.

Same request body as `/api/chat`.

### Example
```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Tell me a short joke."}'
```

### Response
Each event is `data: <delta>\n\n` where `<delta>` is a growing chunk of text. The stream ends with `data: [DONE]\n\n`. On error you receive `data: [ERROR: <message>]\n\n`.

---

## `POST /api/chat/reset`

Resets the conversation thread (starts a fresh chat in the browser context).

```bash
curl -X POST http://localhost:8000/api/chat/reset
```

### Response (`200 OK`)
```json
{
  "status": "New conversation thread initialized successfully."
}
```

- `503` if the browser is not connected.
- `500` if the reset failed.

---

## `GET /api/status`

Returns system health and usage statistics.

### Response (`200 OK`)
```json
{
  "status": "Connected & Ready",
  "is_connected": true,
  "session_exists": true,
  "headless": true,
  "last_error": null,
  "last_activity": "2026-09-04 12:00:00",
  "total_requests": 10,
  "total_success": 9,
  "avg_latency_ms": 4230.5
}
```

---

## `GET /api/screenshot`

Returns a Base64-encoded PNG of the current browser page (for the live dashboard view).

```bash
curl http://localhost:8000/api/screenshot
```

### Response (`200 OK`)
```json
{ "screenshot": "iVBORw0KGgo…" }
```

An empty string if no browser page is available.

---

## `GET /api/logs`

Returns the last 50 API request log entries (newest first).

### Response (`200 OK`)
```json
[
  {
    "id": 51,
    "timestamp": "2026-09-04 12:01:00",
    "prompt": "Explain Quantum…",
    "response": "Quantum computing leverages…",
    "latency_ms": 5230.4,
    "status": "Success"
  }
]
```

---

## `POST /api/reconnect`

Stops and restarts the browser session (self-healing). Returns immediately; the restart runs in the background.

```bash
curl -X POST http://localhost:8000/api/reconnect
```

### Response (`200 OK`)
```json
{ "status": "Reconnect command initiated." }
```

- `500` if the reconnect trigger failed.

---

## `GET /`

Serves the **admin dashboard** (Jinja2-rendered `templates/index.html`).

```
http://localhost:8000
```
