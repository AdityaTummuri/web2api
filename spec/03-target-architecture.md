# 03 — Target Architecture

This document defines **what we are building**: the components, how a request flows through them,
the key design decisions (with reasons and rejected alternatives), and the final directory layout.

---

## 1. System overview

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│  API CLIENTS  (curl, OpenAI Python/JS SDK, LangChain, Cursor/Continue, later: MCP server)  │
└──────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                           │ HTTP  (Bearer sk-w2a-… API key)
                                           │ POST /v1/chat/completions   (JSON or SSE stream)
                                           │ GET  /v1/models,  /web2api/* admin
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│  BRIDGE  (Python, aiohttp only, 127.0.0.1:8787)                    bridge/web2api_bridge/   │
│                                                                                            │
│  auth & host check → OpenAI adapter → Conversation mapper → Router → ExtensionHub          │
│                                          (prefix fingerprints)   (pick extension      │    │
│                                                                   + provider)         │    │
│  Job registry (jobId → asyncio.Queue of events) ◄─────────── WebSocket frames ────────┘    │
└──────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                           │ WebSocket ws://127.0.0.1:8787/ws/extension
                                           │ (Origin check + pairing token; JSON frames, protocol v1)
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│  BROWSER EXTENSION — background (Chrome: service worker / Firefox: event page)             │
│                                                                                            │
│  bridge-client ─► job-runner ─► tab-pool (per provider: worker tabs, busy/idle, queue)     │
│        ▲              │             │                                                      │
│        │              │        config-store (provider JSON + overrides)   health.js        │
│        │              ▼             │                                                      │
│        │        runtime.Port per worker tab                                                │
└────────┼──────────────┬────────────────────────────────────────────────────────────────────┘
         │              │
         │              ▼
┌────────┴───────────────────────────────────────────────────────────────────────────────────┐
│  WORKER TAB (e.g. https://claude.ai/new) — user's real, logged-in session                  │
│                                                                                            │
│  ISOLATED world content scripts:                     MAIN world script (document_start):   │
│   bootstrap → provider registry → driver             net-tap: wraps fetch/XHR/EventSource, │
│     • find composer (tiered + scored)                 recognises the provider's streaming   │
│     • inject text (paste → execCommand → range)       endpoint, parses chunks with the      │
│     • submit + verify                                 provider's stream parser, posts       │
│     • observe (MutationObserver + net-tap events)     deltas via window.postMessage ────┐   │
│     • detect completion (signals)                                                    │   │
│     • extract (net-tap markdown, else DOM→markdown) ◄────────────────────────────────┘   │
│     • detect states (login, captcha, rate limit)                                          │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Components and responsibilities

| Component | Lives in | Responsibility | Must NOT do |
|---|---|---|---|
| **Bridge HTTP layer** | `bridge/web2api_bridge/api/` | Auth, request validation, OpenAI-compatible request/response shapes, SSE formatting, error schema. | Know anything about DOM or providers' internals. |
| **Conversation mapper** | `bridge/.../conversations.py` | Decide "continue thread X" vs "new chat"; build the prompt text to send. | Talk to the extension directly. |
| **Router** | `bridge/.../router.py` | Resolve `model` → provider + variant; choose a connected extension that offers it. | Queue per tab (the extension owns tab scheduling). |
| **Extension hub** | `bridge/.../hub.py` | Manage WebSocket connections, send jobs, route incoming events to the right job's queue, cancellation, heartbeats. | Parse HTML or markdown. |
| **Bridge client** | `extension/src/background/bridge-client.js` | Dial the bridge, authenticate, reconnect with backoff, keepalive, (de)serialise frames. | Make scheduling decisions. |
| **Job runner** | `extension/src/background/job-runner.js` | Accept `JOB_START`, enqueue on the tab pool, relay events from the tab Port to the bridge, enforce timeouts, handle `JOB_CANCEL`. | Touch the DOM. |
| **Tab pool** | `extension/src/background/tab-pool.js` | Own worker tabs per provider: open, claim, track busy/idle, health, recycle; one job per tab; per-provider min delay. | Use a tab the user is actively using unless explicitly assigned. |
| **Config store** | `extension/src/background/config-store.js` | Load bundled provider configs, merge validated overrides, serve the effective config to tabs, persist overrides. | Accept code, only data. |
| **Health** | `extension/src/background/health.js` | Run canary checks, collect failure reports and DOM snapshots, expose them to bridge/popup. | Send anything off-machine. |
| **Driver** | `extension/src/content/driver.js` | Execute one job inside the page using the provider config. | Decide which tab to use. |
| **Net tap** | `extension/src/main-world/net-tap.js` + `extension/src/providers/parsers/*.js` | Observe the provider's own streaming response; emit normalised deltas. | Modify requests or responses. Ever. |
| **Popup** | `extension/src/popup/` | Status, pairing, per-provider tab management, health view, debug toggles, test prompt (via the job queue). | Hold state of its own (it is destroyed when closed). |

---

## 3. Key design decisions

Each decision: **Decision → Why → Rejected alternatives.**

### D1. Drive the user's real browser through an extension (not Playwright, not cookies)

* **Why:** R3 (browser already open, already logged in). Real browser fingerprint, real cookies, real
  extensions — far less bot-like than headless Chromium. No credentials leave the browser.
* **Rejected:** Playwright/Puppeteer (project A — separate login, detectable); copying cookies into a
  Python HTTP client calling private endpoints (breaks constantly on anti-bot tokens like ChatGPT's
  proof-of-work/sentinel headers and Cloudflare; also exfiltrates session secrets); Chrome DevTools
  Protocol via `chrome.debugger` (shows a "being debugged" banner on every tab, needs extra
  permission, and is itself a fingerprint).

### D2. The extension dials out to a local bridge over WebSocket

* **Why:** Browser extensions cannot listen on TCP ports. A WebSocket from the background context to
  `127.0.0.1` is simple, bidirectional, supports streaming, and works on Chrome and Firefox.
* **Rejected:** Native Messaging (requires installing a native host manifest into OS-specific
  locations per browser; awkward for development; restarts the host process per connection — reserve
  as a possible later transport); HTTP long-polling from the extension (more latency, more code).

### D3. One codebase, Manifest V3, two manifests (Chrome + Firefox)

* **Why:** MV2 is gone from Chrome. Both Chrome and Firefox support MV3, but differ: Chrome requires
  `background.service_worker`; Firefox uses `background.scripts` (event page). A tiny build script
  merges `manifests/base.json` with `manifests/chrome.json` or `manifests/firefox.json` and copies
  `src/` into `dist/chrome/` or `dist/firefox/`. No bundler.
* **Rejected:** a single manifest containing both keys (works on recent browser versions but behaviour
  across versions is a footgun; explicit is better); keeping Firefox MV2 (no future).
* **Consequence:** Chrome service workers are terminated after ~30 s idle. An *active* WebSocket that
  exchanges a message at least every ~20–25 s keeps it alive (Chrome 116+). The bridge client sends
  `PING` every 20 s. On restart the worker must reconstruct state from `chrome.storage.session` —
  design all background state to be reloadable (`04-extension-spec.md` §3.2).

### D4. Selectors and site knowledge are DATA (provider config JSON), with a validated override layer

* **Why:** R4. The future maintainer (and a human) can fix a broken site by pushing a JSON override —
  no code change, no extension reload. Also makes adding a new provider mostly a data task.
* **Rejected:** per-provider JS classes with hard-coded selectors (the current prototype and inspo).
* **Rule:** provider-specific *code* is allowed only for (a) network stream parsers and (b) rare
  input quirks, and lives in `src/providers/parsers/<provider>.js` / `src/providers/quirks/<provider>.js`,
  referenced from the config by name.

### D5. Two extraction paths: Net tap first, DOM fallback

* **Why:** The site's own stream contains the **exact markdown** and true token-by-token deltas, is
  unaffected by background-tab rendering throttling, and changes far less often than CSS classes. But
  stream formats are proprietary and do change, and some sites are hard to parse (Gemini) — so DOM
  extraction remains the universal fallback and the cross-check.
* **How they combine:** The driver always runs DOM observation. If the net tap produced a complete
  stream for this job, its text is the answer; otherwise the DOM-extracted markdown is. In debug mode
  both are kept and a similarity score is logged (helps detect parser drift).
* **Rejected:** DOM only (fragile fidelity, throttling); net tap only (no universal fallback).

### D6. Worker tabs are explicit; never hijack the user's chat

* **Why:** L-09. The API must not type into the conversation the user is reading.
* **How:** The tab pool opens its own worker tabs (preferably in a dedicated "Web2API" window, see
  D8) or uses tabs the user explicitly assigned via the popup. Each worker tab is tracked by id in
  `storage.session`.

### D7. One job per tab; parallelism through more tabs

* **Why:** A chat page has one composer. Concurrent jobs in one tab corrupt each other (L-46, L-07).
* **How:** Per-provider pool size (default 1, max configurable, e.g. 3). Jobs beyond capacity wait in
  the extension's per-provider FIFO queue; the bridge enforces a queue timeout.

### D8. Optional dedicated worker window to fight background throttling

* **Why:** L-19. A tab that is the active tab of a normal, non-minimized window is not "hidden", so it
  isn't throttled as aggressively and renders normally.
* **How:** Setting `workerWindowMode: "dedicated" | "background-tabs"` (default `"dedicated"`). In
  dedicated mode, the pool creates one small normal window (`chrome.windows.create({focused:false,
  state:"normal", width: 900, height: 900})`) and each worker tab becomes the active tab of its own
  window when running a job (or one window per worker). Must be validated by the Phase 1 spike; if net
  tap works for a provider in a hidden tab, background-tabs mode is acceptable for it.

### D9. Conversation mapping in the bridge, not the extension

* **Why:** OpenAI's API is stateless (client resends history); web chats are stateful. The mapping is
  pure logic over message lists and belongs in Python where it is easy to test. The extension just
  receives "run this text in thread URL X, or in a new chat" and reports the resulting thread URL.
* **See:** `07-bridge-server-spec.md` §5.

### D10. Push-based job events over a Port

* **Why:** L-20. Streaming requires incremental events; Ports detect tab death immediately.

### D11. Security by default

* **Why:** L-01…L-04. The bridge binds loopback only, requires a bearer token for HTTP, requires
  Origin + pairing token for the extension WebSocket, validates `Host`, has no CORS. See `08-security.md`.

### D12. Python bridge with a single dependency (aiohttp), shipped from source and as a binary

* **Why:** The owner prefers Python and `uv`. `aiohttp` provides HTTP server, WebSocket server and SSE
  streaming in one library, replacing FastAPI + uvicorn + starlette + pydantic (≈ 10 packages) with
  one. Validation is hand-written. The same code is frozen into a standalone binary for users who
  don't want Python (`12` §3). Also, the
  future maintainer/MCP tooling is natural in Python.

---

## 4. End-to-end lifecycle of one request (non-streaming and streaming)

```
Client                Bridge                         Extension BG              Worker tab (content + main)
  │ POST /v1/chat/      │                                 │                          │
  │ completions ───────►│ 1 auth, Host check              │                          │
  │                     │ 2 validate (hand-written)       │                          │
  │                     │ 3 router: model → provider      │                          │
  │                     │ 4 conv mapper: continue/new,    │                          │
  │                     │   build promptText              │                          │
  │                     │ 5 create Job(jobId), queue      │                          │
  │                     │── JOB_START ───────────────────►│ 6 enqueue on pool         │
  │                     │◄─ JOB_ACCEPTED(queuePos) ───────│                          │
  │                     │                                 │ 7 acquire idle tab,       │
  │                     │                                 │   navigate if needed      │
  │                     │                                 │── port: run(job) ───────►│ 8 check states (login…)
  │                     │◄─ JOB_PROGRESS(phase) ──────────│◄─ progress ──────────────│ 9 inject + submit + verify
  │                     │                                 │                          │10 net tap + DOM observe
  │◄── SSE chunk ───────│◄─ JOB_DELTA(seq, text) ─────────│◄─ delta ─────────────────│   (repeat)
  │                     │                                 │                          │11 completion signals
  │                     │◄─ JOB_DONE(text, threadUrl, ───│◄─ done ──────────────────│12 final extract
  │◄── final chunk/JSON │      finishReason, meta)        │ 13 release tab, min delay │
  │                     │ 14 conv mapper records          │                          │
  │                     │    (fingerprint → threadUrl)    │                          │
```

Failure paths:
* Client disconnects / bridge deadline → bridge sends `JOB_CANCEL` → driver clicks stop → `JOB_CANCELLED`.
* Tab closed / navigated → Port disconnect → job runner emits `JOB_ERROR(TAB_LOST)`.
* Login page / captcha / rate-limit banner → `JOB_ERROR(LOGIN_REQUIRED | CAPTCHA_REQUIRED | RATE_LIMITED)`
  with a health report + optional DOM snapshot.
* Selector not found → `JOB_ERROR(SELECTOR_NOT_FOUND, detail: {key: "composer.input"})` + snapshot. This is the
  maintainer's trigger.

---

## 5. Final directory layout

```
web2api/
├── README.md                         # New top-level README (written in Phase 6)
├── spec/                             # This specification
├── inspo/                            # Friend's PromptRelay (reference only)
├── archive/
│   └── playwright-gemini/            # Legacy project A (moved in Phase 0)
├── extension/
│   ├── package.json                  # dev deps only: jsdom (tests). scripts: build, test, lint
│   ├── manifests/
│   │   ├── base.json                 # shared MV3 fields
│   │   ├── chrome.json               # background.service_worker, minimum_chrome_version
│   │   └── firefox.json              # background.scripts, browser_specific_settings.gecko.id
│   ├── scripts/
│   │   └── build.mjs                 # merge manifest + copy src → dist/<browser>/
│   ├── src/
│   │   ├── shared/
│   │   │   ├── protocol.js           # message type constants, error codes, PROTOCOL_VERSION (UMD-style)
│   │   │   ├── logger.js             # levelled logger, content redaction
│   │   │   └── util.js               # ids, sleep with deadline, normaliseText, hashing
│   │   ├── background/
│   │   │   ├── main.js               # entry; wires everything; onInstalled/onStartup
│   │   │   ├── bridge-client.js
│   │   │   ├── job-runner.js
│   │   │   ├── tab-pool.js
│   │   │   ├── config-store.js
│   │   │   ├── health.js
│   │   │   └── settings.js           # user settings (bridge URL, token, pool sizes, modes)
│   │   ├── content/
│   │   │   ├── provider-hosts.js     # GENERATED by build: host regex → provider id
│   │   │   ├── bootstrap.js          # detects provider, opens Port, announces CONTENT_READY
│   │   │   ├── dom.js                # query helpers: tiered resolve, visibility, scoring, waitFor (MutationObserver)
│   │   │   ├── injector.js           # adapted from inspo injector
│   │   │   ├── submitter.js
│   │   │   ├── observer.js           # turn identification, DOM delta diff
│   │   │   ├── completion.js         # completion-signal engine
│   │   │   ├── states.js             # login/captcha/rate-limit/error detection
│   │   │   ├── extract/markdown.js   # DOM → markdown (evolved from extension/parser.js)
│   │   │   ├── nettap-relay.js       # receives postMessage events from MAIN world
│   │   │   ├── snapshot.js           # sanitised DOM snapshot for health reports
│   │   │   └── driver.js             # orchestrates one job
│   │   ├── main-world/
│   │   │   └── net-tap.js            # fetch/XHR/EventSource wrapper (MAIN world, document_start)
│   │   ├── providers/
│   │   │   ├── schema.json           # JSON Schema for provider configs
│   │   │   ├── index.json            # list of provider ids shipped
│   │   │   ├── chatgpt.json
│   │   │   ├── claude.json
│   │   │   ├── gemini.json
│   │   │   ├── deepseek.json
│   │   │   ├── grok.json
│   │   │   ├── perplexity.json
│   │   │   ├── mistral.json
│   │   │   ├── qwen.json
│   │   │   ├── kimi.json
│   │   │   ├── copilot.json
│   │   │   ├── generated/            # GENERATED by build: <id>.nettap.js (endpoint patterns for MAIN world)
│   │   │   └── parsers/              # stream parsers (loaded in MAIN world), one file per provider
│   │   │       ├── sse.js            # generic SSE line splitter shared by parsers
│   │   │       ├── chatgpt.js
│   │   │       ├── claude.js
│   │   │       └── ...
│   │   └── popup/
│   │       ├── popup.html
│   │       ├── popup.css
│   │       └── popup.js
│   ├── tests/
│   │   ├── unit/                     # node:test — markdown, diff, protocol, config validation, parsers
│   │   ├── fixtures/                 # captured DOM snapshots + stream samples per provider
│   │   └── dom/                      # jsdom tests running driver pieces against fixtures
│   └── dist/                         # build output (git-ignored)
└── bridge/
    ├── pyproject.toml                # name web2api-bridge; scripts: web2api-bridge = web2api_bridge.cli:main
    ├── uv.lock
    ├── web2api_bridge/
    │   ├── __init__.py
    │   ├── cli.py                    # arg parsing, token generation/printing, event loop + aiohttp runner
    │   ├── config.py                 # settings (env + config file)
    │   ├── app.py                    # aiohttp app factory, middleware, error mapper
    │   ├── security.py               # host check, origin/pairing-token check for WS, auth middleware
    │   ├── keys.py                   # API key store: create/verify/revoke/rotate, scopes, rate limits (13)
    │   ├── paths.py                  # per-OS config/state dirs (stdlib only)
    │   ├── service.py                # service install/uninstall (systemd/launchd/schtasks) (12 §4)
    │   ├── doctor.py                 # doctor + support-bundle (12 §6)
    │   ├── protocol.py               # message constants + frame builders/validators mirroring extension/src/shared/protocol.js
    │   ├── hub.py                    # connections, jobs, event routing, cancel, heartbeat
    │   ├── router.py                 # model id → provider/variant → connection
    │   ├── conversations.py          # fingerprints, mapping store, prompt building
    │   ├── openai_compat/
    │   │   ├── schemas.py            # request parsing/validation (hand-written dataclasses) + response builders
    │   │   ├── chat.py               # /v1/chat/completions (json + SSE)
    │   │   └── models.py             # /v1/models
    │   ├── admin.py                  # /web2api/status, /web2api/health, /web2api/providers, overrides
    │   └── errors.py                 # error codes → HTTP status + OpenAI error body
    └── tests/
        ├── test_conversations.py
        ├── test_protocol.py
        ├── test_security.py
        ├── test_chat_endpoint.py     # uses a fake extension WebSocket client
        └── fake_extension.py         # test double speaking protocol v1
```

Root-level `bridge_server.py`, `start.sh`, `requirements.txt` are removed at the end of Phase 3 once the
new bridge reaches parity (keep `start.sh` only if it becomes a thin wrapper around `uv run`).

---

## 6. Non-goals for v1

* No MCP server (Phase "later"; see `11-future-maintainer-and-mcp.md`), but the admin API must expose
  everything an MCP server would need.
* No remote/LAN access.
* No image/file inputs or image outputs (return `UNSUPPORTED_CONTENT`).
* No tool-calling emulation in v1 core (designed in `07` §8, implemented in a later phase).
* No Safari, no mobile.
* No automatic account switching or rate-limit evasion beyond a polite minimum delay.
