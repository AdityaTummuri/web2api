# 07 — Bridge Server Specification

The bridge is a local Python service. To API clients it looks like the OpenAI Chat Completions API.
Internally it maps each request to a job for the extension (`06-bridge-protocol.md`).

Package: `bridge/` with module `web2api_bridge` (layout in `03-target-architecture.md` §5).

---

## 1. Tooling

**Lightweight rule:** exactly **one** third-party runtime dependency: `aiohttp` (HTTP server,
WebSocket server, SSE streaming in one library). Everything else is the standard library:
`asyncio`, `json`, `hmac`, `secrets`, `hashlib`, `tomllib`, `logging`, `dataclasses`, `argparse`,
`re`, `unicodedata`. Request validation is hand-written (small functions that raise
`Web2APIError`), replacing pydantic; the OpenAI request surface is small enough that this is
shorter and faster than a schema library, and it lets us accept "anything extra" without 422s.
FastAPI, uvicorn, starlette, pydantic and httpx are **not** used anywhere (including tests).

* Python ≥ 3.11. `uv` for env and lockfile (commit `uv.lock`).
* `bridge/pyproject.toml`:
  ```toml
  [project]
  name = "web2api-bridge"
  version = "0.1.0"
  requires-python = ">=3.11"
  dependencies = ["aiohttp>=3.10,<4"]

  [dependency-groups]
  dev = ["pytest>=8", "pytest-asyncio>=0.23", "pyinstaller>=6"]

  [project.scripts]
  web2api-bridge = "web2api_bridge.cli:main"

  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"
  ```
* Run from source: `cd bridge && uv sync && uv run web2api-bridge`.
* Tests: `uv run pytest`. Test clients use aiohttp's own client + `aiohttp.test_utils`
  (`AioHTTPTestCase` / `aiohttp_client` fixture) and `session.ws_connect` — no extra libraries.
* Standalone binary: see `12-product-and-distribution.md` §3.
* Budgets (enforced in CI, `12` §2): installed size, idle RAM, startup time, binary size.

---

## 2. Configuration

Precedence: CLI flags > environment variables > config file > defaults.

Config file: `$XDG_CONFIG_HOME/web2api/config.toml` (default `~/.config/web2api/config.toml`).
State dir: `$XDG_STATE_HOME/web2api/` (default `~/.local/state/web2api/`).

| Key (TOML) | Env var | Default | Meaning |
|---|---|---|---|
| `host` | `WEB2API_HOST` | `127.0.0.1` | Bind address. Non-loopback refused unless `allow_remote = true` (§08 3.4). |
| `port` | `WEB2API_PORT` | `8787` | Port for HTTP and WebSocket. |
| `allow_remote` | `WEB2API_ALLOW_REMOTE` | `false` | |
| `keys_file` | — | `<config>/keys.json` | API keys (hashes only), `sk-w2a-…` format. Managed with `web2api-bridge keys …`; full design in `13` §1. |
| `pairing_token_file` | — | `<config>/pairing_token` | Token the extension sends in `HELLO`. Auto-generated (0600). |
| `allowed_extension_origins` | — | `["chrome-extension://*", "moz-extension://*"]` | Origin patterns allowed on the WS. Can be pinned to exact ids. |
| `log_level` | `WEB2API_LOG_LEVEL` | `info` | |
| `log_content` | `WEB2API_LOG_CONTENT` | `false` | Log prompts/answers (debug only). |
| `default_provider_order` | — | `["claude", "chatgpt", "gemini"]` | Used by model `auto`. |
| `model_aliases` | — | `{}` | e.g. `{ "gpt-4o" = "chatgpt/default" }` for clients that hard-code model names. |
| `history_mode` | — | `"normal"` | Default `historyMode` for jobs (`normal` / `temporary`). |
| `timeouts.queue_ms` | — | `60000` | |
| `timeouts.first_token_ms` | — | `60000` | |
| `timeouts.total_ms` | — | `300000` | |
| `timeouts.stall_ms` | — | `90000` | |
| `max_prompt_chars` | — | `200000` | |
| `include_web2api_field` | — | `true` | Add the `web2api` object to responses (§6.1). |
| `persist_threads` | — | `false` | Persist the conversation map to `<state>/threads.json`. |
| `sse_keepalive_sec` | — | `15` | Comment lines while waiting. |

