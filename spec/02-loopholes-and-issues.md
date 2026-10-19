# 02 — Loopholes, Bugs, and Design Flaws

Every issue found while reading the existing code (`bridge_server.py`, `extension/`, legacy Playwright
files) and the inspo project (`inspo/extension/`). Each has an id `L-xx` that other documents
reference.

**Severity scale**

| Severity | Meaning |
|---|---|
| **Critical** | Lets someone other than the owner use the owner's AI accounts or read their conversations. Fix before anything else ships. |
| **High** | Produces wrong answers, silently truncated answers, hangs, or hijacks the user's own chat. |
| **Medium** | Breaks specific clients, specific sites, or specific conditions. |
| **Low** | Cosmetic, dead code, or minor maintainability issue. |

"Verified" means the behaviour was reproduced during analysis (not just inferred from reading).

---

## Summary table

| ID | Severity | Area | One-line summary |
|---|---|---|---|
| L-01 | Critical | Bridge | `CORS allow_origins=["*"]` lets **any website you visit** call your local API and read the answers. |
| L-02 | Critical | Bridge | WebSocket `/ws` has no authentication: any web page or local process can impersonate the extension, read every prompt, and forge every answer. |
| L-03 | Critical | Legacy | Playwright server binds `0.0.0.0` with no auth and serves live screenshots of the logged-in account to the LAN. |
| L-04 | High | Bridge | No `Host` header check → DNS-rebinding attacks bypass "it only listens on localhost". |
| L-05 | High | Bridge | Second WebSocket connection replaces the first; when the old one closes it wipes out the *new* one. |
| L-06 | High | Bridge/Ext | Timeouts don't cancel the generation in the browser; the next prompt is typed into a still-busy tab. |
| L-07 | High | Bridge | `reset_thread()` doesn't take the lock — "new chat" can fire in the middle of a running prompt. |
| L-08 | Medium | Bridge | Server and extension use the *same* timeout value, so they race; time spent waiting for the lock is unbounded and uncounted. |
| L-09 | High | Extension | Uses the first matching tab — which may be the tab the user is actively chatting in. |
| L-10 | Medium | Extension | Waiting for a new tab to load has no timeout; can hang forever. |
| L-11 | High | Extension | If the stop-button selector misses during "thinking", an **empty response** is returned as success. |
| L-12 | High | Ext/Legacy | Timeout returns partial text as a normal successful answer. |
| L-13 | High | Extension | "Count messages before/after" baseline is computed inconsistently and can pick the user's own message as the answer. |
| L-14 | High | Bridge | `stream: true` is ignored; OpenAI SDK clients that stream (Cursor, Continue, LangChain, etc.) break. |
| L-15 | High | Bridge | Every API call pastes the *entire* flattened history into the *same* web chat → duplicated context, quadratic growth, confused roles. |
| L-16 | Medium | Bridge | `content` must be a string; OpenAI's array-of-parts content → HTTP 422. |
| L-17 | Medium | Legacy | SSE frames break on multi-line chunks; delta-by-length streaming emits garbage when earlier text re-renders. |
| L-18 | Medium | Bridge/Ext | `model` is ignored — the UI model is never switched, yet the response claims the requested model. |
| L-19 | High | Extension | Background-tab timer throttling makes `setTimeout` polling slow (≥1 s) or nearly frozen (1/min) in hidden tabs. |
| L-20 | High | Extension | One `sendMessage` reply held open for up to 2 minutes; breaks under MV3 service-worker lifetimes and gives no progress. |
| L-21 | Low | Bridge | `/v1/models` returns a hard-coded, partly obsolete Gemini list. |
| L-22 | Low | Parser | Token `usage` is `chars/4` but presented as real numbers. |
| L-23 | Medium | Extension | Full prompts and responses are written to the console. |
| L-24 | Low | Extension | Fallback bridge URL `ws://127.0.0.1:8765` points at nothing. |
| L-25 | Medium | Bridge | Handshake isn't validated; no protocol version negotiation. |
| L-26 | High | Extension | "New chat" selector `a[href*="/app"]` matches links to *old* conversations. |
| L-27 | Low | Extension | `button:has-text("New chat")` is Playwright syntax, invalid CSS; error silently swallowed. |
| L-28 | High | Extension | Prompt inserted via `innerHTML` + one `<p>`: newlines lost, editor model (Quill/ProseMirror) may not register. |
| L-29 | Medium | Extension | Synthetic `KeyboardEvent("Enter")` fallback is ignored by most frameworks. |
| L-30 | High | Extension | Selectors hard-coded in JS; impossible for a maintainer agent to hot-fix without a code change. |
| L-31 | Medium | Parser | JSON extractor: matches any fenced block; greedy `{…}` returns `null` when two objects exist (verified). |
| L-32 | Medium | Parser | Tool-call regex fires on ordinary prose like `call:print(hello)` (verified). |
| L-33 | Medium | Parser | DOM→markdown loses nested-list indentation, math, images, strikethrough; leaks code-block header labels; normalises no whitespace. |
| L-34 | Low | Parser | Non-standard `extracted` object computed and attached to every response. |
| L-35 | Medium | Extension | Tabs opened before the extension was installed/updated have no content script → "Receiving end does not exist". |
| L-36 | Medium | Extension | Logged-out, captcha, rate-limit, and error states are not detected; they surface as generic timeouts. |
| L-37 | Low | Scripts | `start.sh` falls back to a uv path on the friend's machine. |
| L-38 | Low | Legacy | `ask-gemini.sh` builds JSON by string interpolation → broken/injected JSON on quotes. |
| L-39 | Low | Build | `requirements.txt` mixes Playwright into the bridge; no `pyproject.toml`/lockfile. |
| L-40 | Medium | Inspo | Tier-2 input selectors (`textarea`, any `contenteditable`) can grab the wrong box. |
| L-41 | Medium | Inspo | If the user has text selected, extraction returns the selection instead of the answer. |
| L-42 | Medium | Inspo/Ext | Injected DOM (HUD), inline style changes, and `web_accessible_resources` make the extension detectable by the site. |
| L-43 | Low | Inspo | Teleport payload keyed by platform, so concurrent teleports overwrite each other. |
| L-44 | Low | Inspo | `chrome.storage` read-modify-write race across tabs. |
| L-45 | Medium | All | Model output is untrusted input; nothing treats it as such. |
| L-46 | High | Extension | Popup "test prompt" bypasses the server's lock → two prompts typed into one tab at once. |
| L-47 | Info | All | Automating consumer chat UIs can violate provider Terms of Service; accounts can be rate-limited or suspended. |
| L-48 | Low | All | No images/files/attachments support. |
| L-49 | Medium | Extension | Content rendered outside the message element (Gemini drafts, ChatGPT A/B "which response do you prefer", Claude artifacts, canvas) is missed. |
| L-50 | Low | Bridge | Errors are FastAPI `{"detail": ...}`, not OpenAI's `{"error": {...}}` schema. |

