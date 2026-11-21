# Web2API Pro — Firefox & Zen Browser Extension

Transforms your real, authenticated Firefox / Zen browser chat sessions (**Gemini**, **ChatGPT**, **Claude**) into a pro-grade, OpenAI-compatible local API. Bypasses cloud API fees, rate limits, and Cloudflare/bot challenges by automating the native browser tab you are already logged into.

---

## Key Features

- **Zen Browser & Firefox Native**: Optimized for Zen Browser (Mozilla Gecko engine) and standard Firefox (ESR 109+, Firefox 128+).
- **Multi-Provider Support**: Seamlessly bridges **Google Gemini**, **OpenAI ChatGPT**, and **Anthropic Claude**.
- **Zero Bot Detection**: Uses your genuine browser session, authenticated cookies, and real canvas/WebGL fingerprints.
- **Auto-Injection & Healing**: Detects existing open tabs and dynamically injects content automation scripts without requiring tab reloads.
- **Deep Code-Block & Markdown Parser**: Extracts language-tagged code snippets, cleans UI artifacts, preserves indentation, and normalizes output into OpenAI chat completion structures.
- **OpenAI-Compatible Endpoint**: Serves `POST /v1/chat/completions` directly compatible with Cursor, Continue, LangChain, LlamaIndex, AutoGen, and `curl`.
- **Live Pro Console Popup**: Built-in developer popup with bridge connection indicator, provider switcher, prompt playground, latency metrics, and cURL generator.

---

## Directory Structure

```
extension/
├── manifest.json       # WebExtension Manifest (Firefox / Zen compliant)
├── parser.js           # AST / DOM to Markdown & Structured Extractor
├── content.js          # Direct DOM injector & stream observer (Gemini, ChatGPT, Claude)
├── background.js       # Background WebSocket bridge client & tab router
├── popup.html          # Pro Developer Console popup
├── popup.css           # Glassmorphic dark UI styling
├── popup.js            # Controller for tester, tab switching, and bridge status
├── build.js            # Automated packager (generates web2api-firefox.xpi)
├── test_parser.js      # Unit tests for code block and tool extraction
├── web2api-firefox.xpi # Packaged add-on ready to install in Zen / Firefox
└── icons/              # Extension icons (48px, 96px)
```

---

## 🚀 Quick Setup in Zen Browser / Firefox

### Step 1: Install Extension in Zen / Firefox
1. In Zen Browser, navigate to:
   ```
   about:debugging#/runtime/this-firefox
   ```
2. Click **"Load Temporary Add-on..."**.
3. Select either:
   - The manifest file: `/home/suzaykid/Projects/web2api/extension/manifest.json`
   - Or the pre-packaged XPI: `/home/suzaykid/Projects/web2api/extension/web2api-firefox.xpi`
4. The **Web2API Pro** icon (⚡) will appear in your Zen toolbar.

### Step 2: Open Chat Tabs in Zen
Open and sign into your desired AI chat sites in Zen:
- **Gemini**: [gemini.google.com/app](https://gemini.google.com/app)
- **ChatGPT**: [chatgpt.com](https://chatgpt.com/)
- **Claude**: [claude.ai/new](https://claude.ai/new)

*(You can keep these tabs pinned or running in the background).*

### Step 3: Launch the Local Bridge Server
From the repository root:
```bash
./start.sh bridge
```
*Or using `uv` directly:*
```bash
uv run python3 bridge_server.py
```

The bridge server will start at `http://127.0.0.1:8000` with WebSocket endpoint `ws://127.0.0.1:8000/ws`. The extension connects automatically!

---

## 📡 API Usage Examples

### 1. Standard OpenAI Chat Completion (`/v1/chat/completions`)

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

### 2. Simple Direct Chat Endpoint (`/api/chat`)

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

## 🛠 Rebuilding & Packaging

To run unit tests:
```bash
npm test
```

To re-package the `.xpi`:
```bash
npm run build
```
This updates both `web2api-firefox.xpi` and `dist/firefox/`.