### 2.1 CLI (`cli.py`)

```
web2api-bridge [serve] [--host H] [--port P] [--log-level L]
web2api-bridge keys create|list|revoke|rotate   # OpenAI-style API keys, scopes, limits (13 §1.6)
web2api-bridge pairing show|rotate    # extension pairing token
web2api-bridge status                 # GET /web2api/status (needs an admin-scope key via WEB2API_API_KEY or --key); pretty print
web2api-bridge --version              # bridge + protocol version, python or frozen
web2api-bridge doctor [--probe]       # checklist of the whole chain (12 §6.1)
web2api-bridge support-bundle [-o P]  # redacted zip for bug reports (12 §6.2)
web2api-bridge service install|uninstall|status|restart   # per-user auto-start service (12 §4)
```
All commands must work identically from source and from the frozen binary (`12` §3). Use `argparse`
only (no click/typer — dependency rule).

**Directories (stdlib only, no `platformdirs`):** implement `paths.py` — config dir: Linux
`$XDG_CONFIG_HOME` or `~/.config`, macOS `~/Library/Application Support`, Windows `%APPDATA%`, each +
`/web2api`; state dir: Linux `$XDG_STATE_HOME` or `~/.local/state`, macOS
`~/Library/Application Support/web2api/state`, Windows `%LOCALAPPDATA%\web2api`. The `~/.config/...`
paths used elsewhere in this spec are the Linux values. Create dirs with mode 0700 on POSIX.

On `serve` startup print a banner. The API key line appears **only on the very first run** (when the
`default` key is created, `13` §1.6); later runs show the key id and how to make more:
```
Web2API bridge 0.1.0 listening on http://127.0.0.1:8787
  OpenAI base URL : http://127.0.0.1:8787/v1
  API key         : sk-w2a-…    (shown once; new keys: web2api-bridge keys create --name NAME)
  Pairing token   : w2a_pair_…  (paste into the extension popup; `web2api-bridge pairing show`)
```
API keys: format and storage in `13` §1. Pairing token: `"w2a_pair_" + secrets.token_urlsafe(32)`.
Create secret files with `os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)`.

---

## 3. App structure (`app.py`)

`create_app(settings) -> aiohttp.web.Application`:
1. `web.Application(middlewares=[...], client_max_size=5 * 1024 * 1024)`. Middleware order
   (outermost first): request-id (adds `X-Request-Id`), **error mapper**, **host check**
   (`08` §3.3), **bearer auth** for all HTTP routes except `GET /healthz`, access log (no bodies).
   aiohttp middlewares are plain `@web.middleware` async functions.
2. No CORS handling anywhere (`08` §3.1) — aiohttp adds none by default.
3. Error mapper middleware: `Web2APIError` → OpenAI error body (§7); `web.HTTPException` from
   aiohttp (404/405/413) → same body shape; invalid JSON or a failed hand-written validation →
   400 `invalid_request_error` with `param` set to the offending field name; any other exception →
   500 `INTERNAL_ERROR` (log the traceback, return a generic message).
4. Routes registered with `app.router.add_*`: `openai_compat.chat`, `openai_compat.models`,
   `admin`, and the WebSocket route `GET /ws/extension` (`hub.py`).
5. `app["hub"] = ExtensionHub(settings)`, `app["conversations"] = ConversationStore(settings)`,
   `app["router"] = Router(hub, settings)`, `app["settings"] = settings`.
6. `app.on_shutdown`: close all extension sockets with 4500 and fail running jobs.
7. Runner: `web.AppRunner(app, handle_signals=True)` + `web.TCPSite(host, port)`; `cli.py` owns the
   event loop (`asyncio.run`). Handle SIGINT/SIGTERM for graceful shutdown (drain for ≤ 10 s:
   running jobs get `JOB_CANCEL`, then sockets close). On Windows, `handle_signals` is limited —
   rely on `KeyboardInterrupt` and the service wrapper (`12` §4).
8. WebSocket: `ws = web.WebSocketResponse(heartbeat=None, max_msg_size=16 * 1024 * 1024)`; do the
   Origin/Host checks **before** `await ws.prepare(request)` and return
   `web.HTTPForbidden()` (HTTP 403) on failure; application-level close codes (4400–4500) are sent
   with `await ws.close(code=..., message=...)` after `prepare`.

---

## 4. Extension hub and router