---

## Detailed entries

### L-01 — Wildcard CORS exposes your accounts to every website · Critical

* **Where:** `bridge_server.py:28-34`
  ```python
  app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
  ```
* **What happens:** Any web page open in any browser on the machine can run
  `fetch("http://127.0.0.1:8000/v1/chat/completions", {method:"POST", headers:{"Content-Type":"application/json"}, body: ...})`.
  The CORS preflight succeeds because every origin, method and header is allowed, and the page can
  **read the response**. A malicious or compromised site (or ad script) can silently use your
  ChatGPT/Claude/Gemini accounts and read anything the model says — including context from your
  existing conversation in that tab.
* **Fix:** No CORS middleware by default. Require a bearer token on every HTTP route
  (`08-security.md` §3.1). If browser-based clients must be supported later, add an explicit,
  user-configured origin allowlist.

### L-02 — Unauthenticated WebSocket allows extension impersonation · Critical

* **Where:** `bridge_server.py:134-161`. `websocket.accept()` is called unconditionally; the
  "handshake" is read but never validated; the socket becomes `hub.active_socket`.
* **What happens:** WebSockets are **not** protected by CORS. Any web page can
  `new WebSocket("ws://127.0.0.1:8000/ws")`, send `{"type":"HANDSHAKE"}`, and become the
  extension. From then on it receives every prompt sent by every API client and can return fabricated
  answers. Combined with L-05 it also kicks the real extension off.
