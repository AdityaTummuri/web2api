# 04 — Browser Extension Specification

This is the detailed behavioural spec for every part of the extension. Read `03-target-architecture.md`
first for the big picture and directory layout. The wire protocol to the bridge is in
`06-bridge-protocol.md`; provider config format is in `05-provider-adapters.md`.

---

## 1. Platform targets

| Browser | Minimum version | Background type | Why this minimum |
|---|---|---|---|
| Chrome / Chromium / Edge / Brave | 116 | `background.service_worker` (ES module) | WebSocket activity extends service-worker lifetime from 116; `world: "MAIN"` content scripts from 111. |
| Firefox | 128 | `background.scripts` (event page, ES module via `"type": "module"`) | `world: "MAIN"` content scripts from 128. |

Use the `chrome.*` namespace everywhere. Firefox supports `chrome.*` with promise-returning APIs in
MV3. Do **not** add the `webextension-polyfill`. Where a Firefox-only capability is used
(e.g. `browser.webRequest.filterResponseData`), guard it with feature detection and keep it optional.

---

## 2. Manifests and build

### 2.1 `manifests/base.json`

```json
{
  "manifest_version": 3,
  "name": "Web2API",
  "version": "0.1.0",
  "description": "Use the AI chat sites you are logged into as a local OpenAI-compatible API.",
  "icons": { "48": "icons/icon-48.png", "96": "icons/icon-96.png" },
  "action": { "default_popup": "popup/popup.html", "default_title": "Web2API" },
  "permissions": ["storage", "tabs", "scripting", "alarms"],
  "host_permissions": [],
  "content_scripts": []
}
```

* `host_permissions` and `content_scripts` are **generated** by `scripts/build.mjs` from the provider
  configs (see §2.3). Never edit them by hand in `dist/`.
* No `web_accessible_resources` (L-42).
* No `externally_connectable` (would let provider pages message the extension).

### 2.2 Browser overlays

`manifests/chrome.json`
```json
{
  "minimum_chrome_version": "116",
  "background": { "service_worker": "background/main.js", "type": "module" }
}
```

`manifests/firefox.json`
```json
{
  "background": { "scripts": ["background/main.js"], "type": "module" },
  "browser_specific_settings": {
    "gecko": { "id": "web2api@local", "strict_min_version": "128.0" }
  }
}
```

### 2.3 `scripts/build.mjs`

Node ≥ 20 script, no dependencies. Usage: `node scripts/build.mjs chrome|firefox|all`.

Steps:
1. Delete and recreate `dist/<browser>/`.
2. Copy `src/**` into `dist/<browser>/` preserving paths (so `src/background/main.js` →
   `dist/<browser>/background/main.js`). Copy `icons/` too.
3. Read `src/providers/index.json` → list of provider ids. For each, read `src/providers/<id>.json`,
   validate it against `src/providers/schema.json` (write a ~100-line minimal validator for the subset
   of JSON Schema used, or validate structurally in code — do not add a dependency). Fail the build on
   invalid configs with a readable message.
4. `host_permissions` = union of every provider's `match.hostPermissions` (e.g. `"https://claude.ai/*"`).
5. Generate **two** `content_scripts` entries per provider:
   ```json
   {
     "matches": ["https://claude.ai/*"],
     "js": ["providers/parsers/sse.js", "providers/parsers/claude.js",
            "providers/generated/claude.nettap.js", "main-world/net-tap.js"],
     "run_at": "document_start",
     "world": "MAIN",
     "all_frames": false
   },
   {
     "matches": ["https://claude.ai/*"],
     "js": [
       "shared/protocol.js", "shared/logger.js", "shared/util.js",
       "content/dom.js", "content/injector.js", "content/submitter.js", "content/observer.js",
       "content/completion.js", "content/states.js", "content/extract/markdown.js",
       "content/nettap-relay.js", "content/snapshot.js", "content/driver.js", "content/bootstrap.js"
     ],
     "run_at": "document_start",
     "all_frames": false
   }
   ```
   * The MAIN-world entry is only emitted if the provider config has `netTap.enabled: true` and a
     parser file exists. Parser file list comes from `netTap.parsers` (array of names, `sse` is common).
   * `providers/generated/<id>.nettap.js` is **generated** by the build: it registers the provider's
     `netTap.endpoints` array (data copied from the config JSON) on the registration hook (§6.2), so
     the MAIN world knows which URLs to observe without reading extension storage.
   * The build also generates `content/provider-hosts.js` (host regex → provider id, §5.1) and puts it
     first in every isolated-world list.
   * The isolated entry runs at `document_start` so `nettap-relay.js` can complete the MessageChannel
     handshake (§6.4) before page scripts run. `bootstrap.js` itself waits for `DOMContentLoaded`
     before touching the DOM.
6. Merge `base.json` + overlay + generated fields, write `dist/<browser>/manifest.json`.
7. Print a summary: providers included, host permissions, file count.

`package.json` scripts:
```json
{
  "scripts": {
    "build": "node scripts/build.mjs all",
    "build:chrome": "node scripts/build.mjs chrome",
    "build:firefox": "node scripts/build.mjs firefox",
    "test": "node --test tests/unit tests/dom"
  },
  "devDependencies": { "jsdom": "^24.0.0" }
}
```

Loading for development:
* Chrome: `chrome://extensions` → Developer mode → Load unpacked → `extension/dist/chrome`.
* Firefox: `about:debugging#/runtime/this-firefox` → Load Temporary Add-on → `extension/dist/firefox/manifest.json`.

### 2.4 Sharing code between background, content and popup

* `src/shared/*.js` files must work both as classic scripts (content scripts) and as ES modules
  (background, popup). Pattern:
  ```js
  // shared/protocol.js
  (function (root) {
    const W2A = (root.W2A = root.W2A || {});
    W2A.protocol = { PROTOCOL_VERSION: 1, MSG: { /* ... */ }, ERR: { /* ... */ } };
  })(globalThis);
  ```
  The background imports it for side effects: `import "../shared/protocol.js";` then uses
  `globalThis.W2A.protocol`. This keeps one file, no bundler.
* Content scripts all attach to `globalThis.W2A` (isolated world — invisible to the page).
* MAIN-world scripts attach to a **closure-scoped** object, never to `window`, except the single
  registration hook described in §6.2, which is deleted after use.

---

## 3. Background script

### 3.1 `background/main.js` — entry point

