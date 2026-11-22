# Web2API Independent Server Deployment Guide

Web2API is designed as a **completely self-contained, independent microservice**. It runs in isolation without depending on or coupling with external local projects. Once running on your local machine, VPS, cloud instance, or Docker container, any client (Android, Python, Flutter, React, iOS, cURL) can communicate with it over standard HTTP/REST, Server-Sent Events (SSE), or WebSockets.

---

## 1. Quick Start on Any Server

### Option A: Direct Python Execution
```bash
# Clone the repository
git clone https://github.com/seeramsujay/web2api.git
cd web2api

# Install dependencies
pip install -r requirements.txt

# Configure environment (optional API key)
export HOST=0.0.0.0
export PORT=8000
export WEB2API_API_KEY="sk-w2a-live-$(openssl rand -hex 24)"   # required when HOST is not 127.0.0.1

# Run standalone bridge server
python3 bridge_server.py
```

### Option B: Docker / Docker Compose
```bash
# Copy and edit environment settings
cp .env.example .env

# Build and start container in detached mode
docker compose up -d

# Verify health status
curl http://localhost:8000/health
```

---

## 2. Server Architecture & Independence

```
   ┌──────────────────────────────────────────────────────────────┐
   │                  Your Remote Server / VPS                    │
   │                                                              │
   │   ┌──────────────────────────────────────────────────────┐   │
   │   │         Web2API Standalone Bridge (Port 8000)        │   │
   │   │  - REST API (/v1/chat/completions, /api/chat)        │   │
   │   │  - Streaming SSE Chunk Generator                     │   │
   │   │  - WebSocket Hub (/ws, /ws/extension)                │   │
   │   │  - Optional Bearer Token Auth & CORS Protection      │   │
   │   └──────────────────────▲───────────────────────────────┘   │
   └──────────────────────────┼───────────────────────────────────┘
                              │
          ┌───────────────────┴───────────────────┐
          │ HTTP / REST / SSE / WebSocket Tunnel  │
          ▼                                       ▼
┌───────────────────────────┐           ┌───────────────────────────┐
│  Client Applications      │           │  Authenticated Browser    │
│  - Android App (Kotlin)   │           │  (Chrome / Firefox / Zen) │
│  - Python Library         │           │  Running Web2API          │
│  - Flutter Mobile / Web   │           │  Extension                │
│  - React / Next.js / Node │           │  (Logged into Gemini /    │
│  - LangChain / Cursor     │           │   ChatGPT / Claude)       │
└───────────────────────────┘           └───────────────────────────┘
```

### Key Isolation Features:
* **Decoupled**: Zero dependencies on host OS filesystem beyond standard Python libraries.
* **Network-Accessible on request**: Binds to `127.0.0.1` by default; set `HOST=0.0.0.0` to accept external connections. The server refuses a non-loopback bind unless an API key is configured.
* **Authentication Safeguards**: Once any key exists (`WEB2API_API_KEY` or `api.txt`), every request needs `Authorization: Bearer <token>` and the extension WebSocket needs `?token=<key>`.
* **CORS Configurable**: Control permitted web domains via `CORS_ORIGINS`.

---

## 3. Remote Browser Extension Pairing

When running Web2API on a remote server (e.g., `https://api.yourdomain.com` or `http://192.168.1.50:8000`):

1. Open your browser with the **Web2API Extension** installed.
2. In the extension popup or options, change the Bridge URL to your server's address:
   * Non-SSL: `ws://192.168.1.50:8000/ws`
   * SSL / Reverse Proxy: `wss://api.yourdomain.com/ws`
   * With Token: `wss://api.yourdomain.com/ws?token=sk-w2a-secret-key-12345`
3. The server dashboard (`http://your-server:8000/status`) will immediately show `extension_connected: true`.
4. Any connected client can now make queries that execute through your authenticated browser session!

---

## 4. Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` / `/status` | Server health check and extension connection state |
| `GET` | `/v1/models` | Lists available AI models (`gemini-pro`, `gpt-4o`, `claude-3-5-sonnet`) |
| `POST` | `/v1/chat/completions` | Standard OpenAI chat completions (supports JSON and SSE streaming) |
| `POST` | `/api/chat` | Simplified direct prompt endpoint |
| `POST` | `/api/reset` | Resets the conversation tab in browser |
| `WS` | `/ws` / `/ws/extension` | WebSocket bridge for browser extension connection |
| `GET` | `/docs` | Interactive Swagger API UI |
| `GET` | `/openapi.json` | OpenAPI 3.1 specification schema |

---

## 5. Security Best Practices

1. **Always Set an API Key on Public Servers**:
   ```bash
   export WEB2API_API_KEY="sk-w2a-prod-$(openssl rand -hex 16)"
   ```
2. **Reverse Proxy with TLS (Nginx / Caddy / Cloudflare)**:
   Ensure WebSocket upgrades are forwarded:
   ```nginx
   location /ws {
       proxy_pass http://127.0.0.1:8000/ws;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "Upgrade";
       proxy_set_header Host $host;
   }
   ```
3. **Firewall Rules**:
   Allow access to the port only from trusted IP ranges or VPN if not using public API key authentication.