* **Fix:** (1) Validate the `Origin` header: only `chrome-extension://<configured id>` and
  `moz-extension://<configured uuid>` are allowed; reject `http(s)://` origins and missing origins.
  (2) Require a pairing token in the first frame (`HELLO.token`) compared with `hmac.compare_digest`.
  (3) Close with code 4401 on failure. Details: `08-security.md` §3.2, `06-bridge-protocol.md` §3.

### L-03 — Legacy server is open to the LAN · Critical (legacy)

* **Where:** `server.py:26` (`HOST = os.getenv("HOST", "0.0.0.0")`), `server.py:186-190`
  (`/api/screenshot`).
* **What happens:** Anyone on the same Wi-Fi can send prompts as you and fetch live screenshots of
  your logged-in Gemini page.
* **Fix:** Archive the legacy server (Phase 0). The new bridge binds `127.0.0.1` only and refuses to
  start on a non-loopback address unless `--allow-remote` *and* a token are configured.

### L-04 — DNS rebinding · High

* **Where:** whole bridge; no `Host` header validation.
* **What happens:** An attacker's domain resolves first to their server, then to `127.0.0.1`. The
  browser now considers `http://evil.example:8000` same-origin with your bridge, bypassing CORS.
* **Fix:** Middleware that rejects any request whose `Host` header is not `127.0.0.1:<port>`,
  `localhost:<port>` or `[::1]:<port>` (HTTP 421). The bearer token (L-01 fix) also defeats this.

### L-05 — Connection replacement bug · High

* **Where:** `bridge_server.py:54-68`.
  `connect()` overwrites `self.active_socket`; `disconnect()` unconditionally sets it to `None` and
  fails *all* pending futures.
* **What happens:** Extension reloads → new socket connects (becomes active) → old socket's handler
  hits `WebSocketDisconnect` → `hub.disconnect()` clears the *new* socket. The bridge now believes no
  extension is connected although one is. Also, a second browser (e.g. Firefox and Chrome both with
  the extension) silently steals all traffic.
* **Fix:** Track connections by `connectionId`. `disconnect(conn)` only removes *that* connection and
  only fails jobs assigned to it. Support multiple connected extensions explicitly (each advertises
  which providers/tabs it has; routing picks one) — see `07-bridge-server-spec.md` §4.

### L-06 — No cancellation · High

* **Where:** `bridge_server.py:92-106` (timeout → HTTP 504, nothing sent to extension);
  `extension/background.js` has no cancel handler.
* **What happens:** After a timeout, the client gets 504 but the browser tab keeps generating. The
  next request types into a tab whose previous answer is still streaming — the driver then reads the
  wrong message or the send button is disabled.
* **Fix:** Protocol message `JOB_CANCEL` (bridge → extension) sent on timeout *and* when the HTTP
  client disconnects. The driver clicks the provider's stop button, waits for idle, and reports
  `JOB_CANCELLED`. The tab is only returned to the idle pool after it is verified idle
  (`04-extension-spec.md` §5.8).

### L-07 — Reset without lock · High

* **Where:** `bridge_server.py:107-119`.
* **What happens:** `POST /api/reset` while a prompt is running clicks "new chat" mid-generation; the
  running job reads from a page that no longer contains its message.
* **Fix:** All operations on a tab go through that tab's job queue. "New chat" is a job type
  (`JOB_START` with `kind: "new_chat"`) or a flag on a prompt job (`newChat: true`).

### L-08 — Timeout race and unbounded queue wait · Medium

* **Where:** `bridge_server.py:85-95`. The extension is told `timeout = T`; the server also waits `T`.
  Time spent waiting for `self.lock` is not counted against `T` and is unbounded.
* **Fix:** Separate `queue_timeout` (how long a request may wait for a free tab; default 60 s →
  HTTP 429/503 `NO_CAPACITY`) from `generation_timeout`. The server's own deadline is
  `generation_timeout + grace (10 s)` so the extension's timeout always fires first and returns a
  typed error.