Responsibilities, in order:
1. `import` shared modules and all background modules.
2. Register **all** event listeners synchronously at top level (MV3 requirement: listeners registered
   later are missed when the worker is woken by an event): `runtime.onInstalled`, `runtime.onStartup`,
   `runtime.onConnect` (tab Ports), `runtime.onMessage` (popup requests), `tabs.onRemoved`,
   `tabs.onUpdated`, `alarms.onAlarm`.
3. Call `await state.restore()` (reload session state, §3.2), then `configStore.init()`,
   `tabPool.init()`, `bridgeClient.start()`.
4. Create alarm `w2a-watchdog` with `periodInMinutes: 1`. On alarm: if the bridge client is not
   connected and not currently connecting, `bridgeClient.start()`; run `tabPool.reconcile()`.

### 3.2 State persistence (survive service-worker restarts)

All background state that must survive a worker restart lives in `chrome.storage.session` under these
keys (session storage is in-memory, cleared on browser restart — correct for tab ids):

| Key | Shape | Written by |
|---|---|---|
| `pool.tabs` | `{ [tabId]: { provider, origin: "opened"|"assigned", windowId, state: "idle"|"busy"|"dirty"|"loading", threadUrl, jobId|null, lastUsedAt } }` | tab-pool |
| `jobs.active` | `{ [jobId]: { provider, tabId|null, phase, startedAt, deadlineAt } }` | job-runner |

Persistent settings live in `chrome.storage.local`:

| Key | Shape |
|---|---|
| `settings` | see §10 |
| `config.overrides` | `{ [providerId]: { version, appliedAt, source, patch } }` (see `05` §2.4) |
| `health.reports` | ring buffer (max 50) of health/failure reports (no prompt text; see §9) |
| `health.snapshots` | ring buffer (max 10) of `{ id, provider, createdAt, html (≤ 2 MB), reason }` |

**Rule:** only the background writes storage (single writer, avoids L-44). Content scripts and the
popup ask the background via messages.

On restart, jobs found in `jobs.active` are failed with `EXTENSION_RESTARTED` (sent once the bridge
reconnects), and their tabs are marked `dirty` (the driver in the tab will have lost its Port; the
tab-pool will re-verify them).

### 3.3 `background/bridge-client.js`

```
state machine:  idle → connecting → authenticating → ready
                  ▲         │              │            │
                  └─────────┴──── backoff ◄┴────────────┘ (on close/error)
```

* URL from `settings.bridgeUrl` (default `ws://127.0.0.1:8787/ws/extension`).
* On open: send `HELLO` (fields in `06-bridge-protocol.md` §3.1) including `settings.pairingToken`. If
  the token is empty, do not connect; set status `needs_pairing` (popup shows instructions).
* Wait ≤ 5 s for `WELCOME`. On `WELCOME`: state `ready`, reset backoff, send `PROVIDERS_UPDATE`
  (§4.6) immediately.
* On close code 4401 (bad token) or 4400 (protocol mismatch): **stop reconnecting** and surface the
  reason in the popup/badge until settings change. Other closes: exponential backoff with jitter
  (1 s, 2 s, 4 s … cap 30 s).
* Keepalive: every 20 s while `ready`, send `PING {ts}`; expect `PONG` within 10 s else close and
  reconnect. (This ping traffic is also what keeps the Chrome service worker alive, D3.)
* **Firefox lifetime check:** the Phase 1 spike must confirm the event page is not suspended while
  the socket is open and idle. If it is, additionally call `chrome.runtime.getPlatformInfo()` in the
  20 s keepalive tick (extension API calls reset the idle timer).
* Incoming frames are parsed with `JSON.parse` in try/catch; invalid frames are logged (type only) and
  ignored. Dispatch by `type` to job-runner / config-store / health.
* Outgoing: `send(frame)` serialises; if not `ready`, frames of type `JOB_*` are buffered (max 200,
  max 60 s) and flushed on reconnect; `JOB_DELTA` frames older than 60 s are dropped in favour of the
  final `JOB_DONE` (which always carries the full text).

### 3.4 Background ↔ content script channel (internal, not the bridge protocol)

Each worker tab's content script opens a Port: `chrome.runtime.connect({ name: "w2a-tab" })`.
The background tracks `portsByTabId`. Messages are plain objects with `t` (type):

| Direction | `t` | Fields | Meaning |
|---|---|---|---|
| tab → bg | `ready` | `provider, url, loggedIn, composerFound, netTapActive, threadId|null, pageState` | Sent after bootstrap finishes (and again after SPA navigations). |
| tab → bg | `state` | `pageState` (`ok`/`logged_out`/`captcha`/`rate_limited`/`error`) | Page state changed while idle. |
| bg → tab | `run` | `job` (see below) | Start a job. |
| bg → tab | `cancel` | `jobId` | Cancel the running job. |
| bg → tab | `probe` | `probeId, checks` | Run health checks (§9). |
| bg → tab | `snapshot` | `requestId, reason` | Return a sanitised DOM snapshot. |
| bg → tab | `config` | `config` | Effective provider config (sent on connect and on override change). |
| tab → bg | `progress` | `jobId, phase, detail` | Phase changes: `preflight`, `injecting`, `submitting`, `waiting_first_token`, `generating`, `finalizing`. |
| tab → bg | `delta` | `jobId, seq, kind: "text"|"reasoning", text, source: "net"|"dom"` | Incremental text. |
| tab → bg | `done` | `jobId, text, reasoning|null, finishReason, threadUrl, threadId, modelLabel|null, source, warnings[]` | Job completed. |
| tab → bg | `error` | `jobId, code, message, detail, partialText|null` | Job failed. |
| tab → bg | `cancelled` | `jobId, partialText|null` | Cancel completed. |
| tab → bg | `probeResult` | `probeId, results` | Health check results. |
| tab → bg | `snapshotResult` | `requestId, html, meta` | Snapshot. |

`job` object sent with `run`:
```js
{
  jobId: "job_01J...",
  provider: "claude",
  promptText: "…",               // exact text to type
  target: { mode: "new" } | { mode: "continue", threadUrl: "https://claude.ai/chat/…" } | { mode: "current" },
  modelVariant: "default",       // or a configured variant id
  historyMode: "normal" | "temporary",
  timeouts: { firstTokenMs: 60000, totalMs: 300000, stallMs: 90000 },
  stream: true,                   // whether to emit deltas
  wantReasoning: false
}
```

Port disconnect handling: if a tab's Port disconnects while it has a running job → job-runner emits
`JOB_ERROR` with `TAB_LOST` (if the tab is gone) or `PAGE_NAVIGATED` (if the tab still exists) and
marks the tab `dirty`.

