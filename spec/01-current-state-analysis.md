# 01 — Current State Analysis

This document describes, file by file, what exists today: the prototype in the repository root, the
prototype extension in `extension/`, and the friend's project in `inspo/`. For each piece it says
**what it does**, **how it does it**, and a verdict: **KEEP** (port the idea/code), **REWRITE**
(right idea, wrong implementation), or **DROP**.

Bugs and holes are only mentioned briefly here; the full list with fixes is in
`02-loopholes-and-issues.md` (referenced as `[L-xx]`).

---

## 1. Big picture: there are actually three projects in this repo

| Project | Location | How it talks to the chat site | Sites | Status |
|---|---|---|---|---|
| **A. Playwright server** | `server.py`, `session_manager.py`, `setup_session.py`, `templates/`, `ask-gemini.sh`, `docs/`, `README.md` | Launches its *own* headless Chromium with a saved Google profile and automates it with Playwright + `playwright-stealth`. | Gemini only | **Legacy. Drop.** Violates R3 (the user's real browser must be used), has a separate login flow, and headless automation with stealth patches is the most bot-detectable approach. |
| **B. Firefox extension + bridge** | `extension/`, `bridge_server.py` | A Firefox MV2 extension drives the Gemini tab in the user's real browser; a FastAPI server exposes HTTP and talks to the extension over WebSocket. | Gemini only | **The right architecture, prototype quality.** This is the base we evolve. |
| **C. PromptRelay (inspo)** | `inspo/extension/` | A Chrome MV3 extension. Does *not* expose an API; it helps a human hand context from one chat site to another (inject a "summarise yourself" prompt, capture the answer, paste it into another site). | ChatGPT, Claude, Gemini | **Reference.** Its DOM techniques (multi-tier selectors, visibility checks, paste-event injection, polling for the input) are proven on all three sites and should be ported. |

The direction is: **architecture of B + multi-site DOM techniques of C + everything in this spec
that neither has** (net tap, tab pool, config-driven selectors, health checks, security, streaming,
conversation mapping).

---

## 2. Project B in detail (the base)

### 2.1 Data flow today

```
API client (curl / OpenAI SDK)
   │ POST /v1/chat/completions  or  POST /api/chat
   ▼
bridge_server.py (FastAPI, 127.0.0.1:8000)
   │ ExtensionBridgeHub.dispatch_prompt()  — asyncio.Lock → one request at a time
   │ WebSocket text frame {"id","action":"CHAT","prompt","model","timeout"}
   ▼
extension/background.js (Firefox MV2 persistent background page)
   │ getOrCreateChatTab() → first tab matching *://gemini.google.com/*  (or opens a pinned one)
   │ browser.tabs.sendMessage(tabId, {action:"RUN_PROMPT", ...})
   ▼
extension/content.js (in the Gemini page)
   │ typePrompt(): set innerHTML of contenteditable, dispatch input events, click send / fake Enter
   │ waitForResponse(): poll innerText every 300ms until unchanged for 1.2s and no stop button
   │ Web2APIParser.domToMarkdown() → normalizeToApiResponse()
   ▼
sendResponse({success, data: <OpenAI chat.completion object>})  → background → WebSocket → bridge
   ▼
HTTP 200 JSON to client
```

### 2.2 `bridge_server.py` (291 lines)

* **What:** FastAPI app with a single global `ExtensionBridgeHub`.
  * `@app.websocket("/ws")`: accepts *any* connection, reads one message as a handshake (does not
    validate it), then stores the socket as `hub.active_socket` and loops reading responses,
    resolving the matching `asyncio.Future` by `id`.
  * `dispatch_prompt()`: creates a future, takes `hub.lock`, sends a `CHAT` frame, waits with
    `asyncio.wait_for(future, timeout)`.
  * `reset_thread()`: sends `RESET`, waits 10 s. **Does not take the lock** `[L-07]`.
  * `GET /health`, `GET /status`: status JSON.
  * `GET /v1/models`: a hard-coded list of Gemini model names, some of them obsolete `[L-21]`.
  * `POST /v1/chat/completions`: flattens all messages into one string
    `"[User]: ...\n\n[Assistant]: ...\n\n[Assistant]:"` and dispatches it. Ignores `stream`,
    `temperature`, `max_tokens` `[L-14]`, `[L-15]`.
  * `POST /api/chat`, `POST /api/reset`: simplified endpoints.
* **Verdict: REWRITE.** The hub/future pattern is correct and should be kept conceptually. Everything
  around it (auth, streaming, multi-provider routing, cancellation, connection lifecycle, conversation
  mapping) must be rebuilt per `07-bridge-server-spec.md`.

### 2.3 `extension/manifest.json`

* Firefox **Manifest V2**, persistent background page, content script only on `gemini.google.com`.
* Permissions: `tabs`, `activeTab`, `storage`, Gemini host, localhost http/ws.
* **Verdict: REWRITE** as Manifest V3 with per-browser manifests (Chrome service worker vs Firefox
  background scripts). See `04-extension-spec.md` §2. MV2 is dead on Chrome and deprecated on Firefox
  for new features.

### 2.4 `extension/background.js` (269 lines)

* Holds the WebSocket. Tries `ws://127.0.0.1:8000/ws`, then `ws://127.0.0.1:8765` (nothing listens on
  8765 `[L-24]`), reconnects every 2.5 s.
* `getOrCreateChatTab()`: returns `tabs[0]` of any Gemini tab — possibly the tab the user is typing in
  `[L-09]`. If none, creates a pinned background tab and waits for `status === "complete"` with **no
  timeout** `[L-10]`.
* `handleBridgeRequest()`: `PING`, `CHAT`/`PROMPT`, `RESET`. No cancellation, no streaming, no
  per-tab queue.
* Popup message handlers: `GET_STATUS`, `RUN_POPUP_PROMPT`, `OPEN_CHAT_TAB`, `RECONNECT_BRIDGE`.
* **Verdict: REWRITE**, splitting into `bridge-client.js`, `tab-pool.js`, `job-runner.js`,
  `config-store.js`, `health.js` (see `04-extension-spec.md` §3).

### 2.5 `extension/content.js` (291 lines)

* `SELECTORS.gemini` / `SELECTORS.generic`: inline selector lists `[L-30]`. One of them,
  `'button:has-text("New chat")'`, is Playwright syntax and is not valid CSS; it throws and is silently
  swallowed `[L-27]`. Another, `'a[href*="/app"]'`, matches links to *old* conversations, so "new chat"
  can open a random previous chat `[L-26]`.
* `typePrompt()`: clears the editor with `innerHTML = ""`, inserts one `<p>` containing the whole
  prompt, fires generic `Event("input")`. Newlines in the prompt are flattened `[L-28]`, and the
  editor's internal model (Quill on Gemini) may not register the change.
  Falls back to a synthetic `KeyboardEvent("keydown", Enter)` which most frameworks ignore `[L-29]`.
* `waitForResponse()`: counts message elements before and after; polls `innerText` every 300 ms; done
  when text unchanged for 1.2 s **and** no stop button. If the stop-button selector is wrong and the
  model is "thinking" (empty text), it returns an **empty string immediately** `[L-11]`. On timeout it
  returns whatever partial text exists as a success `[L-12]`.
* **Verdict: REWRITE** into the generic config-driven driver in `04-extension-spec.md` §5.

### 2.6 `extension/parser.js` (332 lines)

* `domToMarkdown()`: clones the message element, removes noise (buttons, icons, citation blocks),
  recursively converts `pre/code/h1-6/p/blockquote/ul/ol/strong/em/table/a/hr` to markdown.
  Handles code language via `language-xxx` class or `data-language`.
* `extractCodeBlocks()`, `extractStructuredJson()`, `extractToolCalls()`, `normalizeToApiResponse()`.
* Unit tests in `test_parser.js` (4 tests, all pass under `node --test`).
* Known defects: nested lists lose indentation; whitespace in text nodes is not normalised;
  math/KaTeX, images, strikethrough are dropped or garbled; ChatGPT's code-block header label leaks
  into output; the JSON extractor is greedy and returns `null` when the text has two JSON objects
  (verified); the tool-call regex fires on ordinary prose such as `call:print(hello)` (verified)
  `[L-31]`–`[L-34]`.
* **Verdict: KEEP the DOM→markdown converter as a starting point** (move it to
  `content/extract/markdown.js`, fix the defects, drive noise selectors from provider config).
  **DROP** `extractStructuredJson` and `extractToolCalls` from the default response path; the
  `extracted` field becomes opt-in (see `07-bridge-server-spec.md` §6.4).

### 2.7 `extension/popup.html|css|js`

* Status badges (bridge connected, tab ready), a test-prompt box, output format switch, copy-curl.
* Hard-coded to Gemini (`popup.js:93`, `popup.js:111`).
* **Verdict: REWRITE** as a provider-aware status/settings popup (see `04-extension-spec.md` §8).

### 2.8 `start.sh`

* Subcommands `setup`, `bridge`, `serve`, `auth`. Uses `uv` if found, else falls back to a path on the
  friend's machine: `/home/suzaykid/.local/bin/uv` (`start.sh:23`) `[L-37]`.
* **Verdict: REWRITE** as a minimal launcher for the new bridge (`uv run web2api-bridge`), or replace
  with `pyproject.toml` scripts entirely.

---

## 3. Project C (inspo / PromptRelay) in detail

### 3.1 What it does for the user

1. Shows a floating "pill" (HUD) on ChatGPT / Claude / Gemini with a rough prompt counter.
2. "Ask for Handover Brief" → pastes a long meta-prompt into the chat input (never auto-submits).
3. "Save Latest Brief" → reads the latest assistant message from the DOM and stores it.
4. "Teleport" → opens another chat site in a new tab and pastes the stored text into its input.

This is exactly the read/write primitive set Web2API needs (**find input → insert text → read latest
answer**), minus auto-submit and completion detection, and it works on three sites.

### 3.2 File-by-file

| File | Technique worth keeping | Verdict |
|---|---|---|
| `manifest.json` | Clean MV3 layout: `storage`, `activeTab`, explicit host permissions, ordered content-script list sharing globals. | **KEEP** the structure (we add more permissions). |
| `content/detector.js` | Hostname → platform id; conversation title heuristics per site. | **KEEP idea**, replace with the provider registry matching `hostPatterns` from config. |
| `content/extractor.js` → `findInputElement()` | **Tiered selector waterfall**: tier 1 = provider-specific selectors, tier 2 = generic ARIA/semantic selectors; every candidate filtered by `_isElementVisible()` (display, visibility, opacity, non-zero size). | **KEEP** the tier + visibility model. Tier 2 is too broad (`textarea`, any `contenteditable`) `[L-40]`; in our version tier 2 must still be constrained to the composer region. |
| `content/extractor.js` → `waitForInputElement()` | Poll up to 30 × 250 ms for the input to mount (survives SPA cold loads, Cloudflare interstitials). | **KEEP**, but implement with a `MutationObserver` + timeout instead of `setTimeout` polling (background-tab timer throttling, `[L-19]`). |
| `content/extractor.js` → `findLatestAssistantMessage()` | Per-site assistant selectors: ChatGPT `[data-message-author-role="assistant"]`; Claude `[data-is-streaming]`, `.font-claude-message`; Gemini `model-response`, `.message-content`. Generic fallback `.markdown, [class*="prose"]`. | **KEEP** as initial selector candidates in provider configs. |
| `content/extractor.js` → `extractLatestResponseText()` | Clone, strip buttons/svg/sr-only/feedback, return `innerText`. | **KEEP the cleaning list**; we produce markdown instead of plain `innerText`. Drop the "if the user has selected >40 chars, return the selection instead" behaviour `[L-41]` — an API must never depend on the user's mouse selection. |
| `content/injector.js` | **The most valuable file.** For `contenteditable` editors (ProseMirror on Claude and ChatGPT, Quill on Gemini) it dispatches a synthetic `ClipboardEvent("paste")` carrying a `DataTransfer` with `text/plain`. The editor's own paste handler then inserts the text through its internal model, preserving newlines as paragraphs. Falls back to `document.execCommand("insertText")`, then to manual `Range.insertNode` + `InputEvent`. For `<textarea>` it uses `execCommand("insertText")` (which React observes) with a value-setter fallback. | **KEEP and port** as `content/injector.js`. Add: clearing existing draft first, verification that the editor now contains the text, and per-provider strategy order from config. |
| `content/tracker.js` | Detects rate-limit banners by keyword ("you've reached", "rate limit", "try again in", …) inside alert-like elements, debounced `MutationObserver`. | **KEEP the idea** for detecting `RATE_LIMITED` errors (`06-bridge-protocol.md` §7). Move keywords into provider config. The prompt counter itself is not needed. |
| `content/ui.js` | Closed shadow-DOM HUD with inline styles (CSP-proof). | **DROP** for worker tabs. Injecting visible DOM into the provider's page is detectable by the site `[L-42]`. Status belongs in the popup and the extension badge. |
| `background/service-worker.js` | Single-use "teleport" payload in `chrome.storage.session` with 60 s TTL, claimed by the new tab on load. | **KEEP the pattern** for "open a fresh tab and hand it a job once it's ready". Key it by `jobId`/`tabId`, not by platform `[L-43]`. |
| `utils/storage.js` | Promise wrappers over `chrome.storage.local`, default settings merge. | **KEEP the pattern** (`config-store.js`). Note the read-modify-write race `[L-44]`. |
| `popup/*` | Tabbed popup (overview / vault / settings), all untrusted text set via `textContent`. | **KEEP the XSS discipline**; UI itself is not reused. |
| `assets/handover-prompt.txt` | The handover meta-prompt. | **DROP** (not relevant to API use). Could become a future "export conversation" feature. |

### 3.3 Why the inspo "works on all sites" and the prototype doesn't

1. It tries **several selectors per site, then generic ones**, and filters by **visibility** — so a
   hidden duplicate editor or a removed class does not break it.
2. It inserts text through the **editor's own paste pipeline** rather than overwriting `innerHTML`,
   so ProseMirror/Quill/React all register the change.
3. It **waits for the input to exist** before acting.
4. It never auto-submits and never waits for completion — which conveniently avoids the two hardest
   problems (submit and done-detection). Web2API must solve both; see `04-extension-spec.md` §5.4–5.6.

---

## 4. Project A (Playwright server) — why it is dropped

Kept here only so nobody resurrects it by accident.

* Requires a separate login in a separate Chromium profile (`setup_session.py`) — violates R3.
* Headless Chromium + `playwright-stealth` + `--disable-blink-features=AutomationControlled` is the
  textbook bot fingerprint; Google, OpenAI and Anthropic all run bot detection.
* Binds `0.0.0.0` by default with no auth (`server.py:26`) — anyone on the LAN can use the account and
  view live screenshots of it via `/api/screenshot` `[L-03]`.
* Its streaming endpoint emits multi-line text in single `data:` lines, which breaks SSE framing
  (`server.py:248`) `[L-17]`.

**Action (Phase 0 of the plan):** move `server.py`, `session_manager.py`, `setup_session.py`,
`templates/`, `ask-gemini.sh`, the current `README.md` and `docs/` into `archive/playwright-gemini/`
with a short `archive/README.md` explaining why. Do not delete — git history is enough, but the owner
may want to look at it.

---

## 5. What is reusable, as a checklist

- [x] Bridge hub pattern: request id → `asyncio.Future`, resolved by WebSocket replies.
- [x] Extension-initiated WebSocket to localhost (browsers cannot listen on ports; the extension must
      dial out).
- [x] `domToMarkdown` converter skeleton + its tests.
- [x] Inspo's paste-event injector.
- [x] Inspo's tiered, visibility-filtered selector waterfall.
- [x] Inspo's `waitForInputElement` concept.
- [x] Inspo's per-site initial selector candidates.
- [x] Inspo's rate-limit keyword detection.
- [x] Inspo's single-use session-storage handoff for freshly opened tabs.
- [ ] Everything else is rebuilt.