### L-09 — Hijacking the user's tab · High

* **Where:** `extension/background.js:99-105` (`tabs[0]` of any Gemini tab).
* **What happens:** If the user has Gemini open and is typing, the API types over their draft,
  submits into their conversation, and pollutes their history.
* **Fix:** Worker tabs are **claimed explicitly**: either opened by the extension itself (tracked by
  id in `storage.session`) or assigned by the user from the popup ("Use this tab for API"). A tab
  that is the active tab of a focused window is never auto-claimed. See `04-extension-spec.md` §4.

### L-10 — Tab-load wait without timeout · Medium

* **Where:** `extension/background.js:116-125`. The listener resolves only on `status === "complete"`;
  if the page errors, redirects to login, or is closed, the promise never settles and the request
  hangs until the server times out.
* **Fix:** Wait for a `CONTENT_READY` message from the content script (sent once the input is found)
  with a 30 s timeout; also listen to `tabs.onRemoved`. On timeout, classify (login page? captcha?)
  and fail with a typed error.

### L-11 — Empty answers during "thinking" · High

* **Where:** `extension/content.js:186-198`. `currentRawText === lastText` is true when both are `""`,
  so "steady for 1.2 s and no stop button" completes immediately if the stop-button selector does not
  match. Reasoning models routinely show nothing (or only a "Thinking…" header) for 5–60 s.
* **Fix:** Completion requires *positive* evidence: at least one provider-specific completion signal
  (stream closed via net tap, stop button seen-then-gone, `data-is-streaming="false"`, action toolbar
  rendered) **and** non-empty content, **or** an explicit "empty answer" signal. Text-stability is only
  a tie-breaker, never sufficient alone. See `04-extension-spec.md` §5.6.

### L-12 — Partial answers reported as success · High

* **Where:** `extension/content.js:182-202` (loop exits on timeout, then returns text);
  `session_manager.py:248-252` (logs a warning, returns partial).
* **Fix:** On timeout return error `GENERATION_TIMEOUT` with the partial text attached in
  `error.partial`. The bridge maps it to HTTP 504 (non-streaming) or, for streaming, to a final chunk
  with `finish_reason: "length"` followed by an error event (`07-bridge-server-spec.md` §6.3).

### L-13 — Wrong message picked as the answer · High

* **Where:** `extension/content.js:149-153` and `:259-261`. `findAllElements()` returns the results of
  the *first selector that matches anything*. Before sending, that may be selector #3; after sending,
  selector #1 may start matching, so `messages.length > initialCount` compares counts from different
  selectors. Generic selectors like `article` (`content.js:39`) match user turns too, so the user's own
  prompt can be returned as the "answer".
* **Fix:** Identify the answer by **identity, not count**: before submit, record the set of existing
  assistant-turn elements (a `WeakSet`) and the last turn's DOM node; after submit, the answer is the
  first assistant-turn element *not in the set* that appears after the user turn containing our prompt
  marker. Use one resolved selector for the whole job. Assistant-turn selectors must be
  role-specific (never bare `article`). See `04-extension-spec.md` §5.5.

### L-14 — Streaming ignored · High

* **Where:** `bridge_server.py:172` (`stream` accepted, never used).
* **What happens:** OpenAI SDKs with `stream=True` expect `text/event-stream` and `chat.completion.chunk`
  objects; they receive one JSON body and either crash or show nothing.
* **Fix:** Full SSE streaming end to end: the extension emits `JOB_DELTA` frames (from the net tap or
  from DOM diffing), the bridge converts them into OpenAI chunks. `07-bridge-server-spec.md` §6.2.

### L-15 — Stateless API vs stateful chat · High

* **Where:** `bridge_server.py:214-222`.
* **What happens:** OpenAI clients resend the full history on every call. The bridge pastes all of it
  as one new message into the *same* ongoing web chat. After 10 turns the web chat contains the
  history 10 times; the model sees fake `[Assistant]:` lines it never wrote; the context window fills
  quadratically; system prompts are treated as plain user text.
* **Fix:** Conversation mapping (`07-bridge-server-spec.md` §5): fingerprint the message prefix; if
  the request extends a conversation we already ran in a known web thread, send *only the new user
  message* into that thread; otherwise open a new chat and send a single well-formed transcript prompt.