Navigation note: when the background navigates a worker tab (new chat / thread URL), the old content
script dies and a new one connects. The job-runner must therefore send `run` **after** the new
`ready` arrives — never before navigation completes. See §4.4.

### 3.5 `background/job-runner.js`

Responsibilities:
1. Handle `JOB_START` from the bridge: validate fields (unknown provider → `PROVIDER_UNAVAILABLE`;
   provider disabled → same), create job record, reply `JOB_ACCEPTED { jobId, queuePosition }`.
2. `tabPool.acquire(provider, job)` → resolves with a ready tab (may open/navigate one) or rejects
   with a typed error (`NO_CAPACITY` after `settings.queueTimeoutMs`, `LOGIN_REQUIRED`, …).
3. Send `run` over the tab's Port; relay `progress/delta/done/error/cancelled` to the bridge as
   `JOB_PROGRESS/JOB_DELTA/JOB_DONE/JOB_ERROR/JOB_CANCELLED`.
4. Enforce a background-side hard deadline = `timeouts.totalMs + 15 s` (in case the content script
   hangs): on expiry send `cancel` to the tab, wait 10 s, then emit `JOB_ERROR(GENERATION_TIMEOUT)`
   and mark the tab `dirty`.
5. Handle `JOB_CANCEL` from the bridge: if queued → remove from queue, emit `JOB_CANCELLED`; if
   running → send `cancel` to the tab.
6. On completion of any kind: `tabPool.release(tabId, outcome)`.
7. Increment counters for the popup (`stats` in memory, mirrored to `storage.session`).

Use `chrome.alarms` is **not** suitable for sub-minute deadlines; use `setTimeout` in the background
(background contexts are not subject to tab timer throttling). Because the Chrome worker may restart,
deadlines are also stored in `jobs.active` and re-checked by the watchdog alarm.

---

## 4. Tab pool (`background/tab-pool.js`)

### 4.1 Concepts

* **Worker tab** = a tab in `pool.tabs`. Two origins:
  * `opened` — created by the pool. The pool may navigate, reload, and close it.
  * `assigned` — an existing tab the user assigned via the popup ("Use this tab for API"). The pool
    may navigate it (user consented), but **never closes or reloads it**.
* A tab not in `pool.tabs` is **never** touched by jobs (fixes L-09). Exception: none.
* Per provider: `settings.providers[id].poolSize` (default 1, max 4).

### 4.2 Tab states

```
            open/assign
               │
               ▼
          ┌─ loading ──(ready msg, composer found, logged in)──► idle ◄──────────────┐
          │      │                                                │                  │
          │      └─(timeout 30s / login page / captcha)──► dirty  │ acquire          │ release(ok)
          │                                                 │     ▼                  │ + min delay
          │                                     verify/recover   busy ───────────────┘
          │                                                 │     │
          └───────────────── navigate ◄─────────────────────┘     └─ release(failed) ──► dirty
```

* `dirty` tabs are re-verified before reuse: send `probe` for `composer.input` + page state; if
  generation is still running (stop button visible), send `cancel` first; if verification fails and
  the tab is `opened`, navigate to `newChatUrl`; if it's `assigned`, mark the provider unhealthy and
  notify the popup.

### 4.3 Queueing and fairness

* Per-provider FIFO queue of pending jobs.
* `acquire()` picks an idle tab whose `threadUrl` matches `job.target.threadUrl` if continuing a
  thread (affinity), else any idle tab, else opens a new tab if under `poolSize`, else waits in queue.
* Enforce `settings.providers[id].minDelayMs` (default 3000) between the end of one job and the start
  of the next **in the same tab** (L-47).
* Queue timeout `settings.queueTimeoutMs` (default 60000) → reject with `NO_CAPACITY`.
* Popup test prompts use the same queue (fixes L-46).

### 4.4 Preparing a tab for a job (navigation)

Given `job.target`:
* `{mode:"current"}` — use the tab as is (only valid for `assigned` tabs; used by the popup test and
  by explicit API requests with `web2api.thread: "current"`).
* `{mode:"continue", threadUrl}` — if `tab.url` (normalised: strip query/hash) equals `threadUrl` and
  the tab is idle → use as is. Else `chrome.tabs.update(tabId, {url: threadUrl})` and wait for `ready`.
* `{mode:"new"}` — navigate to `config.urls.newChat` (or `config.urls.newChatTemporary` if
  `historyMode === "temporary"` and defined). Always navigate (never click a "new chat" button) unless
  the config sets `urls.newChatStrategy: "click"` with explicit selectors (L-26).

Waiting for `ready`: resolve when the tab's Port posts `ready` with `composerFound: true` and
`pageState: "ok"`. Reject on 30 s timeout, `tabs.onRemoved`, or `ready` with a bad `pageState`
(map `logged_out`→`LOGIN_REQUIRED`, `captcha`→`CAPTCHA_REQUIRED`, `rate_limited`→`RATE_LIMITED`).

### 4.5 Opening tabs and the worker window (D8)

* `settings.workerWindowMode`:
  * `"dedicated"` (default): ensure a window exists with id stored in `storage.session` key
    `pool.windowId`; create with
    `chrome.windows.create({ url, focused: false, state: "normal", width: 1000, height: 900 })`.
    Additional worker tabs: `chrome.tabs.create({ windowId, url, active: false })`. Before running a
    job in a tab, make it the active tab of that window
    (`chrome.tabs.update(tabId, {active: true})`) — this does not focus the window or steal OS focus.
    If two providers run jobs simultaneously in the same window, only one tab can be active; therefore
    with pool sizes > 1 or multiple providers, create **one window per busy worker** lazily, up to
    `settings.maxWorkerWindows` (default 3); beyond that, fall back to background tabs.
  * `"background-tabs"`: `chrome.tabs.create({ url, active: false, pinned: true })` in the last
    focused normal window.
* Firefox may refuse `focused: false` on window creation in some versions; ignore the error and
  continue (the window may take focus once).
* If the user closes the worker window, all its tabs are removed from the pool (`tabs.onRemoved`);
  running jobs fail with `TAB_LOST`.

### 4.6 Provider availability report

