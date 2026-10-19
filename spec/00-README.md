# Web2API Specification Set — Start Here

> **Audience:** the engineer (human or AI model, e.g. Claude Sonnet) who will write the code.
> **Author intent:** these documents are the *single source of truth* for what to build. The code that
> exists in the repository today is a prototype. Where this spec and the existing code disagree,
> **the spec wins** unless the spec explicitly says "keep the existing behaviour".
>
> **Date written:** 2026-10-20

---

## 1. What Web2API is (one paragraph)

Web2API turns the AI chat websites a person is **already logged into in their own browser**
(ChatGPT, Claude, Gemini, DeepSeek, Grok, Perplexity, Mistral Le Chat, Qwen, Kimi, Copilot, …)
into a **local, OpenAI-compatible HTTP API**. A browser extension drives the chat page exactly like
a person would (types the prompt, presses send, waits for the answer, reads the answer). A small
local server (the *bridge*) exposes `http://127.0.0.1:<port>/v1/chat/completions` and relays every
request to the extension over a WebSocket. Later, an MCP server will sit on top of the bridge, and
a "maintainer" agent (using a real paid API) will automatically repair the extension when a chat
website changes its HTML.

## 2. Hard requirements given by the project owner

These came directly from the owner. Every design decision in this spec traces back to them.

| # | Requirement | Where it is addressed |
|---|---|---|
| R1 | Phase 1 is **just an extension that gives API access**. MCP comes later. | `03-target-architecture.md`, `11-future-maintainer-and-mcp.md` |
| R2 | **Do not restrict to Gemini.** Support all the major chat sites, like the inspo project does (ChatGPT, Claude, Gemini) and more. | `05-provider-adapters.md` |
| R3 | **Assume the user has the browser open** and is logged in. No headless Playwright, no cookie stealing, no separate login flow. | `03-target-architecture.md` §3 |
| R4 | Later, a **maintainer** using a real API will update the extension when a website changes. The extension must therefore be *maintainable by a machine*: selectors as data, health checks, DOM snapshots. | `05-provider-adapters.md` §2, `11-future-maintainer-and-mcp.md` |
| R5 | The `inspo/` folder (formerly `legacy/`) is a friend's working project ("PromptRelay") that successfully extracts the latest chat response. Borrow its proven techniques. | `01-current-state-analysis.md` §3 |

## 3. Reading order

Read **all** of these before writing code. They are long on purpose; each one assumes you read the
previous ones.

| File | What it contains | When you need it |
|---|---|---|
| `00-README.md` | This file. Ground rules, glossary. | Always first. |
| `01-current-state-analysis.md` | What exists today in this repo and in `inspo/`, file by file, and what is worth keeping. | Before touching any existing file. |
| `02-loopholes-and-issues.md` | Every bug, security hole, design flaw, and fragility found in both codebases, with file:line, impact, and the fix. | Before designing anything — these are the traps to avoid. |
| `03-target-architecture.md` | The system we are building: components, data flow, key decisions and *why*, final directory layout. | Before writing the first file. |
| `04-extension-spec.md` | Exact behaviour of every part of the browser extension (background, content scripts, main-world network tap, popup). | While building the extension. |
| `05-provider-adapters.md` | The provider adapter model, the selector-config JSON schema, and per-site notes for every supported website. | While building/adding a provider. |
| `06-bridge-protocol.md` | The WebSocket wire protocol between extension and bridge: every message type, field, error code, and sequence diagram. | While building either side of the WebSocket. |
| `07-bridge-server-spec.md` | The local HTTP server: OpenAI-compatible endpoints, streaming, conversation mapping, admin endpoints, config. | While building the bridge server. |
| `08-security.md` | Threat model and the mandatory security controls. | Before shipping anything, and while building auth. |
| `09-testing-strategy.md` | Unit tests, DOM-fixture tests, live smoke tests, health checks. | Continuously. |
| `10-implementation-plan.md` | **The ordered, step-by-step build plan** with acceptance criteria for each step. | This is your task list. Follow it in order. |
| `11-future-maintainer-and-mcp.md` | What the future maintainer agent and MCP server will need, and the hooks you must build *now* so they are possible later. | Before finalising the protocol and config formats. |
| `13-api-keys-and-openai-compat.md` | OpenAI-style API keys (`sk-w2a-…`), scopes, rate limits, and the exact OpenAI compatibility contract + conformance suite. Supersedes the single API token in `07`/`08`. | Before building auth or the `/v1` endpoints. |
| `12-product-and-distribution.md` | What makes this a dependable product rather than a prototype: footprint budgets, reliability engineering, binary + source distribution, service install, updates, diagnostics, CI/release, support policy. | Before Phase 3, and again before release. |

## 4. Ground rules for the implementer

Follow these unless a specific document overrides them.

1. **Follow `10-implementation-plan.md` in order.** Each phase has acceptance criteria. Do not start
   phase N+1 until phase N's criteria pass. If a criterion cannot be met, stop and report why rather
   than silently weakening it.
2. **Never hard-code a CSS selector in JavaScript logic.** All site-specific selectors, URLs, labels
   and timing constants live in the provider config JSON files (see `05-provider-adapters.md`). Code
   reads them through the provider registry. This is the single most important rule for R4.
