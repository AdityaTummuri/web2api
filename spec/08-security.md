# 08 — Security

Web2API holds the keys to the owner's AI accounts and conversation history. Anything that can talk to
the bridge can act as the owner on ChatGPT/Claude/Gemini and read what the model says. This document
is the threat model and the list of **mandatory** controls. None of these are optional for v1.

---

## 1. Assets

| Asset | Where it lives | Why it matters |
|---|---|---|
| Logged-in provider sessions | Browser cookies (never leave the browser) | Ability to chat as the owner, consume paid quota, read history. |
| Conversation content | Provider servers, the worker tabs, transiently in bridge memory | Private data. |
| API token | `~/.config/web2api/api_token` | Grants HTTP API access. |
| Pairing token | `~/.config/web2api/pairing_token`, extension `storage.local` | Lets a WebSocket client act as the extension. |
| Provider config overrides | extension `storage.local` | Malicious selectors could make the driver click the wrong things. |
| Health snapshots | extension `storage.local`, bridge memory | Page structure; must not contain conversation text. |

## 2. Threats (and which control addresses each)

| # | Threat | Control |
|---|---|---|
| T1 | A website the owner visits calls `http://127.0.0.1:8787/v1/...` from JavaScript (CSRF / cross-origin read). | No CORS (§3.1), bearer token (§3.1), Host check (§3.3). |
| T2 | A website opens `ws://127.0.0.1:8787/ws/extension` and pretends to be the extension (receives prompts, forges answers). | Origin check + pairing token (§3.2). |
| T3 | DNS rebinding makes an attacker's domain resolve to 127.0.0.1. | Host header check (§3.3) + tokens. |
| T4 | Another device on the LAN connects. | Loopback bind; remote requires explicit opt-in (§3.4). |
| T5 | Another local user/process on the machine reads tokens. | 0600 token files; tokens never in URLs/logs (§3.5). |
| T6 | Another installed browser extension messages ours. | No `externally_connectable`; `runtime.onMessage` handlers check `sender.id === chrome.runtime.id` and that popup-only actions come from the popup URL (§4.2). |
| T7 | The provider page (or a script injected into it) detects or tampers with the extension. | Minimal page footprint (§5); MAIN-world code observes only; private MessageChannel. |
| T8 | Malicious config override (e.g. selector pointing the "send" click at "Delete conversation"). | Overrides validated (`05` §2.4), only from authenticated bridge or user import, logged, revertible; destructive-action guard (§4.3). |
| T9 | Prompt injection via model output (model tells the system to do something). | Output is never interpreted or acted upon by Web2API (§4.4). |
| T10 | Leaking conversation content through logs, health reports, or snapshots that later go to the maintainer's paid API. | Redacting logger, content-free reports, redacted snapshots (`04` §9). |
| T11 | Supply chain: compromised dependency. | Minimal deps (3 runtime Python deps, zero runtime JS deps), lockfile committed. |

## 3. Bridge controls

### 3.1 HTTP authentication, no CORS

* Every route except `GET /healthz` requires `Authorization: Bearer <api_token>`. Compare with
  `hmac.compare_digest`. Missing/invalid → 401 OpenAI-style error.
* Do **not** install `CORSMiddleware`. Without CORS headers, browsers block cross-origin pages from
  reading responses, and the `Authorization` header forces a preflight that fails.
* Do not accept the token in query strings (would end up in logs and browser history).

### 3.2 WebSocket authentication

Before `accept()`:
1. `Origin` header must be present and match `allowed_extension_origins` (glob match; defaults
   `chrome-extension://*`, `moz-extension://*`). Web origins (`http://`, `https://`), `null`, and
   missing origins are rejected (close before accept → HTTP 403).
2. Host check (§3.3).

After `accept()`:
3. First frame must be `HELLO` within 5 s with the correct pairing token (constant-time compare) →
   else close 4401.

Optional hardening (config): pin `allowed_extension_origins` to the exact Chrome extension id. For a
stable Chrome id during development, add a `key` to `manifests/chrome.json` (document how to generate
it in the README).

### 3.3 Host header check (anti DNS rebinding)

Middleware for HTTP **and** the WebSocket route: allowed `Host` values are `127.0.0.1:<port>`,
`localhost:<port>`, `[::1]:<port>` (plus configured extra hosts when `allow_remote`). Anything else →
421 Misdirected Request (HTTP) / close before accept (WS).

### 3.4 Bind address

* Default `127.0.0.1`. If `host` is not a loopback address and `allow_remote` is false → refuse to
  start with a clear error.
* With `allow_remote = true`, print a loud warning on startup; tokens remain mandatory. TLS is out of
  scope; recommend an SSH tunnel instead of remote exposure.

### 3.5 Token handling

* Generated with `secrets.token_urlsafe(32)`; stored in files created with mode 0600 in a directory
  with mode 0700.
* Printed once at startup (owner needs them) and via `web2api-bridge tokens show`. Never logged
  otherwise.