### 4.1 `hub.py` — data model

```python
@dataclass
class Connection:
    connection_id: str
    instance_id: str
    websocket: web.WebSocketResponse
    browser: dict
    capabilities: set[str]
    providers: dict[str, ProviderInfo]     # from PROVIDERS_UPDATE
    connected_at: float
    last_seen: float
    send_lock: asyncio.Lock                 # serialise websocket.send_text

@dataclass
class Job:
    job_id: str
    provider: str
    connection_id: str
    created_at: float
    phase: str = "created"
    submitted: bool = False                 # set True once phase >= "submitting" reported... see below
    events: asyncio.Queue                   # JOB_DELTA / JOB_PROGRESS / terminal frames
    terminal: asyncio.Future                # resolves with JOB_DONE payload or raises Web2APIError
    last_seq: int = 0
    pending_deltas: dict[int, dict]         # out-of-order buffer
```
`submitted` is taken from the terminal `JOB_ERROR.submitted` / `JOB_CANCELLED.submitted` when present;
otherwise derived from the last `JOB_PROGRESS` phase (`submitting` or later ⇒ `True`, conservative).

### 4.2 `hub.py` — behaviour

* `ws_endpoint(request)`: check Origin (`08` §3.2) **before** `ws.prepare()` (reject with
  `raise web.HTTPForbidden()`); `await ws.prepare(request)`; `await asyncio.wait_for(ws.receive_str(), 5)`
  for `HELLO`; validate version/token (constant-time `hmac.compare_digest`); register connection
  (handling duplicate `instance_id`, `06` §3.1); send `WELCOME`; then `async for msg in ws:` →
  handle `WSMsgType.TEXT` → `dispatch(frame)`; treat `ERROR`/`CLOSE` as disconnect.
* `dispatch`: by `type` → `PROVIDERS_UPDATE` (update connection), `PING` (reply `PONG`), `PONG`,
  `JOB_*` (route to job), responses with `requestId` (resolve pending request future),
  `HEALTH_REPORT` (store in a ring buffer of 100, expose via admin API).
* `finally` (socket closed): remove **this** connection only; fail its non-terminal jobs with
  `EXTENSION_DISCONNECTED` (`submitted` per job state); fail its pending requests.
* `start_job(conn, job_spec) -> Job`: create Job, send `JOB_START`, wait ≤ 2 s for `JOB_ACCEPTED` or
  `JOB_ERROR` (timeout → `EXTENSION_DISCONNECTED`-like error `INTERNAL_ERROR: no ack`).
* `cancel_job(job_id, reason)`: send `JOB_CANCEL`; do not wait (the terminal frame arrives via the
  normal path). Idempotent.
* Delta ordering per `06` §5.4.
* Heartbeat watchdog task: every 10 s, close connections silent for > 60 s.
* `request(conn, type, payload, timeout)` helper for config/health/snapshot request-responses.

### 4.3 `router.py`

`resolve_model(model: str) -> (provider, variant)`:
1. Apply `model_aliases`.
2. `auto` or `web2api/auto` → first provider in `default_provider_order` that is routable on any
   connection; none → `NO_EXTENSION` (if no connections) or `PROVIDER_UNAVAILABLE`.
3. `<provider>` → `(provider, "default")`; `<provider>/<variant>` → as given.
4. Unknown provider id (not offered by any connection) → `MODEL_NOT_AVAILABLE` (HTTP 404, OpenAI code
   `model_not_found`).
5. Variant not in the provider's `variants` → `MODEL_NOT_AVAILABLE`.

`pick_connection(provider) -> Connection`: among connections offering the provider with a routable
status, prefer (a) `status == "ready"` with idle tabs, (b) fewest busy tabs, (c) most recent
`connected_at`. If the request continues a thread whose record has a `connection_id`, prefer that
connection (thread affinity).

---

## 5. Conversation mapping (`conversations.py`) — fixes L-15

### 5.1 Goal

OpenAI clients send the full history every call. Web chats keep history server-side. We want:
* **Continuation:** if the request is exactly "the conversation we already ran in web thread T, plus
  new user message(s)", send only the new user message(s) into thread T.
* **Fresh start:** otherwise open a new chat and send one prompt that contains the whole history in a
  clear transcript format.

### 5.2 Normalisation