Whenever the pool state changes meaningfully (tab ready/lost, login state change, health change), the
pool computes and the bridge client sends `PROVIDERS_UPDATE`:
```js
{ providers: [ { id: "claude", enabled: true, status: "ready"|"degraded"|"login_required"|"no_tabs"|"unhealthy",
                 tabs: { idle: 1, busy: 0, total: 1 }, canOpenTabs: true,
                 variants: ["default", ...], configVersion: "2026.10.20-1", netTap: true } ] }
```
A provider with zero tabs but `canOpenTabs: true` is still *available* (the pool opens a tab on
demand) — report `status: "no_tabs"`; the bridge treats it as routable.

### 4.7 Content-script presence (L-35)

When a tab is assigned or found without a Port: send nothing; instead call
`chrome.scripting.executeScript({ target: {tabId}, files: [<isolated content script list>] })`.
The MAIN-world net tap cannot be retro-injected at `document_start`; for `opened` tabs, reload the tab
instead (so the net tap is present); for `assigned` tabs, run in DOM-only mode and show a hint in the
popup ("reload this tab to enable exact streaming").

---

## 5. Content-script driver

### 5.1 `content/bootstrap.js`

1. Determine provider: iterate effective configs (bundled copy is available synchronously because the
   background also sends `config` over the Port, but bootstrap needs the provider id first — so the
   build script writes a tiny generated `content/provider-hosts.js` with `{hostRegex → providerId}`;
   include it first in the isolated script list). If no match → do nothing.
2. Guard against double injection: `if (globalThis.W2A?.booted) return; W2A.booted = true;`
3. Open Port `w2a-tab`, wait for `config` message (≤ 5 s; if it doesn't arrive, disconnect and retry
   once).