### L-16 — Array content rejected · Medium

* **Where:** `bridge_server.py:164-166` (`content: str`).
* **What happens:** Many clients send `content: [{"type":"text","text":"..."}]`; Pydantic returns 422.
* **Fix:** Accept `str | list[ContentPart] | None`. Concatenate text parts; reject image parts with a
  clear `UNSUPPORTED_CONTENT` error until attachments are implemented (L-48).

### L-17 — Broken SSE in legacy streaming · Medium (legacy)

* **Where:** `server.py:248` (`yield f"data: {chunk}\n\n"` — a chunk containing `\n` ends the event
  early), `session_manager.py:346-348` (delta computed by string length; if earlier text re-renders,
  e.g. markdown reflow, deltas are wrong).
* **Fix:** Legacy is archived. In the new bridge, SSE payloads are always single-line JSON
  (`json.dumps` escapes newlines). Deltas from the DOM path are computed by common-prefix diff with a
  "replace" fallback (`06-bridge-protocol.md` §5.4).

### L-18 — Model parameter ignored · Medium

* **Where:** `extension/background.js:156`, `extension/content.js:274`, `parser.js:290`.
* **What happens:** Asking for `gemini-1.5-flash` uses whatever model the tab has selected, but the
  response says `"model": "gemini-1.5-flash"`.
* **Fix:** Model ids are `<provider>/<variant>` (e.g. `claude/default`, `chatgpt/default`). `default`
  means "whatever the tab currently uses". Explicit variants are supported only when the provider
  config defines a model-picker procedure; otherwise return `MODEL_NOT_AVAILABLE`. The response's
  `model` field reports what was actually used when detectable. `05-provider-adapters.md` §4.6.

### L-19 — Background-tab throttling · High

* **Where:** all `setTimeout`-based polling in `extension/content.js` (and inspo's
  `waitForInputElement`).
* **What happens:** Browsers throttle timers in hidden tabs: Chrome clamps to ≥1 s, and after the tab
  has been hidden ~5 minutes "intensive throttling" can delay chained timers to once per minute.
  Firefox also throttles background tabs. Some sites batch rendering with `requestAnimationFrame`,
  which does not run at all in hidden tabs, so the DOM may not even update. A worker tab opened with
  `active: false` is hidden.
* **Fix:** (1) Event-driven observation: `MutationObserver` callbacks and net-tap stream events are
  not timer-driven. (2) Use timers only for coarse deadlines. (3) Prefer the net tap, which reads the
  network stream regardless of rendering. (4) Offer an optional "worker window" mode (a separate,
  normal-size, non-minimized window holding worker tabs, each the active tab of its window, so it is
  not "hidden"). The Phase 1 spike must measure behaviour per provider in a hidden tab
  (`10-implementation-plan.md` Phase 1).

### L-20 — Long-held message replies · High

* **Where:** `extension/background.js:153-158` awaits `tabs.sendMessage` for the whole generation;
  `content.js:256-289` replies at the end.
* **What happens:** No progress information is possible (so no streaming). In Chrome MV3 the
  background is a service worker that can be terminated when idle; a held reply plus no events is
  fragile. If the page navigates, the reply never arrives.
* **Fix:** Use a long-lived `runtime.Port` per worker tab (`tabs.connect`/`runtime.onConnect`). The
  job is started with one message; the content script then *pushes* `progress`, `delta`, `done`,
  `error` messages. Port disconnection is detected immediately (tab closed/navigated).
  `04-extension-spec.md` §3.4.

### L-21 — Fake model list · Low

* **Where:** `bridge_server.py:192-202`.
* **Fix:** `/v1/models` is generated from the providers currently available through connected
  extensions (`07-bridge-server-spec.md` §6.5).

### L-22 — Fake token usage · Low

* **Where:** `parser.js:309-313`, `bridge_server.py:248-252`.
* **Fix:** Keep the estimate (clients need *something*) but mark it: add
  `"usage": {..., "estimated": true}` and document it. Never claim exactness.

### L-23 — Prompts in console logs · Medium (privacy)