`normalize(messages) -> list[NMsg]` where `NMsg = (role, text)`:
* Roles: `system` and `developer` → `system`; `user`; `assistant`; `tool` (see §8).
* `content` may be a string, `null` (assistant with only tool calls), or a list of parts. Text parts
  (`{"type":"text","text":…}`) are joined with `\n`. Any non-text part (`image_url`, `input_audio`,
  `file`) → `UNSUPPORTED_CONTENT` (HTTP 400) in v1.
* Text normalisation for fingerprinting only (the prompt keeps the original text): `\r\n`→`\n`, strip
  trailing whitespace on each line, collapse 3+ newlines to 2, strip leading/trailing whitespace,
  Unicode NFC.
* `name` fields are ignored.

### 5.3 Fingerprints

`fp(provider, nmsgs) = sha256(json.dumps([provider] + [[r, t] for r, t in nmsgs], ensure_ascii=False, separators=(",", ":")))`.

### 5.4 Store

```python
@dataclass
class ThreadRecord:
    provider: str
    thread_url: str | None       # None for temporary chats (not URL-addressable)
    thread_id: str | None
    tab_id: int | None           # required for temporary chats (only continuable in the same tab)
    connection_id: str | None
    history_mode: str
    tip_fp: str                   # fingerprint of the conversation as of the last completed turn
    created_at: float
    last_used_at: float
    turns: int
    busy: bool                    # a job is currently running in this thread
```
Index: `tip_fp → ThreadRecord`. LRU capped at 1000 records; optional JSON persistence
(`persist_threads`). Records older than 7 days are evicted.

### 5.5 Algorithm

```
plan(provider, nmsgs, overrides) -> Plan(target, prompt_text, prefix_fp_after)

0. Validate: nmsgs non-empty; last message role must be "user" (or "tool" when tools enabled, §8).
   Last = "assistant" (prefill) → 400 UNSUPPORTED_CONTENT "assistant prefill is not supported".
1. Split: tail = maximal run of trailing "user" messages; prefix = everything before it.
2. Explicit override (body web2api.thread or header X-Web2API-Thread):
     "new"      → fresh start (step 5)
     "current"  → target {mode:"current"} and prompt_text = join(tail); no transcript; record nothing
                  as continuation unless the extension returns a thread URL
     <url>      → target {mode:"continue", threadUrl:url}; prompt_text = join(tail)
3. If prefix is empty → fresh start (step 5).
4. rec = store.get(fp(provider, prefix)):
     if rec and not rec.busy and prefix[-1].role == "assistant"
            and (rec.thread_url or rec.tab_id still a worker tab):
         target = continue(rec.thread_url) [or current-in-tab rec.tab_id for temporary]
         prompt_text = join(tail)
         system messages that appear in the prefix are already in the thread → ignore
         if tail contains a system message change → fresh start instead (system changed mid-convo)
         → return
     if rec and rec.busy → fresh start (do not interleave; client is branching concurrently)
5. Fresh start: target {mode:"new"}; prompt_text = build_transcript(nmsgs_original)
```
`join(tail)` = texts joined with `\n\n`.

After `JOB_DONE`:
```
full = nmsgs + [("assistant", normalize_text(done.text))]
store.put(fp(provider, full), ThreadRecord(thread_url=done.threadUrl, thread_id=done.threadId,
          tab_id=done.tabId, connection_id=..., history_mode=..., tip_fp=fp(provider, full), ...))
remove the old record whose tip_fp == fp(provider, prefix)   # the thread moved forward
```

Fallback: if a continuation job fails with `PAGE_NAVIGATED`/`SELECTOR_NOT_FOUND` *before submission*
because the thread URL no longer exists (deleted chat), retry once as a fresh start and drop the record.

Known limitations (document in README): if the client edits earlier messages or trims history
(context-window management), the fingerprint misses and a fresh chat with a transcript is used —
correct but uses more of the web model's context.

### 5.6 Transcript template (`build_transcript`)

Rules, in order:
1. Exactly one `user` message and no `system` → send the user text verbatim.
2. `system` + exactly one `user` →
   ```
   {system text(s) joined by \n\n}

   ---

   {user text}
   ```