4. Wait for `DOMContentLoaded` if needed, then `dom.waitFor(config.selectors.composer.input, 20000)`.
5. Evaluate page state via `states.evaluate()`.
6. Post `ready`. Re-post `ready` after SPA navigations. The page's own `history.pushState` calls
   cannot be intercepted from the isolated world (wrapping `history.pushState` there only wraps the
   isolated world's view of it). Instead, compare `location.href` with the last seen value inside the
   MutationObserver callback that already watches `document.body` (SPA route changes always mutate
   the DOM) — a cheap string comparison, no timers. Also listen to `popstate`.
7. Register the Port message handler that dispatches `run`, `cancel`, `probe`, `snapshot`, `config`.

### 5.2 `content/dom.js` — element resolution

**Selector entries** (from config, see `05` §3.2) are objects:
```json
{ "css": "div.ProseMirror[contenteditable='true']", "within": "composer.root", "visible": true, "nth": "last", "text": null, "attr": null }
```
or a list of such entries tried in order (**tiers**). A bare string is shorthand for `{ "css": "<string>" }`.

`resolve(key, opts)`:
1. Look up `config.selectors` by dotted key (`"composer.input"`).
2. For each tier in order: compute the scope (`within` → resolve that key first, else `document`),
   `scope.querySelectorAll(css)`, filter by `visible` (if true, use the visibility check below), by
   `text` (regex against `textContent`, case-insensitive), by `attr` (`{name: regex}`), then pick by
   `nth` (`"first"` default, `"last"`, or an integer).
3. Return `{ el, tier, css }` for the first tier yielding an element, or `null`.
4. Record a resolution metric: `key → tier index used` (health uses it: falling to tier 3 means
   tier 1 broke — an early warning for the maintainer).

Visibility check (from inspo `_isElementVisible`, extended):
```js
function isVisible(el) {
  if (!el || !el.isConnected) return false;
  const s = getComputedStyle(el);
  if (s.display === "none" || s.visibility === "hidden" || Number(s.opacity) === 0) return false;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0;
}
```
(In hidden tabs layout still computes, so this works.)

`waitFor(key, timeoutMs, {predicate})`: resolves when `resolve(key)` returns an element (and optional
predicate passes). Implementation: try immediately; else a `MutationObserver` on `document.documentElement`
(`childList, subtree, attributes`) re-checks on each callback (coalesce: at most one check per
animation-independent microtask burst, i.e. set a flag and check in `queueMicrotask`); reject on
timeout via a single `setTimeout` (coarse deadline only — L-19).

Composer scoring for generic fallbacks (L-40): if a tier is marked `"score": true`, gather all
candidates instead of the first, and score: +3 inside `composer.root`, +2 inside a `form` or
`fieldset`, +2 bottom-most visible, +1 has a placeholder/aria-label matching
`config.composer.placeholderPattern`, +1 a send-button candidate within 200 px. Highest score wins; if
the top two tie, return `null` with `reason: "ambiguous"`.

### 5.3 `content/injector.js` — inserting the prompt (adapted from inspo)

Contract: `async insert(editorEl, text, strategies) → { ok, strategy, mismatch? }`.

Step 0 — focus: `editorEl.focus()`. Do **not** `scrollIntoView` with smooth behaviour, do **not**
change styles (inspo's outline pulse is removed — L-42).

Step 1 — clear existing draft:
* `contenteditable`: select all inside the editor (`Range.selectNodeContents(editorEl)`, set
  selection) then `document.execCommand("delete")`. If the editor still has text, fall back to
  dispatching `beforeinput` with `inputType: "deleteContentBackward"` after select-all.
* `textarea`/`input`: `el.select(); document.execCommand("delete")`, fallback to the native value
  setter (`Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set.call(el, "")`)
  + `input` event — the native setter is required for React-controlled inputs.

Step 2 — insert, trying `strategies` in order (config `composer.insertStrategies`, default
`["paste", "execCommand", "range"]` for contenteditable, `["execCommand", "nativeSetter"]` for
textarea):
* `paste`: `const dt = new DataTransfer(); dt.setData("text/plain", text);` dispatch
  `new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true })` on the editor.
  ProseMirror (ChatGPT, Claude) and Quill (Gemini) handle this through their own clipboard pipelines
  and preserve newlines as paragraphs. Note: in Firefox, the `clipboardData` init option may be
  ignored for synthetic events; if `event.clipboardData` is null after construction, skip this
  strategy.
* `execCommand`: `document.execCommand("insertText", false, text)`.
* `range`: insert a text node at the collapsed selection and dispatch
  `new InputEvent("input", { bubbles: true, inputType: "insertText", data: text })`.
* `nativeSetter`: native value setter + `input` + `change` events.

Step 3 — verify (fixes L-28): after each strategy, wait one macrotask (`await new Promise(r => setTimeout(r, 0))` —
acceptable even if throttled to 1 s in hidden tabs; it's once), then read the editor text
(`editorEl.innerText` for contenteditable, `.value` for textarea), normalise both sides
(`\r\n→\n`, collapse runs of blank lines, trim, NBSP→space) and compare. Success if equal, or if the
editor text contains the normalised prompt and is at most 2 % longer (editors sometimes add trailing
newlines). On mismatch, clear and try the next strategy. If all fail → error `INPUT_REJECTED`
with `detail: {strategiesTried, lastEditorTextLength}`.

Very long prompts: some editors are slow with `insertText` on >50 k characters; `paste` is fastest.
If `text.length > config.composer.maxChars` (if defined) → fail early with `PROMPT_TOO_LONG`.

### 5.4 `content/submitter.js` — sending

1. Wait up to 5 s for `selectors.composer.send` to resolve **and** be enabled
   (`!el.disabled && el.getAttribute("aria-disabled") !== "true"`).
2. Record pre-submit markers (see §5.5) **before** clicking.
3. Trigger, by `config.composer.submitStrategies` order (default `["click", "enter", "formSubmit"]`):
   * `click`: `el.click()`.
   * `enter`: on the editor dispatch `keydown`, `keypress`, `keyup` with
     `{ key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true }`.
   * `formSubmit`: `editorEl.closest("form")?.requestSubmit()`.
4. Verify within 3 s (any of): net tap reports a matching request started; a new user-turn element
   appeared; the editor became empty; the stop button appeared. If none → try the next strategy
   (only if the editor still contains the prompt, to avoid double sending). All fail → `SUBMIT_FAILED`.

### 5.5 `content/observer.js` — identifying *our* answer (fixes L-13)

Before submit:
* `before = new WeakSet(document.querySelectorAll(resolvedAssistantTurnCss))` using the **css string of
  the tier that resolves** `selectors.turns.assistant` at this moment — the same css is then used for
  the whole job.
* Also record `beforeUserTurns` similarly with `selectors.turns.user`.

After submit:
* Our user turn = first element matching `turns.user` not in `beforeUserTurns`. If the config defines
  no user-turn selector, skip.
* Our assistant turn = first element matching the job's assistant css that is **not** in `before` and
  (if our user turn is known) follows it in document order
  (`userTurn.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING`).
* Wait for it with `waitFor`, up to `timeouts.firstTokenMs`. Timeout → `NO_RESPONSE` (with state
  check first: a rate-limit banner turns this into `RATE_LIMITED`).
* Answer content element = `selectors.answer.content` resolved **within** the assistant turn
  (e.g. `.markdown` inside it). Exclusions (`selectors.answer.exclude`, e.g. thinking blocks, citations,
  toolbars) are removed from a clone at extraction time, not from the live DOM.

Edge: some SPAs **replace** the assistant node during streaming (re-mount). If the tracked node becomes
disconnected (`!el.isConnected`), re-run the identification (new nodes not in `before`, after the user
turn) and continue.

### 5.6 `content/completion.js` — knowing when the answer is done (fixes L-11, L-12)

The config lists signals (`05` §3.5). Each signal is evaluated on every observation tick (Mutation
callback or net-tap event). Signal types:

| Type | Fires when | Strength |
|---|---|---|
| `netDone` | Net tap reported `done` for the stream bound to this job. | strong |
| `attrEquals` | An attribute on a resolved element equals a value (e.g. `data-is-streaming="false"` on the assistant turn). | strong |
| `appears` | A selector (usually within the assistant turn) resolves (e.g. the action toolbar with copy/retry buttons). | strong |
| `disappears` | A selector that **was seen during this job** no longer resolves (e.g. stop button). If it was never seen, this signal can only fire after `neverSeenGraceMs` (default 8000) *and* content is non-empty. | strong (if seen), weak (grace) |
| `sendReady` | Send button is present and enabled while the editor is empty. | weak |
| `textStable` | Answer markdown unchanged for `ms`. | weak (tie-breaker only) |

**Decision rule:**
```
done ⇔ (at least one STRONG signal fired)
       AND (answer text non-empty OR config.completion.allowEmpty)
       AND (textStable for config.completion.settleMs, default 600 ms)
```
* `settleMs` avoids cutting the last few tokens that render after the stream closes.
* Text stability alone **never** completes a job.
* **Stall detection:** if no DOM mutation inside the assistant turn and no net-tap event for
  `timeouts.stallMs` (default 90 s) and no strong signal → evaluate states; if a known state matches,
  fail with its code; else fail `GENERATION_STALLED` with `partialText`.
* **Total timeout:** `timeouts.totalMs` (default 300 s) → `GENERATION_TIMEOUT` with `partialText`.
* Implementation of time-based checks: because timers may be throttled in hidden tabs, compute
  `textStable` from timestamps recorded in mutation callbacks (`lastChangeAt`); schedule a single
  `setTimeout(check, settleMs)` after each change. If throttled to 1 s, completion is merely ~1 s later
  — acceptable. Net-tap `done` events trigger an immediate check.

**Reasoning / thinking models:** thinking content is excluded from the answer via
`selectors.answer.exclude` (DOM) or emitted as `kind: "reasoning"` deltas (net tap). Thinking phases
do not count toward stall detection while a `thinking` indicator selector (config
`selectors.status.thinking`) is visible.

### 5.7 Extraction (`content/extract/markdown.js`)

Order:
1. If the net tap delivered a complete stream (`netDone` fired and the parser reported text), use the
   net-tap text (exact markdown). `source: "net"`.
2. Else DOM: clone the answer content element, remove `answer.exclude` selectors and the global noise
   list (buttons, `svg`, `[aria-hidden="true"]` icons, `.sr-only`), convert with `domToMarkdown`.
   `source: "dom"`.
3. In debug mode with both available: compute similarity (normalised Levenshtein on the first 5 k
   chars or line-set Jaccard) and add `warnings: ["net_dom_divergence:<score>"]` if < 0.9. This is a
   cheap, continuous check of parser health.

`domToMarkdown` requirements (evolve `extension/parser.js`; fix L-33):
* Block elements: `p, div(block), h1–h6, blockquote, ul/ol/li (nested with 2/3-space indentation per
  level; ordered lists honour the `start` attribute), pre/code, table, hr, br`.
* Inline: `strong/b → **x**`, `em/i → *x*`, `del/s → ~~x~~`, `code → \`x\`` (use longer backtick
  fences if `x` contains backticks), `a → [text](absolute href)` (resolve relative to `location.href`;
  drop `javascript:` links, keep text), `img → ![alt](src)` (only http(s) src; skip data: URLs > 1 kB),
  `sup/sub → ^x^/~x~` only if config enables, else plain text.
* Code blocks: language from (in order) `code[class*="language-"]`, `[data-language]` on `pre` or an
  ancestor within 2 levels, a header label selected by `selectors.answer.codeLanguageLabel` (config);
  remove the header element itself (configured via `selectors.answer.codeHeader`) so its text does not
  leak. Code text from `textContent` (not `innerText`, which can drop leading whitespace in some
  renderers), `\r\n→\n`, strip one trailing newline. Fence with ``` unless the code contains ```,
  then use ````.
* Math: if an element has `annotation[encoding="application/x-tex"]` → inline `$tex$` or display
  `$$\ntex\n$$` (display if the element or ancestor has `display="block"`/`katex-display`). Also honour
  `data-math`/`data-latex` attributes. Remove the rendered glyph spans.
* Whitespace: collapse runs of whitespace in text nodes to a single space **except** inside `pre`;
  trim spaces around block boundaries; at the end collapse 3+ newlines to 2.
* Tables: header row from `thead tr` or first row; escape `|`; `colspan` → repeat empty cells.
* Unknown elements: recurse into children.
* Must be pure (no globals besides DOM interfaces) so it can be unit-tested with jsdom.

### 5.8 Cancellation

On `cancel`:
1. Resolve `selectors.composer.stop`; if found and visible → `click()`.
2. Wait (MutationObserver) up to 10 s for the completion engine to see idle (stop button gone or
   `sendReady`).
3. Post `cancelled { jobId, partialText }`.
4. If still not idle after 10 s → post `error { code: "CANCEL_FAILED" }`; the pool marks the tab dirty
   (and, if `opened`, navigates it to `newChatUrl`).

### 5.9 DOM-path streaming deltas

When `job.stream` is true and the net tap is not active for this job:
* On each assistant-turn mutation (coalesced to at most one extraction per 150 ms using `lastExtractAt`
  timestamps), compute `md = domToMarkdown(clone)`.
* **Stable-prefix policy:** only emit text up to the last safe boundary: the last `\n\n` that is not
  inside an unclosed code fence (count ``` occurrences) — the tail after it is still volatile because
  markdown conversion of half-rendered content changes.
* `delta = safe.slice(emittedLength)` if `safe.startsWith(emitted)`; else (earlier text changed — rare)
  emit nothing more during streaming and set warning `stream_divergence`; the final `done.text` is
  authoritative.
* `seq` increments per delta; the bridge reorders/de-dupes by `seq`.

### 5.10 `content/states.js` — page states (fixes L-36)

`evaluate()` checks, in order, `config.states.<name>` for `captcha`, `loggedOut`, `rateLimited`,
`error`, `interrupt` (each: list of selector entries and/or `textPatterns` searched only within
`config.states.<name>.scope` elements — never `document.body.innerText`, which is slow and forces
layout). Returns the first match `{ state, matchedBy }` or `{ state: "ok" }`.

Called: at bootstrap, before submit (preflight), on stall, on first-token timeout, and whenever a
mutation adds an element matching any state's selector (cheap check via `matches()` on added nodes).

### 5.11 `content/driver.js` — orchestration

```js
async function runJob(job) {
  const ctx = createJobContext(job);          // timers, seq counter, abort flag
  progress("preflight");
  assertState("ok");                          // throws typed errors
  const editor = await resolveOrFail("composer.input");
  if (job.modelVariant !== "default") await selectModel(job.modelVariant); // §5.12
  progress("injecting");
  await injector.insert(editor, job.promptText, cfg.composer.insertStrategies);
  const markers = observer.captureBefore();
  netTapRelay.arm(job.jobId);                 // bind next matching stream to this job
  progress("submitting");
  await submitter.submit(editor, markers);
  progress("waiting_first_token");
  const turn = await observer.waitForAssistantTurn(markers, job.timeouts.firstTokenMs);
  progress("generating");
  const result = await completion.waitForDone(turn, ctx);   // emits deltas while waiting
  progress("finalizing");
  const thread = await readThreadUrl(cfg.urls.threadPattern, 3000); // URL may update after 1st reply
  return { text: result.text, reasoning: result.reasoning, finishReason: "stop",
           threadUrl: thread.url, threadId: thread.id, modelLabel: readModelLabel(),
           source: result.source, warnings: result.warnings };
}
```
Every thrown error is a `W2AError { code, message, detail, partialText }`; the Port handler converts it
to an `error` message. Unknown exceptions become `INTERNAL_ERROR` with the stack in `detail` (stack only,
no prompt text). On any error, also request a snapshot (§9.3) if the code is in the snapshot-worthy set
(`SELECTOR_NOT_FOUND`, `INPUT_REJECTED`, `SUBMIT_FAILED`, `NO_RESPONSE`, `GENERATION_STALLED`).

### 5.12 Model selection (optional per provider)

If `config.models.variants[variant].select` exists, it is a list of steps executed in order:
`{ "click": <selector entry> }`, `{ "waitFor": <selector entry>, "timeoutMs": 3000 }`,
`{ "assertText": <selector entry>, "pattern": "Opus" }`. If any step fails → `MODEL_SELECT_FAILED`
(not silent). If the currently displayed model label (selector `models.currentLabel`) already matches
`variants[variant].labelPattern`, skip the steps. Variant selection is a v1.1 feature; v1 supports
only `default` and must return `MODEL_NOT_AVAILABLE` for anything else.

---

## 6. MAIN-world net tap

### 6.1 Purpose and guarantees

Observe — never modify — the provider's own streaming responses, parse them into deltas, and hand
them to the isolated world. Guarantees:
* Request and response bodies seen by the page are **byte-identical** to what they would be without
  the extension (use `Response.clone()`/`tee`; never consume the original body).
* Any exception inside the tap is caught and reported; the page's `fetch` must behave exactly as the
  original even if the tap breaks.
* Only URLs matching the provider config's `netTap.endpoints[].urlPattern` are observed. Everything
  else passes through with zero work beyond one regex test.

### 6.2 Load order and configuration in the MAIN world

The MAIN world cannot read extension storage. The parsers are bundled per provider by the manifest
entry (§2.3); the endpoint URL patterns come from the generated `providers/generated/<id>.nettap.js`
(bundled config data) *plus* runtime overrides delivered through the MessageChannel (§6.4) once it is
established (overrides only affect URL patterns/flags, i.e. data). Sequence:
1. `providers/parsers/sse.js` defines a helper in a closure and registers it on a temporary hook:
   `window.__w2a_reg = window.__w2a_reg || []; window.__w2a_reg.push(["parser", "sse", factory]);`
2. `providers/parsers/<provider>.js` registers its parser factory the same way
   (`["parser", "claude", factory]`).
3. `providers/generated/<provider>.nettap.js` registers `["endpoints", "claude", [ ... ]]`.
4. `main-world/net-tap.js` runs last: reads and **deletes** `window.__w2a_reg`, builds its parser and
   endpoint tables in its closure, installs the wrappers, sets up the MessageChannel. After this, no
   `__w2a*` global remains. (Between steps 1 and 4 the hook exists for microseconds before any page
   script runs, because all four files execute synchronously at `document_start`.)

### 6.3 Wrappers

* `fetch`: replace with `new Proxy(originalFetch, { apply(target, thisArg, args) { … } })`. A Proxy
  around a native function keeps `Function.prototype.toString` output native-looking. Inside: build a
  `Request`-like descriptor `{url, method}` cheaply from `args` (don't construct a `Request` unless
  needed; don't read the body unless the endpoint config sets `captureRequestBody: true`, and then
  only via `init.body` when it is a string). Call `Reflect.apply(target, thisArg, args)`; if the URL
  matches, attach `.then(res => observe(res.clone(), endpoint))` to a *side* promise; return the
  original promise untouched.
* `XMLHttpRequest`: wrap `open` to record URL/method on the instance (in a `WeakMap`, not a property),
  and add a `progress`/`readystatechange` listener for matching ones that reads `responseText`
  increments (XHR streaming, used by Gemini's batchexecute-style endpoints).
* `WebSocket` (only if any endpoint has `transport: "websocket"`): wrap the constructor via Proxy;
  for matching URLs add a `message` listener (`addEventListener`, never overwrite `onmessage`).
* `EventSource`: same pattern if needed.

`observe(response, endpoint)`: read `response.body.getReader()` with a `TextDecoder("utf-8", {stream: true})`;
feed each decoded chunk to the parser; post resulting events. On reader error → post
`{type: "error", code: "NET_STREAM_ERROR"}` for that stream.

### 6.4 Private channel to the isolated world

* At startup the tap creates `const ch = new MessageChannel()`.
* It listens for `window` `message` events whose `event.source === window` and `event.data` is an
  object `{ w2a: "hello", nonce: <string> }` (sent by `nettap-relay.js` in the isolated world).
  On the first such message it replies `window.postMessage({ w2a: "port", nonce }, "*", [ch.port2])`
  and stops listening. From then on all traffic goes over `ch.port1` (not observable by page scripts).
* `nettap-relay.js` sends `hello` immediately at `document_start` and re-sends every 50 ms up to 40
  times until the port arrives (this is the only short-interval timer; the tab is loading, so it's
  not hidden-throttled in practice; if it fails, net tap is reported inactive and the job uses DOM).
* Messages over the port:
  * isolated → MAIN: `{ t: "arm", jobId }`, `{ t: "disarm" }`, `{ t: "override", endpoints }`.
  * MAIN → isolated: `{ t: "stream_start", streamId, url, jobId|null }`, `{ t: "event", streamId, event }`,
    `{ t: "stream_end", streamId }`, `{ t: "tap_error", message }`.
* Binding: when armed, the **first** matching stream that starts after `arm` and whose endpoint has
  `role: "completion"` (not `role: "title"` or `"other"`) is bound to the job. Streams starting while
  not armed are ignored (they belong to the user or to background requests).

### 6.5 Parser interface

Each parser file registers a factory returning:
```js
{
  id: "claude",
  // Called once per matching stream.
  createState(meta) { return { buffer: "", text: "", reasoning: "", done: false }; },
  // Called with each decoded text chunk. Returns an array of normalised events.
  onChunk(state, chunk) { return [ /* events */ ]; },
  // Called when the body ends (or errors).
  onEnd(state) { return [ /* e.g. { type: "done", finishReason: "stop" } if not already */ ]; }
}
```
Normalised events:
| `type` | Fields | Meaning |
|---|---|---|
| `text` | `delta` | Append to answer text. |
| `reasoning` | `delta` | Append to reasoning/thinking text. |
| `replace` | `text` | Provider sent a full snapshot instead of a delta (some do); replaces answer text. |
| `meta` | `conversationId?, messageId?, model?` | Identifiers (used for thread URL and `model` label). |
| `done` | `finishReason` (`stop`/`length`/`content_filter`/`error`) | Stream finished. |
| `error` | `code, message` | Provider-reported error inside the stream (e.g. rate limit, overloaded). |

`sse.js` provides `createSseSplitter()` → `push(chunk) → Array<{event, data, id}>` implementing the
SSE spec (lines, `data:` concatenation, blank-line dispatch, `\r\n`/`\n`/`\r` handling, comments `:`).
Parsers must tolerate unknown event types (ignore them) — providers add new event types often.

Parser correctness is unit-tested against recorded stream samples in `tests/fixtures/<provider>/stream-*.txt`
(`09-testing-strategy.md` §2.3).

### 6.6 Firefox alternative (optional, later)

Firefox supports `browser.webRequest.filterResponseData(requestId)` in the background, which can read
response bodies without touching the page at all (zero page-visible footprint). It requires the
`webRequest` and `webRequestBlocking` permissions. Plan it as an optional Firefox-only transport for
the net tap in a later phase; keep the parser interface identical so the same parsers run in either
place.

---

## 7. Config store (`background/config-store.js`)

* On init: load bundled configs (`fetch(chrome.runtime.getURL("providers/<id>.json"))` for each id in
  `providers/index.json`), load `config.overrides` from storage, compute **effective config** per
  provider = deep-merge(bundled, override.patch) using the merge rules in `05` §2.4.
* Validate the effective config against the schema; if an override makes it invalid, reject the
  override (keep the previous effective config) and report `CONFIG_REJECTED`.
* `applyOverride(providerId, override)` (from bridge `CONFIG_OVERRIDE` frame or popup import):
  validate → persist → push `config` to every connected tab of that provider → reply
  `CONFIG_ACK {providerId, version, status}`.
* `revertOverride(providerId)` restores the bundled config.
* Expose `getEffective(providerId)` and `describe()` (versions, override present?, applied when, by
  whom) for the popup and the bridge's `/web2api/providers` endpoint.

---

## 8. Popup (`popup/`)

Plain HTML/CSS/JS. All dynamic text via `textContent`. Data comes from the background via
`chrome.runtime.sendMessage({ t: "popup:getState" })` and live updates via a Port
`chrome.runtime.connect({ name: "w2a-popup" })` while open.

Sections (single scrolling page with collapsible sections, ≈ 380 px wide):

1. **Connection**
   * Status pill: `Connected` / `Connecting…` / `Bridge offline` / `Needs pairing` /
     `Rejected: bad token` / `Rejected: version mismatch`.
   * Bridge URL input (default `ws://127.0.0.1:8787/ws/extension`), pairing-token input (password type)
     with "Save & connect".
   * One-line help: "Start the bridge with `uv run web2api-bridge` and paste the token it prints."
2. **Providers** — one row per provider:
   * Name, status dot (ready / degraded / login required / unhealthy / disabled), tab count
     (idle/busy), enable toggle, pool size (1–4).
   * Buttons: "Open worker tab", "Use current tab" (only when the active tab belongs to that provider
     and isn't already in the pool), "Release tab".
   * Hint when net tap inactive in an assigned tab: "Reload tab for exact streaming".
3. **Health** — latest reports (time, provider, code, failing key). Buttons per report:
   "Copy report" (JSON to clipboard) and "Download snapshot" (if present). "Run health check now".
4. **Settings** — worker window mode, min delay per provider, history mode (normal/temporary),
   debug content logging (off by default, with a warning text), queue timeout.
5. **Test** — provider dropdown, prompt textarea, "Run" → submits a job through the queue
   (`t: "popup:testJob"`), shows streamed text in a `<pre>`; "Stop" cancels.

Action badge (set by background): text `""` when idle and connected, `"…"` when jobs running (or the
count), `"!"` red when disconnected/rejected or any provider unhealthy.

---

## 9. Health checks, failure reports, snapshots (`background/health.js`)

These exist primarily for the future maintainer (R4), and secondarily for the human.

### 9.1 Health checks (probes)

* **Passive:** every job outcome updates per-provider counters (success/fail by code) and per-selector
  resolution tiers (from §5.2 metrics, reported in `done`/`error` detail as
  `resolution: { "composer.input": 0, "turns.assistant": 2, ... }`).
* **Active probe:** on demand (popup button, bridge `HEALTH_PROBE` frame) or every
  `settings.healthIntervalMin` (default 30, via alarm) for providers with an idle tab: send `probe` to
  the tab with checks = every selector key listed in the config's top-level `critical` array (typically
  composer.input, composer.send, turns.assistant, answer.content [only if a previous turn exists]). The tab returns,
  per key: `{ found: bool, tier, count, css }`. **Probes never type or send anything.**
* Provider health status:
  * `healthy` — all critical keys found at tier 0, last 5 jobs ok.
  * `degraded` — critical keys found but some only at fallback tiers, or 1–2 of the last 5 jobs failed
    with selector-type errors.
  * `unhealthy` — any critical key not found, or 3+ of the last 5 jobs failed with selector-type errors.

### 9.2 Failure report format

Stored in `health.reports` and sent to the bridge as `HEALTH_REPORT`:
```json
{
  "reportId": "hr_01J…",
  "createdAt": "2026-10-20T12:00:00Z",
  "provider": "claude",
  "configVersion": "2026.10.20-1",
  "overrideVersion": null,
  "extensionVersion": "0.1.0",
  "browser": "chrome/130",
  "trigger": "job_error" | "probe",
  "code": "SELECTOR_NOT_FOUND",
  "failingKeys": ["composer.send"],
  "resolution": { "composer.input": 0, "composer.send": null },
  "pageUrlPattern": "https://claude.ai/chat/<id>",
  "pageState": "ok",
  "snapshotId": "snap_01J…" | null
}
```
No prompt or answer text, ever. URLs are reduced with `config.urls.threadPattern` to replace ids with
`<id>`.

### 9.3 DOM snapshots (`content/snapshot.js`)

Purpose: give a human or the maintainer agent the actual HTML the selectors failed against.

Algorithm:
1. `const clone = document.documentElement.cloneNode(true)`.
2. Remove `script`, `style` contents (keep `<style>` tags empty? → remove entirely), `noscript`,
   `iframe` (keep tag with `src` origin only), `svg` (replace with `<svg data-w2a-removed>`),
   `img`/`video` `src` (keep only origin + path length marker), `link[rel=stylesheet]`.
3. **Redact text content:** replace every text node's content with a same-length placeholder of `x`
   characters *except* inside elements matching the allowlist of UI chrome
   (`button, [role=button], label, [aria-label], [placeholder]` and their descendants), so conversation
   content is not leaked but button labels (useful for selector repair) remain. Also redact
   `value`, `placeholder` is kept, `title` kept, `aria-label` kept, `href` reduced to path pattern.
4. Remove all attributes starting with `on` and any attribute longer than 500 chars.
5. Serialize, truncate at 2 MB, prepend an HTML comment with provider, url pattern, viewport size,
   timestamp, config version.

Snapshots are only taken on snapshot-worthy errors or on explicit request, stored locally (max 10),
and only sent to the bridge when the bridge asks (`SNAPSHOT_REQUEST`) — the bridge is local, but the
future maintainer may send snapshots to a paid API, so the redaction above is mandatory.

---

## 10. Settings (`background/settings.js`)

Stored in `chrome.storage.local.settings`, merged over defaults:
```js
const DEFAULT_SETTINGS = {
  bridgeUrl: "ws://127.0.0.1:8787/ws/extension",
  pairingToken: "",
  workerWindowMode: "dedicated",        // "dedicated" | "background-tabs"
  maxWorkerWindows: 3,
  historyMode: "normal",                // "normal" | "temporary"
  queueTimeoutMs: 60000,
  healthIntervalMin: 30,
  debugContentLogging: false,
  providers: {
    // filled with defaults for every bundled provider:
    // chatgpt: { enabled: true, poolSize: 1, minDelayMs: 3000 }
  }
};
```
Settings changes are broadcast to modules via an internal event emitter; bridge URL/token changes
restart the bridge client.

---

## 11. Logging (`shared/logger.js`)

* Levels: `error`, `warn`, `info`, `debug`. Default `info`.
* Each log line: `[W2A][<context>] <message>` + structured object. Contexts: `bg`, `bridge`, `pool`,
  `job:<jobId short>`, `tab:<provider>`, `tap:<provider>`.
* **Redaction:** the logger never prints fields named `promptText`, `text`, `delta`, `partialText`,
  `reasoning` unless `debugContentLogging` is on; it prints `<redacted len=1234>` instead. MAIN-world
  code does not log at all (page-visible console) — it reports problems over the private channel only.
