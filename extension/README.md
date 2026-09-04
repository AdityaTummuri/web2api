# Web2API Pro — Firefox Extension & Local API Bridge

Transforms your real, authenticated Firefox browser chat session (Google Gemini) into a pro-grade, OpenAI-compatible REST API. Bypasses cloud API fees, rate limits, and headless bot detection by leveraging your native browser session.

---

## Key Features

- **Zero Bot Detection**: Runs in your daily Firefox profile with genuine cookies, headers, and canvas fingerprints.
- **Deep Code-Block Parsing**: Extracts code snippets with language tags (`python`, `rust`, `javascript`, etc.), cleans DOM artifacts, preserves indentation, and produces pristine Markdown.
- **Structured Output & Tool Calling**: Includes regex and JSON schema extractors to parse tool calls (`<tool_call>...`, `call:fn()`) and structured JSON outputs directly from the chat stream.
- **OpenAI-Compatible Endpoint**: Serves `POST /v1/chat/completions` directly compatible with LangChain, LlamaIndex, Cursor, AutoGen, and curl.
- **Live Developer Console**: Firefox popup with connection badges, prompt tester, latency timer, and multi-format viewer (OpenAI JSON, Code Only, Raw Markdown).

---

## Directory Structure

```
extension/
├── manifest.json       # WebExtension Manifest (Firefox MV2/MV3)
├── parser.js           # AST / DOM to Markdown & Structured Extractor
├── content.js          # Direct DOM injector & stream observer for Gemini
├── background.js       # Background service & WebSocket bridge client
├── popup.html          # Pro Developer Console popup
├── popup.css           # Glassmorphic dark UI styling
├── popup.js            # Controller for tester, status, and clipboard actions
└── icons/              # Extension icons (48px, 96px)
```

---

## 🚀 Quick Setup & Installation

### Step 1: Install Extension in Firefox
1. Open Firefox and type `about:debugging#/runtime/this-firefox` into the address bar.
2. Click **"Load Temporary Add-on..."**.
3. Select `manifest.json` located inside this directory:
   `/mnt/shared/web2api/extension/manifest.json`
4. The **Web2API Pro** icon (⚡) will appear in your Firefox toolbar.

### Step 2: Open Gemini in Firefox
1. Navigate to [gemini.google.com/app](https://gemini.google.com/app).
2. Ensure you are signed into your Google account. (You can keep this tab pinned or open in the background).

### Step 3: Launch the Local Bridge Server
From the project root:
```bash
./start.sh bridge
```
*Or using `uv` directly:*
```bash
uv run python3 bridge_server.py
```

The bridge server will start at `http://127.0.0.1:8000` with WebSocket endpoint `ws://127.0.0.1:8000/ws`. The Firefox extension connects automatically!

---

## 📡 API Usage Examples

### 1. OpenAI-Compatible Chat Completion (`/v1/chat/completions`)

```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-pro",
    "messages": [
      {"role": "user", "content": "Write an asynchronous LRU cache in Python with thread-safety."}
    ]
  }'
```

**Response Format:**
```json
{
  "id": "chatcmpl-4f18a287",
  "object": "chat.completion",
  "created": 1756981240,
  "model": "gemini-pro",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Here is an asynchronous, thread-safe LRU Cache in Python...\n\n```python\nimport asyncio\nfrom collections import OrderedDict..."
      },
      "finish_reason": "stop"
    }
  ],
  "extracted": {
    "code_blocks": [
      {
        "index": 0,
        "language": "python",
        "code": "import asyncio\nfrom collections import OrderedDict\n..."
      }
    ],
    "structured_data": null,
    "tool_calls": null
  },
  "latency_seconds": 3.8
}
```

### 2. Simple Prompt Endpoint (`/api/chat`)

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize the differences between TCP and UDP in a markdown table."}'
```

### 3. Reset Thread (`/api/reset`)

```bash
curl -X POST http://127.0.0.1:8000/api/reset
```

---

## 🧪 Browser Popup Testing
1. Click the **Web2API Pro** icon (⚡) in Firefox.
2. Confirm the badges display:
   - `Bridge: Connected` (Green)
   - `Tab: Ready` (Green)
3. Type a prompt in the textarea and click **Run Prompt**.
4. Switch views between:
   - **OpenAI JSON**: Complete payload with usage and token estimation.
   - **Code Blocks Only**: Isolated code snippets ready for copy/paste.
   - **Raw Markdown**: Clean markdown representation.