3. Otherwise (multi-turn):
   ```
   {system text(s), if any}

   Below is a conversation transcript. Continue it: reply ONLY with the next message from the
   assistant, without any prefix like "Assistant:".

   <transcript>
   <user>
   {text}
   </user>
   <assistant>
   {text}
   </assistant>
   <user>
   {text}
   </user>
   </transcript>
   ```
   If any message text contains the literal strings `<transcript>`, `</transcript>`, `<user>`,
   `</user>`, `<assistant>`, `</assistant>`, replace the angle brackets in those occurrences with
   `‹`/`›` to keep the structure unambiguous.
4. Templates are module constants so they can be changed in one place; expose
   `transcript_template` in config later if needed (not v1).

---

## 6. OpenAI-compatible endpoints

### 6.1 `POST /v1/chat/completions` — request

Accepted fields (parsed by a hand-written `parse_chat_request(body: dict) -> ChatRequest`
dataclass builder in `openai_compat/schemas.py`; **unknown fields are ignored, never an error**):

| Field | Handling |
|---|---|
| `model` | Required. Resolved by router (§4.3). |
| `messages` | Required. §5.2. |
| `stream` | Supported (§6.2). |
| `stream_options.include_usage` | Supported: extra final chunk with `usage`. |
| `stop` (str or list ≤ 4) | Applied **post hoc**: final text truncated at the earliest stop sequence; `finish_reason: "stop"`. During streaming, hold back the last `max(len(stop))-1` characters so a stop sequence spanning chunks is caught. |
| `n` | Only `1` (or absent). Otherwise 400. |
| `temperature`, `top_p`, `max_tokens`, `max_completion_tokens`, `presence_penalty`, `frequency_penalty`, `seed`, `logit_bias`, `user`, `metadata`, `parallel_tool_calls` | Accepted and **ignored** (the web UI offers no such controls). Add response header `X-Web2API-Ignored-Params: temperature,max_tokens` listing the ones that were present. |
| `logprobs`, `top_logprobs` | If truthy → 400 (cannot provide). |
| `response_format` | `{"type":"text"}` ok. `{"type":"json_object"}` / `json_schema` → append an instruction to the prompt ("Respond with only a single valid JSON value, no markdown fences") and post-process: if the answer contains a fenced ```json block, unwrap it; validate with `json.loads`; on failure return the raw text and warning `json_invalid` (do not error). |
| `tools`, `tool_choice` | v1: 400 `UNSUPPORTED_CONTENT` "tool calling is not supported yet". Later: §8. |
| `web2api` (via `extra_body`) | Web2API options object: `{"thread": "new"|"current"|"<url>", "history_mode": "normal"|"temporary", "include_reasoning": bool, "timeouts": {...}, "extract": ["code_blocks"]}`. All optional. |

Header alternatives (for clients that can't set `extra_body`): `X-Web2API-Thread`,
`X-Web2API-History-Mode`.

### 6.2 Response — non-streaming

```json
{
  "id": "chatcmpl-<jobId>",
  "object": "chat.completion",
  "created": 1760960000,
  "model": "claude/default",
  "system_fingerprint": null,
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "…markdown…", "refusal": null },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": { "prompt_tokens": 120, "completion_tokens": 340, "total_tokens": 460, "estimated": true },
  "web2api": {
    "provider": "claude",
    "model_label": "Claude Sonnet 4.5",
    "thread_url": "https://claude.ai/chat/…",
    "continued": true,
    "source": "net",
    "warnings": [],
    "timings": { "queued_ms": 0, "first_token_ms": 1650, "total_ms": 9300 }
  }
}
```
* `model` echoes the requested model string (after alias resolution, report the resolved
  `provider/variant`).
* Token estimate: `ceil(len(text) / 4)`; `estimated: true` (L-22).
* If `include_reasoning` and the job returned reasoning: `message.reasoning_content` (the field name
  used by DeepSeek-style APIs, widely understood by clients).
* `web2api` omitted when `include_web2api_field = false`.

### 6.3 Response — streaming (SSE)

`Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
Each event is `data: <single-line JSON>\n\n` (`json.dumps` guarantees no raw newlines — fixes L-17).

Sequence:
1. Immediately after the job is accepted: role chunk
   `{"id","object":"chat.completion.chunk","created","model","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}`.
2. While waiting (queue, thinking, slow first token): every `sse_keepalive_sec` send a comment line
   `: keepalive\n\n` (ignored by SSE parsers, keeps proxies/clients from timing out).