* **Where:** `extension/background.js:63` logs every incoming bridge message, including prompts.
* **Fix:** A logger with levels; by default log ids, sizes and timings, never content. A "debug
  content logging" toggle in the popup, off by default.

### L-24 — Dead fallback port · Low

* **Where:** `extension/background.js:13`.
* **Fix:** One configurable bridge URL (default `ws://127.0.0.1:8787/ws`, see `07` §2), editable in
  the popup.

### L-25 — Unvalidated handshake · Medium

* **Where:** `bridge_server.py:140-144`.
* **Fix:** `HELLO` must include `protocolVersion`, `token`, `extensionVersion`, `browser`,
  `providers`. Mismatched major protocol version → close 4400 with a readable reason shown in the
  popup.

### L-26 — "New chat" opens an old chat · High

* **Where:** `extension/content.js:42` (`'a[href*="/app"]'`), also `session_manager.py:35`.
* **What happens:** On Gemini, every sidebar conversation link is `/app/<id>`, so the first match is
  often a previous conversation.
* **Fix:** New chat is done by **navigating to the provider's configured new-chat URL**
  (`newChatUrl`, e.g. `https://claude.ai/new`) — deterministic, no clicking. Clicking a button is only
  a configured fallback with exact selectors.

### L-27 — Invalid selector silently swallowed · Low

* **Where:** `extension/content.js:45`, `:65-68`.
* **Fix:** Selectors are validated when the provider config is loaded (`document.querySelector` in a
  try/catch at load time; invalid ones are reported in the health report and dropped). Runtime lookups
  never use bare `catch {}`.

### L-28 — Prompt insertion breaks the editor · High

* **Where:** `extension/content.js:96-107`.
* **What happens:** Setting `innerHTML` bypasses ProseMirror/Quill's document model. The editor may
  show the text but its internal state (what gets sent) can be empty or stale; React's send button may
  stay disabled. A single `<p>` with `textContent` containing `\n` collapses newlines — multi-line
  prompts and code arrive as one line.
* **Fix:** Port inspo's injector (`inspo/extension/content/injector.js`): synthetic `paste` event
  with `DataTransfer` first, then `execCommand("insertText")`, then range insert. Clear existing
  content first via select-all + `execCommand("delete")`. After insertion, **verify** by reading the
  editor's text back and comparing (normalised) to the prompt; on mismatch try the next strategy.
  `04-extension-spec.md` §5.3.

### L-29 — Synthetic Enter ignored · Medium

* **Where:** `extension/content.js:128-135`.
* **Fix:** Submission order: (1) click configured send button once it is enabled (wait up to 5 s for
  `disabled`/`aria-disabled` to clear); (2) dispatch the full `keydown`/`keypress`/`keyup` Enter
  sequence on the editor; (3) `form.requestSubmit()` if the editor is inside a `<form>`. Then
  **verify submission** (editor cleared, or a new user turn appeared, or the net tap saw the request);
  if not verified within 3 s, fail with `SUBMIT_FAILED`. `04-extension-spec.md` §5.4.

### L-30 — Hard-coded selectors · High (maintainability)

* **Where:** `extension/content.js:14-55`, `session_manager.py:31-35`.
* **Why it matters:** The owner's plan is for a maintainer agent to fix the extension when a site
  changes. If selectors are code, every fix is a code change + extension reload/re-publish. If they are
  data, the maintainer can push a validated override over the WebSocket within minutes.
* **Fix:** Provider config JSON + override layer. `05-provider-adapters.md` §2.

### L-31 — JSON extractor is unreliable · Medium (verified)

* **Where:** `extension/parser.js:212-246`.
* **What happens:** The fenced regex `/```(?:json)?\s*([\s\S]*?)\s*```/` matches *any* fenced block
  (python, bash…). The fallback `/(\{[\s\S]*\})/` is greedy from the first `{` to the last `}`;
  verified: input containing `{"a":1} then {"b":2}` returns `null`.
* **Fix:** Removed from the default path. If structured output is requested
  (`response_format: {"type": "json_object"}`), use a proper scanner: iterate fenced blocks tagged
  `json` first, then do a balanced-brace scan respecting strings/escapes, return the *last* valid
  top-level JSON value. Unit tests required.