3. **No remote code.** The extension may receive *data* (selector overrides) from the bridge, but
   never code to `eval`. Chrome Web Store policy forbids remote code in MV3, and it is a security
   hole. Network-response parsers are code and therefore ship inside the extension.
4. **Vanilla JavaScript, no bundler, no framework** in the extension. Use modern JS (ES2022), JSDoc
   type comments, and plain files. Content scripts cannot be ES modules, so they share one namespace
   object (`globalThis.W2A`). The background script *can* be an ES module (`"type": "module"`).
   Rationale: the future maintainer agent must be able to read and patch any file without a toolchain.
5. **Python 3.11+ with exactly one third-party dependency, `aiohttp`**, for the bridge, managed with
   `uv` and a `pyproject.toml` (replace `requirements.txt`). Everything else is the standard
   library. The bridge ships two ways: from source (`uv`) **and** as a single-file standalone binary
   (`12-product-and-distribution.md`). Stay within the size/RAM/startup budgets in `12` §2.
   Playwright, FastAPI, uvicorn, pydantic and httpx are never used.
6. **One request in flight per chat tab.** A chat tab is a single-threaded resource. Parallelism is
   achieved with multiple tabs (a tab pool), never by sending two prompts into the same tab.
7. **Every failure must be loud and typed.** No `catch (e) {}` that swallows errors. Every error
   that reaches the API client must carry one of the error codes defined in `06-bridge-protocol.md` §7.
   A timed-out generation is an *error* or a `finish_reason: "length"`, never a silent "success" with
   partial text.
8. **Match the surrounding code style** once code exists: 2-space indent in JS, 4-space in Python,
   double quotes in JS, `snake_case` in Python, `camelCase` in JS, small functions, comments that
   explain *why* rather than *what*.
9. **Write tests alongside code**, as specified in `09-testing-strategy.md`. Parser and protocol code
   must have unit tests before being wired in.
10. **Do not delete `inspo/`.** It is reference material. Do not import from it at runtime; copy and
    adapt code instead, with a comment `// Adapted from inspo/extension/<path>`.

## 5. Glossary

| Term | Meaning |
|---|---|
| **Provider** | A chat website, e.g. `chatgpt`, `claude`, `gemini`. Identified by a lowercase id. |
| **Provider adapter** | The combination of a provider's config JSON (selectors, URLs, timings) and optional provider-specific code (network-stream parser, special input handling). |
| **Bridge** | The local Python server. Exposes HTTP to API clients, WebSocket to the extension. |
| **Bridge client** | The code inside the extension's background script that holds the WebSocket to the bridge. |
| **Job** | One prompt → one response execution inside one chat tab. Has a `jobId`. |
| **Driver** | The content-script code that executes a job in a page: find input, insert text, submit, observe, extract. |
| **Worker tab** | A browser tab that the extension has *claimed* for API use. The extension never uses a tab the user is actively chatting in unless the user explicitly assigned it. |
| **Tab pool** | The set of worker tabs per provider and their busy/idle state. |
| **Net tap** | A script running in the page's MAIN world that wraps `window.fetch` (and `EventSource`/XHR where needed) to observe the site's own streaming response — the most reliable way to get exact markdown and real streaming. |
| **DOM extraction** | Reading the answer from the rendered HTML and converting it back to markdown. The fallback when the net tap is unavailable. |
| **Completion signal** | Any observable fact that tells us the model finished: stream closed, stop-button disappeared, `data-is-streaming="false"`, action toolbar appeared, etc. |
| **Health check / canary** | A cheap check that each critical selector still matches something on a live page. Results feed the future maintainer. |
| **DOM snapshot** | A sanitised HTML dump of a provider page captured when something fails, so selectors can be fixed offline (by a human or the maintainer agent). |
| **Conversation mapping** | How the bridge decides whether an incoming stateless OpenAI request continues an existing web chat thread or starts a new one. |
| **Inspo** | The `inspo/` folder: the friend's "PromptRelay" extension. Reference only. |

## 6. Current repository state (snapshot at time of writing)

```
web2api/
├── bridge_server.py        # Prototype bridge (FastAPI + WebSocket; replaced by bridge/) for the Firefox extension. Gemini only.
├── server.py               # LEGACY: Playwright headless server. Superseded (violates R3).
├── session_manager.py      # LEGACY: Playwright automation engine for Gemini.
├── setup_session.py        # LEGACY: Playwright interactive login.
├── templates/index.html    # LEGACY: dashboard for server.py.
├── ask-gemini.sh           # LEGACY: curl helper for server.py.
├── start.sh                # Launcher (setup / bridge / serve / auth).
├── requirements.txt        # Python deps (mixes bridge + Playwright deps).
├── far_future.md           # Long-term ACP/agent vision (out of scope for now).
├── README.md, docs/        # Docs for the LEGACY Playwright server.
├── extension/              # Prototype Firefox MV2 extension. Gemini only.
├── inspo/extension/        # Friend's Chrome MV3 extension (PromptRelay). ChatGPT + Claude + Gemini.
└── spec/                   # ← you are here
```

The `legacy/` folder was renamed to `inspo/` on 2026-10-20 at the owner's request.