3. For each `JOB_DELTA kind=text`: chunk with `delta: {"content": text}` (after the stop-sequence
   hold-back logic, §6.1).
   For `kind=reasoning` when `include_reasoning`: `delta: {"reasoning_content": text}`; otherwise drop.
4. On `JOB_DONE`: let `streamed` = concatenation of emitted content. If `done.text` (after stop
   truncation) starts with `streamed`, emit the remaining suffix as one chunk. If it does not (divergence),
   emit nothing more and log a warning (the client already displayed slightly different text — rare
   with the stable-prefix policy). Then the final chunk `delta: {}` with `finish_reason`.
5. If `include_usage`: chunk with `choices: []` and `usage`.
6. If `include_web2api_field`: one more chunk `{"object":"chat.completion.chunk", "choices": [], "web2api": {...}}`.
   (Strict clients ignore unknown top-level fields; chunks with empty `choices` are standard since
   `include_usage` exists.)
7. `data: [DONE]\n\n`.

Errors:
* Before the first content chunk → respond with a normal JSON error and HTTP status (not SSE) if the
  error arrives before headers are sent. Practically: wait for `JOB_ACCEPTED` before starting the
  `StreamingResponse`, so routing/validation/queue-rejection errors return proper HTTP errors.
* After streaming began → emit `data: {"error": {"message", "type", "code"}}\n\n` then
  `data: [DONE]\n\n`. If partial text exists, it has already been streamed; the final chunk uses
  `finish_reason: "length"` for `GENERATION_TIMEOUT`/`GENERATION_STALLED` before the error event.

Streaming is implemented with `web.StreamResponse` (`await resp.prepare(request)`, then
`await resp.write(b"data: ...\n\n")` per event; `resp.write` raises `ConnectionResetError` when the
client is gone).

Client disconnect: catch `ConnectionResetError` / `asyncio.CancelledError` (aiohttp cancels the
handler task when the client goes away) → `hub.cancel_job(job_id, "client_disconnected")` → re-raise. For non-streaming requests,
aiohttp cancels the handler task on client disconnect (default behaviour on aiohttp ≥ 3.7 unless
`handler_cancellation` is disabled — **set `web.AppRunner(app, handler_cancellation=True)`
explicitly**), so wrap the job wait in `try/except asyncio.CancelledError` → cancel the job →
re-raise. Add a unit test proving a disconnect sends `JOB_CANCEL`.

### 6.4 Optional extraction extras

If `web2api.extract` contains `"code_blocks"`, add `web2api.code_blocks: [{"language", "code"}]`
parsed from the final markdown with a fence-aware parser (handles ```` and ~~~ fences, info strings).
This replaces the always-on `extracted` object of the prototype (L-34).

### 6.5 `GET /v1/models` and `GET /v1/models/{model}`

Built from current connections: for each routable provider, `"<provider>"` and each
`"<provider>/<variant>"`, plus `"auto"`, plus configured aliases. Shape:
```json
{ "object": "list", "data": [ { "id": "claude/default", "object": "model", "created": 0, "owned_by": "web2api:claude" } ] }
```
If no extension is connected, return an empty list (200), not an error (clients call this at startup).
Only models the calling key may use are listed (`13` §1.3). `GET /v1/models/{model:.+}` returns one model
object (the id contains `/`, so the route uses a catch-all pattern); unknown → 404 `model_not_found`.
Any other unimplemented `/v1/*` path returns the `unsupported_endpoint` error in `13` §2.1.

---

## 7. Errors (`errors.py`)

```python
class Web2APIError(Exception):
    def __init__(self, code: str, message: str, *, http_status: int | None = None,
                 retry_after: int | None = None, detail: dict | None = None, partial_text: str | None = None): ...
```
HTTP status from the table in `06` §7 unless overridden. Body:
```json
{ "error": { "message": "Claude is showing a login page. Log in to claude.ai in your browser.",
             "type": "web2api_error",
             "code": "LOGIN_REQUIRED",
             "param": null,
             "web2api": { "provider": "claude", "partial_text": null, "health_report_id": null } } }
```
Map `type` for familiar client behaviour: 400 → `invalid_request_error`; 401 → `authentication_error`;
404 → `invalid_request_error` with `code: "model_not_found"`; 429 → `rate_limit_error`; 5xx →
`api_error`. Put the Web2API code in `code`, except `model_not_found`. `Retry-After` header when known.