### L-32 — Tool-call false positives · Medium (verified)

* **Where:** `extension/parser.js:266-274`.
* **What happens:** Verified: `"You can call:print(hello) in prose"` yields
  `[{"name":"print","rawArguments":"hello"}]`.
* **Fix:** Tool calling is a later, opt-in feature (`07-bridge-server-spec.md` §8). When enabled,
  only one strict format is recognised (a fenced block tagged `tool_call` containing JSON with
  `name` and `arguments`), and only when the request included `tools`.

### L-33 — Markdown fidelity · Medium

* **Where:** `extension/parser.js:46-185`.
* **Problems:** nested lists flatten (no indentation); text nodes keep raw whitespace/newlines from
  HTML formatting; `<del>/<s>`, `<sup>/<sub>`, `<img>`, `<br>` ignored; KaTeX/MathJax renders as
  duplicated glyph soup (they include both MathML and HTML spans); ChatGPT/Claude code blocks have a
  header bar with the language name and a "Copy" button outside `<pre>` — the button is removed but
  the label text leaks; relative links are emitted as-is; tables with `colspan` misalign.
* **Fix:** Prefer exact markdown from the net tap (where the provider streams markdown). For the DOM
  path, fix each item and add fixture tests per provider (`09-testing-strategy.md` §3). Math: read the
  TeX source from `annotation[encoding="application/x-tex"]` or `data-math`/`data-latex` attributes
  and emit `$…$` / `$$…$$`.

### L-34 — Always-on `extracted` field · Low

* **Where:** `parser.js:315-319`.
* **Fix:** Only include `web2api` extras when the client asks (`extra_body: {"web2api": {"extract": ["code_blocks"]}}`).

### L-35 — Missing content scripts in pre-existing tabs · Medium

* **Where:** `extension/background.js` assumes the content script is present.
* **What happens:** Declared content scripts are injected only into pages loaded *after* install. After
  installing or reloading the extension, existing provider tabs throw "Could not establish connection.
  Receiving end does not exist."
* **Fix:** Before using a tab, ping it; on failure inject programmatically with
  `chrome.scripting.executeScript` (Chrome / Firefox MV3) or reload the tab if it is an
  extension-owned worker tab. Note: the MAIN-world net tap must run at `document_start`, so for a
  pre-existing tab the net tap is unavailable until reload — fall back to DOM mode or reload worker
  tabs (never reload a user's tab).

### L-36 — Undetected page states · Medium

* **Fix:** Each provider config defines `states`: `loggedOut`, `captcha`, `rateLimited`,
  `error`, `modelOverloaded`, each with selectors and/or text patterns (inspo's tracker keywords are a
  starting list). The driver checks them before submit and continuously during generation, and fails
  fast with the matching error code (`LOGIN_REQUIRED`, `CAPTCHA_REQUIRED`, `RATE_LIMITED`,
  `PROVIDER_ERROR`).

### L-37 — Machine-specific path · Low

* **Where:** `start.sh:23` (`/home/suzaykid/.local/bin/uv`).
* **Fix:** Require `uv` on `PATH`; print install instructions if missing.

### L-38 — JSON injection in shell helper · Low (legacy)

* **Where:** `ask-gemini.sh:17-19`.
* **Fix:** Archived. If a CLI helper is reintroduced, build JSON with `jq -n --arg p "$PROMPT"` or
  Python.

### L-39 — Dependency hygiene · Low

* **Where:** `requirements.txt` pins `playwright`/`playwright-stealth` (only used by legacy).
* **Fix:** `bridge/pyproject.toml` with only bridge deps, `uv.lock` committed.

### L-40 — Inspo's broad fallback selectors · Medium

* **Where:** `inspo/extension/content/extractor.js:44-61`.
* **What happens:** On a page with a search box, a message-edit box, or a canvas/artifact editor, the
  first visible `textarea`/`contenteditable` may not be the composer.
* **Fix:** Generic fallbacks are restricted to the composer *region* (config `composerRoot`), and
  candidates are scored: inside a `<form>`/`fieldset`, near the send button, largest bottom-most
  visible editor, has placeholder matching provider patterns. Highest score wins; ties fail with
  `SELECTOR_AMBIGUOUS` rather than guessing.

### L-41 — Selection overrides extraction · Medium

* **Where:** `inspo/extension/content/extractor.js:141-144`.
* **Fix:** Do not port. The driver never reads `window.getSelection()`.

### L-42 — Detectability · Medium

* **Where:** inspo `content/ui.js` (appends `#cr-hud-host` to `document.body`), `injector.js:132-143`
  (writes inline `outline` on the editor), inspo manifest `web_accessible_resources` (any page can
  probe `chrome-extension://<id>/content/content.css` to detect the extension).
* **Why it matters:** Sites can (and do) look for automation fingerprints. Each one is a reason to
  flag an account.
* **Fix:** In worker tabs: inject **no DOM**, mutate **no styles**, expose **no**
  `web_accessible_resources` (the MAIN-world script is registered via the manifest `world: "MAIN"`
  field, which does not require web-accessible resources), and keep the MAIN-world footprint minimal
  (wrap `fetch` with a function whose `toString()` matches native, communicate via `window.postMessage`
  with a per-load random channel id). See `08-security.md` §5.

### L-43 — Teleport key collision · Low

* **Where:** `inspo/extension/background/service-worker.js:23`.
* **Fix:** Our equivalent (pending jobs for freshly opened tabs) is keyed by `tabId` and `jobId`.

### L-44 — Storage race · Low

* **Where:** `inspo/extension/utils/storage.js:53-68`.
* **Fix:** All writes to shared state go through the background script (single writer). Content
  scripts never write `storage` directly.

### L-45 — Untrusted model output · Medium

* **Why it matters:** The answer text comes from a remote model that can be prompt-injected by
  content it read. Today it's only returned to the client, but future features (tool calling, the
  maintainer, MCP) will act on it.