* `tokens rotate` regenerates; rotating the pairing token closes all extension connections with 4401
  (the user re-pastes the token).
* Two separate tokens: leaking the API token (likely — it gets pasted into many tools) does not allow
  impersonating the extension.

### 3.6 Input limits

* Max request body 5 MB (reject larger with 413).
* `max_prompt_chars` on the generated prompt.
* Max concurrent jobs waiting in the bridge per provider: 20 (beyond → 503 `NO_CAPACITY`).

## 4. Extension controls

### 4.1 Permissions (least privilege)

Exactly: `storage`, `tabs`, `scripting`, `alarms`, plus host permissions for the enabled providers'
origins. No `<all_urls>`, no `cookies`, no `webRequest` (until the optional Firefox net-tap transport,
which would add it behind a separate build flag), no `debugger`, no `clipboardRead`, no
`web_accessible_resources`, no `externally_connectable`.

### 4.2 Message hygiene

* `runtime.onMessage` / `onConnect`: verify `sender.id === chrome.runtime.id`. For popup-only
  messages (`popup:*`), verify `sender.url` starts with `chrome.runtime.getURL("popup/")`. For tab
  Ports, verify `sender.tab` exists and its URL matches a provider host; bind the Port to that tab id
  and provider (a content script cannot claim to be another provider).
* Validate every message's shape (type and required fields) before acting.

### 4.3 Driver safety rails

* The driver only clicks elements resolved from these keys: `composer.send`, `composer.stop`,
  model-selection steps, configured interrupt handling. It never clicks elements derived from answer
  content.
* **Destructive-action guard:** before any click, check the target's accessible name
  (`aria-label` + `textContent`, lowercased) against a deny list
  (`delete`, `remove`, `clear`, `log out`, `logout`, `sign out`, `archive`, `share`, `upgrade`,
  `subscribe`, `buy`, `pay`). If it matches → refuse, error `SELECTOR_SUSPICIOUS`, health report. This
  limits the blast radius of a bad override (T8) or a site redesign that moves buttons.
* Navigation only to URLs from the provider config whose origin is within the provider's host
  permissions, or to thread URLs matching `urls.threadPattern`.

### 4.4 Untrusted output

* The extension and bridge treat answer text as opaque data. No `innerHTML` with it anywhere
  (popup uses `textContent`). No URL opening, no clicking, no execution based on it.
* Future tool calling returns calls to the API client; Web2API never executes tools.

## 5. Page-footprint minimisation (detectability, T7, L-42)

In provider pages the extension must:
1. Inject **no** DOM nodes and set **no** inline styles or attributes on page elements (the inspo HUD
   and outline pulse are not ported).
2. Expose **no** `web_accessible_resources` (prevents `chrome-extension://<id>/…` probing).
3. MAIN world: wrap `fetch`/`XMLHttpRequest`/`WebSocket` with `Proxy` objects (native-looking
   `toString`), use a private `MessageChannel` after a one-time handshake, delete the temporary
   registration global immediately, never write to `window`, never log to the console.
4. Never read `document.body.innerText` on the whole page (expensive, forces layout); scope state
   detection to configured elements.
5. Pace jobs (minimum delay per provider) and avoid superhuman typing patterns where possible (paste is
   a normal human action; a single `paste` event is less suspicious than thousands of synthetic key
   events).

These measures reduce, but cannot eliminate, the chance that a provider identifies automated use
(see L-47 in `02`).

## 6. Data handling

* The bridge keeps prompts/answers only in memory for the duration of a job. Job history stores
  metadata only.
* `persist_threads` stores thread URLs and fingerprints (hashes), not text.
* Snapshots are redacted at capture (`04` §9.3) and capped in number and size.
* The README must tell the owner: everything sent through Web2API lands in their provider history
  unless `history_mode = "temporary"` is used on providers that support it.

## 7. Security test checklist (automated where possible — see `09` §5)

- [ ] HTTP request without token → 401.
- [ ] HTTP request with `Origin: https://evil.example` and valid token → still works for non-browser
      clients, but response has **no** `Access-Control-Allow-Origin` header.
- [ ] `OPTIONS` preflight → no CORS allow headers.
- [ ] `Host: evil.example:8787` → 421.
- [ ] WebSocket with `Origin: https://evil.example` → rejected before accept.
- [ ] WebSocket without `Origin` → rejected.
- [ ] WebSocket with extension origin but wrong token → closed 4401.
- [ ] WebSocket with no HELLO for 5 s → closed 4408.
- [ ] Bridge refuses to start with `--host 0.0.0.0` without `allow_remote`.
- [ ] Token files created with mode 0600.
- [ ] Override touching `match` or `netTap.parsers` → rejected.
- [ ] Override whose `composer.send` resolves to a button labelled "Delete" → click refused
      (`SELECTOR_SUSPICIOUS`) — jsdom test.
- [ ] Logs contain no prompt text with default settings (grep test over captured logs).