Human-readable messages must tell the user **what to do** ("Open the extension popup and click
'Open worker tab' for Claude", "Solve the captcha in the Web2API window").

---

## 8. Tool calling emulation (later phase, design only)

Not in v1. Designed now so the protocol and conversation mapper don't need breaking changes.

* When `tools` is present: append to the prompt a tool section describing each function (name,
  description, JSON schema) and the exact output contract:
  ````
  If you need to call a tool, reply with ONLY one fenced block and nothing else:
  ```tool_call
  {"name": "<function name>", "arguments": { ... }}
  ```
  ````
* Parse the final answer: if it consists (after trimming) of one or more ```` ```tool_call ```` blocks with
  valid JSON whose `name` is one of the declared tools and `arguments` validates against the schema
  (basic type check), return `message.tool_calls` (ids `call_<random>`), `content: null`,
  `finish_reason: "tool_calls"`. Otherwise return as plain text.
* `tool` role messages in the next request become user text in the tail:
  `Tool result for <name> (call <id>):\n<content>` — so the continuation path still works.
* Streaming with tools: buffer the whole answer (no content deltas) when the answer starts with a
  ```` ```tool_call ```` fence; otherwise stream normally.
* Web2API never executes tools itself (L-45).

---

## 9. Admin API (`admin.py`) — also the future MCP/maintainer surface

All require an API key with the `admin` scope (`13` §1.3); key management endpoints are in `13` §1.7. All return JSON, never prompt/answer text unless stated.

| Method & path | Purpose |
|---|---|
| `GET /healthz` | **No auth.** `{"ok": true}` only. For process supervisors. |
| `GET /web2api/status` | Bridge version, uptime, connections (instance, browser, connected_at, capabilities), providers per connection, running job count. |
| `GET /web2api/providers` | Merged provider list across connections with status, tabs, config/override versions. |
| `POST /web2api/providers/{id}/probe` | Sends `HEALTH_PROBE`, returns results. |
| `GET /web2api/health/reports?since=` | Reports received via `HEALTH_REPORT` (ring buffer) merged with `HEALTH_REPORTS_GET`. |
| `GET /web2api/snapshots/{snapshot_id}` | Fetches via `SNAPSHOT_REQUEST`; returns `text/html`. |
| `POST /web2api/providers/{id}/snapshot` | Captures a fresh snapshot from an idle worker tab. |
| `GET /web2api/config/{id}` | Effective/bundled/override config via `CONFIG_GET`. |
| `POST /web2api/config/{id}/override` | Body = override object (`05` §2.4). Validated against the shared JSON Schema first, then `CONFIG_OVERRIDE`. Returns the `CONFIG_ACK`. |
| `DELETE /web2api/config/{id}/override?to=bundled|previous` | `CONFIG_REVERT`. |
| `GET /web2api/jobs?limit=50` | Recent jobs: id, provider, phase, outcome code, timings, warnings. No text. |
| `POST /web2api/jobs/{job_id}/cancel` | Cancel. |
| `GET /web2api/jobs/{job_id}/events` | SSE stream of the job's phase changes (no text) — for MCP progress (`11` H5). Stretch. |
| `POST /web2api/providers/{id}/probe` with body `{"candidatePatch": {...}}` | Dry-run probe (`11` H6). |
| `POST /web2api/providers/{id}/stream-sample` | Arms a redacted stream capture for the next job (`11` H4). Stretch. |
| `GET /web2api/threads` | Conversation map entries (provider, thread_url, turns, last_used). |
| `DELETE /web2api/threads` | Clear the map. |

---

## 10. Logging

* Python `logging`, one line per event, `key=value` style: `event=job_done job=job_01J provider=claude
  source=net total_ms=9300 chars=1820`.
* Never log prompt/answer text unless `log_content = true`.
* Log WebSocket connect/disconnect with instance id and browser.

---

## 11. Migration from the prototype

* `bridge_server.py` → replaced by `bridge/web2api_bridge/*`. Delete the root file at the end of
  Phase 3 (when the new bridge passes its tests and a live smoke test).
* `/api/chat`, `/api/reset` (prototype convenience endpoints) are **not** carried over; the OpenAI
  endpoint plus `web2api.thread: "new"` covers both.
* Default port changes from 8000 to 8787 (8000 collides with countless dev servers).