* **Fix:** The extension never executes, navigates to, or clicks anything based on answer content.
  Popup renders answers with `textContent` only. Tool calls (future) are returned to the API client,
  never executed by Web2API itself.

### L-46 — Popup bypasses serialisation · High

* **Where:** `extension/background.js:235-250` (`RUN_POPUP_PROMPT` sends directly to the tab, outside
  the bridge's lock).
* **Fix:** All prompt executions — API or popup — go through the extension's per-tab job queue
  (`04-extension-spec.md` §4.3). The popup test feature submits a job like any other.

### L-47 — Terms of Service / account risk · Informational

Automating a consumer chat website with a script is very likely against the provider's terms, and
providers do rate-limit, challenge, or suspend accounts that look automated. This spec minimises
fingerprints and request rates (one job per tab, human-plausible pacing, no headless browser) but
cannot remove the risk. The README must state this plainly and recommend not using an account the
owner can't afford to lose. Add a configurable minimum delay between jobs per provider (default 3 s).

### L-48 — No attachments · Low

* **Fix (later phase):** Image/file parts → inject as a synthetic `paste`/`drop` event with a `File`
  in the `DataTransfer` (works on most editors). Out of scope for v1; return `UNSUPPORTED_CONTENT`.

### L-49 — Content outside the message element · Medium

* **Examples:** Gemini "Show drafts" alternatives; ChatGPT's occasional side-by-side "Which response
  do you prefer?" (two answers, one must be chosen); Claude artifacts (rendered in a side panel, only a
  card in the message); ChatGPT canvas; images generated inline; "search results" cards.
* **Fix:** Provider configs list these as `states` with handling policies: for A/B comparisons, pick
  the first response and click its "prefer" button (configurable) or fail with `PROVIDER_INTERRUPT`;
  for artifacts/canvas, extract from the net tap (which carries the artifact source) or report
  `"web2api": {"warnings": ["artifact_not_extracted"]}`.

### L-50 — Non-OpenAI error schema · Low

* **Where:** all `HTTPException` uses in `bridge_server.py`.
* **Fix:** Custom exception handler that returns
  `{"error": {"message": ..., "type": ..., "code": ..., "param": null}}` with the right status code
  (`07-bridge-server-spec.md` §7).
