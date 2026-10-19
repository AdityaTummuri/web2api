# 05 — Provider Adapters

A **provider adapter** = one JSON config file (`extension/src/providers/<id>.json`) + optionally one
stream parser (`extension/src/providers/parsers/<id>.js`). This document defines the config format,
the override mechanism, the procedure for researching a site, and the per-site notes for every
provider we intend to support.

> ⚠️ **All selectors, URLs and stream formats in §5 are starting candidates** based on knowledge
> available at the time of writing. Chat sites change their front-ends every few weeks. **Every value
> must be re-verified on the live site during the recon phase (`10-implementation-plan.md` Phase 1)**
> using the procedure in §4, and the verified values — not the ones below — go into the JSON files.

---

## 1. Provider tiers (scope)

| Tier | Providers | Target phase | Notes |
|---|---|---|---|
| **1** | `chatgpt`, `claude`, `gemini` | v1 (Phases 2–5) | The inspo's three sites. Must be rock solid, with net tap for ChatGPT and Claude. Gemini starts DOM-only. |
| **2** | `deepseek`, `grok`, `perplexity`, `mistral`, `qwen`, `kimi` | v1.1 (Phase 7) | Data-mostly additions once the framework is proven. |
| **3** | `copilot`, `meta`, `huggingchat`, `aistudio`, `zai` | Later | Unusual transports (WebSocket, GraphQL, gRPC-web) or lower demand. |

A provider can ship with `"enabled": false` by default in settings until it passes its live smoke
test (`09-testing-strategy.md` §4).

---

## 2. Provider config format

### 2.1 Full annotated example (`claude.json`)

Comments are for explanation only — real JSON files cannot contain comments. Put human notes in the
`notes` field instead.

```jsonc
{
  "schemaVersion": 1,                       // version of THIS format; bump on breaking changes
  "id": "claude",                           // lowercase, [a-z0-9-]+, unique
  "displayName": "Claude",
  "configVersion": "2026.10.20-1",          // date + counter; bump on every edit
  "tier": 1,

  "match": {
    "hostPermissions": ["https://claude.ai/*"],     // goes into the manifest; cannot be overridden
    "hostRegex": "^claude\\.ai$"                     // matched against location.hostname
  },

  "urls": {
    "home": "https://claude.ai/",
    "newChat": "https://claude.ai/new",
    "newChatTemporary": null,                         // null = provider has no URL for temporary chats
    "newChatStrategy": "navigate",                    // "navigate" (default) | "click" (uses selectors.composer.newChatButton)
    "threadPattern": "^https://claude\\.ai/chat/(?<id>[0-9a-f-]{36})(?:[/?#]|$)",
    "loginPattern": "^https://claude\\.ai/(login|logout)"
  },

  "selectors": {                                     // every leaf is a SelectorTiers value (§2.2)
    "composer": {
      "root":  [ { "css": "fieldset" } ],
      "input": [
        { "css": "div.ProseMirror[contenteditable='true']", "within": "composer.root", "visible": true },
        { "css": "[contenteditable='true'][role='textbox']", "visible": true, "score": true }
      ],
      "send": [
        { "css": "button[aria-label='Send message']", "visible": true },
        { "css": "button[type='submit']", "within": "composer.root", "visible": true }
      ],
      "stop": [ { "css": "button[aria-label='Stop response']", "visible": true } ]
    },
    "turns": {
      "user":      [ { "css": "[data-testid='user-message']" } ],
      "assistant": [ { "css": "div[data-is-streaming]" } ]
    },
    "answer": {
      "content":           [ { "css": ".font-claude-response" }, { "css": ".font-claude-message" } ],
      "exclude":           [ { "css": "[data-testid='thinking-block']" } ],
      "codeHeader":        [ { "css": "pre > div:first-child" } ],
      "codeLanguageLabel": [],
      "actionsBar":        [ { "css": "[data-testid='action-bar-copy']" } ]
    },
    "status": {
      "thinking": []
    },
    "models": {
      "currentLabel": [ { "css": "[data-testid='model-selector-dropdown']" } ]
    }
  },

  "critical": ["composer.input", "composer.send", "turns.assistant"],

  "composer": {
    "insertStrategies": ["paste", "execCommand", "range"],
    "submitStrategies": ["click", "enter"],
    "placeholderPattern": "(?i)(reply|message|talk|prompt|claude)",
    "maxChars": null
  },

  "completion": {
    "signals": [
      { "type": "netDone" },
      { "type": "attrEquals", "target": "@assistantTurn", "attr": "data-is-streaming", "value": "false" },
      { "type": "disappears", "selector": "composer.stop" },
      { "type": "appears", "selector": "answer.actionsBar", "within": "@assistantTurn" }
    ],
    "settleMs": 600,
    "allowEmpty": false,
    "neverSeenGraceMs": 8000
  },

  "states": {
    "loggedOut":   { "urlPattern": "^https://claude\\.ai/login", "selectors": [], "textPatterns": [], "scope": [] },
    "captcha":     { "selectors": [ { "css": "iframe[src*='challenges.cloudflare.com']" } ] },
    "rateLimited": {
      "selectors": [],
      "textPatterns": ["(?i)out of (free )?messages", "(?i)usage limit", "(?i)message limit", "(?i)try again (at|in)"],
      "scope": [ { "css": "[role='alert']" }, { "css": "fieldset" } ]
    },
    "error":       { "textPatterns": ["(?i)something went wrong", "(?i)overloaded"], "scope": [ { "css": "[role='alert']" } ] },
    "interrupt":   { "selectors": [] }
  },

  "models": {
    "variants": { "default": {} }
  },

  "netTap": {
    "enabled": true,
    "parsers": ["sse", "claude"],
    "endpoints": [
      {
        "id": "completion",
        "urlPattern": "/api/organizations/[^/]+/chat_conversations/[^/]+/(completion|retry_completion)(\\?|$)",
        "method": "POST",
        "transport": "fetch",
        "role": "completion",
        "parser": "claude",
        "captureRequestBody": false
      }
    ]
  },

  "timeouts": { "firstTokenMs": 60000, "totalMs": 300000, "stallMs": 90000 },

  "locale": { "verifiedWith": ["en-US"] },

  "notes": "data-is-streaming flips to 'false' when generation ends; strongest DOM signal."
}
```

### 2.2 `SelectorTiers` value

A `SelectorTiers` is an **array** of `SelectorEntry` (tried in order = tiers), or a single string
(shorthand for `[{ "css": "<string>" }]`).

`SelectorEntry` fields:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `css` | string, required | — | A standard CSS selector (no Playwright extensions like `:has-text`). Validated at build/load time with `document.querySelector` in a try/catch (L-27). `:has()` is allowed (Chrome 105+, Firefox 121+). |
| `within` | string \| null | null | Dotted key of another selector to use as the search root, or the special value `@assistantTurn` / `@userTurn` (the job's identified turns). |
| `visible` | bool | false | Filter out non-visible candidates (§04 5.2). Use `true` for anything we click or type into. |
| `nth` | `"first"` \| `"last"` \| int | `"first"` | Which candidate to take after filtering. |
| `text` | regex string \| null | null | Candidate's `textContent` must match. Prefix `(?i)` for case-insensitive (the loader converts it into a JS `RegExp` flag). |
| `attr` | object \| null | null | `{ "<attr name>": "<regex>" }` — all must match. |
| `score` | bool | false | Use the composer scoring heuristic over all candidates instead of `nth` (§04 5.2). Only meaningful for `composer.input`. |
| `note` | string | — | Human/maintainer note, ignored by code. |

**Regex convention (applies to every regex string in a config):** JavaScript does not accept a
leading `(?i)` inline flag, so the loader strips a leading `(?i)` and compiles the rest with the `i`
flag. No other inline flags are allowed. Python (bridge-side validation) understands `(?i)` natively.
Named groups are written JS-style, `(?<name>…)`. Python rejects that syntax (verified:
`re.error: unknown extension ?<i`) and needs `(?P<name>…)`, so the bridge validator must rewrite
`(?<name>` → `(?P<name>` (but not lookbehinds `(?<=` / `(?<!`) before compiling.

**Selector authoring rules** (the maintainer agent follows the same rules):
1. Prefer, in order: `data-testid` / `data-test-id` / other `data-*` attributes → `id` (if not
   auto-generated) → custom element tag names (e.g. Gemini's `model-response`) → ARIA role/structure →
   `aria-label` → semantic tags + structure → class names.
2. **Never** use hashed/generated class names (`css-1k9xq2`, `_a8f3c`, `sc-bdVaJa`, Tailwind utility
   soups that change often).
3. `aria-label` and text patterns are **locale-dependent** (a user with French UI gets French labels).
   Every config records `locale.verifiedWith`. When a label-based selector is the only option, also add
   a structural fallback tier. Text patterns in `states` should include common languages where feasible
   or rely on selectors.
4. Each critical key should have **at least two tiers** that rely on different attributes, so one
   front-end change rarely breaks both.

### 2.3 Completion signal entries

| `type` | Fields | Notes |
|---|---|---|
| `netDone` | — | Requires `netTap.enabled`. |
| `attrEquals` | `target` (selector key or `@assistantTurn`), `attr`, `value` | Checked on attribute mutations. |
| `appears` | `selector` (key), `within` (optional key or `@assistantTurn`) | |
| `disappears` | `selector` (key) | Strong only if it was seen during the job (§04 5.6). |
| `sendReady` | — | Uses `composer.send` + empty `composer.input`. Weak. |
| `textStable` | `ms` | Weak. Normally not listed; `settleMs` already applies. |

### 2.4 Overrides (hot fixes without a code change)

An **override** is a JSON object pushed by the bridge (`CONFIG_OVERRIDE`, see `06` §6) or imported in
the popup:
```json
{
  "providerId": "claude",
  "overrideVersion": "ovr-2026.10.25-1",
  "baseConfigVersion": "2026.10.20-1",
  "source": "manual" | "maintainer",
  "createdAt": "2026-10-25T09:12:00Z",
  "reason": "Send button aria-label changed to 'Send'",
  "patch": {
    "selectors": {
      "composer": {
        "send": [ { "css": "button[aria-label='Send']", "visible": true },
                  { "css": "button[type='submit']", "within": "composer.root", "visible": true } ]
      }
    }
  }
}
```

**Merge rule:** RFC 7396 JSON Merge Patch — objects merge recursively, **arrays replace wholesale**,
`null` deletes a key. (Replacing arrays is deliberate: tiers are ordered and partial array merges are
ambiguous.)

**Validation (reject the override if any fails):**
1. `baseConfigVersion` must equal the bundled config's `configVersion`. (When the extension updates
   and its bundled config changes, stale overrides are dropped automatically and reported.)
2. The patch must not touch `id`, `match`, `schemaVersion`, or `netTap.parsers` (code references and
   host permissions are fixed at build time).
3. `urls.*` values must stay inside the provider's `match.hostPermissions` origins.
4. Every `css` must parse; every regex must compile (`new RegExp`), and regexes are limited to 500
   chars (avoid catastrophic patterns: reject nested quantifiers like `(a+)+` with a simple check).
5. The effective config must pass the schema validation.
6. Overrides are data only: any string field named `code`, `script`, `eval`, or containing
   `javascript:` is rejected.

On acceptance, the store keeps the previous override (one level of undo).

### 2.5 JSON Schema

`extension/src/providers/schema.json` formalises §2.1–2.3 (JSON Schema draft 2020-12). The Python
bridge validates overrides against the **same** schema file before sending them (copy it into
`bridge/web2api_bridge/provider_schema.json` at build time, or read it from `../extension/src/providers/`
in dev; a test asserts both copies are identical).

---

## 3. Stream parsers (provider-specific code)

* File: `extension/src/providers/parsers/<id>.js`, MAIN world, interface in `04` §6.5.
* Must be **pure** with respect to its inputs (no DOM, no network, no timers) so it can be unit-tested
  in Node with recorded samples.
* Must be **tolerant**: unknown event types/fields are ignored; malformed JSON lines are skipped with
  a counter (reported in `done.warnings` as `parser_skipped:<n>`), never thrown.
* Must handle chunk boundaries anywhere (mid-line, mid-UTF-8 sequence — the `TextDecoder` with
  `stream: true` handles UTF-8; the parser must buffer partial lines).
* Should emit `meta` with the conversation id when the stream reveals it (helps thread URL capture
  before the page updates `location`).

---

## 4. Recon procedure: researching a site (do this per provider in Phase 1)

Produce, per provider, a folder `extension/tests/fixtures/<id>/` and a filled-in config.

1. **Setup:** Chrome with a logged-in account, UI language English (record it). DevTools open,
   "Preserve log" on.
2. **Composer:** Inspect the input. Record: element type (`textarea` vs `contenteditable`), editor
   library (ProseMirror shows class `ProseMirror`; Quill shows `ql-editor`; Lexical shows
   `data-lexical-editor`; TipTap is ProseMirror-based), stable attributes, the enclosing form/fieldset.
   Check whether there are **hidden duplicate editors** (e.g. a hidden `<textarea>` fallback) — the
   `visible: true` flag must exclude them.
3. **Insertion test** (in the DevTools console on the page — this runs in the page's MAIN world, which
   is fine for recon):
   ```js
   const ed = document.querySelector("<input selector>");
   ed.focus();
   const dt = new DataTransfer(); dt.setData("text/plain", "line 1\n\nline 2\n  indented");
   ed.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
   ```
   Confirm the text appears with newlines preserved and that the send button becomes enabled. If not,
   try `document.execCommand("insertText", false, "...")`. Record which strategy works.
4. **Send + turns:** Send a prompt that produces a long answer with a code block, a list, a table and
   math, e.g. *"Write a markdown answer with: a heading, a nested bulleted list, a python code block, a
   2x2 table, and the formula $e^{i\pi}+1=0$."* While it streams:
   * Identify the user-turn and assistant-turn containers and the answer content element.
   * Right-click the assistant turn → *Break on → attribute modifications* to discover attributes that
     flip at completion (like Claude's `data-is-streaming`).
   * Note the stop button's selector while visible, and what replaces it after.
   * Note what appears only after completion (copy/retry/feedback toolbar).
5. **Network:** In the Network tab filter `Fetch/XHR`, find the request that streams the answer (type
   `eventsource`/`fetch` with a long duration). Record: URL path pattern, method, response content
   type, framing (SSE `data:` lines, NDJSON, length-prefixed arrays, WebSocket frames). Copy the full
   response body into `tests/fixtures/<id>/stream-basic.txt`. **Redact** cookies, auth headers,
   account/org ids, emails (replace with `<redacted>`); the body itself usually contains only the
   answer. Also record *other* streaming requests that are **not** the answer (title generation,
   suggestions) so the `urlPattern` excludes them.
6. **Thread URL:** After the first answer, record how the URL changed (`/chat/<uuid>`, `/c/<id>`,
   `/app/<hex>`), and how long after the first token it changes.
7. **States:** Log out in a separate profile or private window and record the logged-out page (URL and
   a stable selector). Search the provider's help pages for the exact rate-limit message text. If you
   hit a limit, save the banner's HTML.
8. **Thinking models:** If the provider has a reasoning mode, record how thinking is shown (collapsible
   block selector) and how it appears in the stream (separate event type/field).
9. **DOM fixture:** Save a redacted DOM snapshot after completion (use the extension's snapshot
   feature once built; before that, `copy(document.documentElement.outerHTML)` in the console, then
   manually replace conversation text) to `tests/fixtures/<id>/dom-complete.html`, and one captured
   mid-stream to `dom-streaming.html`.
10. **Hidden-tab behaviour (L-19):** Start a long answer, immediately switch to another tab for 60 s,
    come back: did the DOM keep updating while hidden (check timestamps by logging from a
    `MutationObserver` you install in the console)? Did the network stream continue? Record results in
    `notes`.
11. Fill in the JSON config, set `configVersion`, `locale.verifiedWith`, and write a
    `tests/fixtures/<id>/RECON.md` with the date, browser version, plan tier (free/paid — UIs differ),
    and observations.

---

## 5. Per-provider notes (starting candidates — VERIFY)

Legend for confidence: **H** = long-stable, widely relied on; **M** = known recently, may have
changed; **L** = uncertain, discover during recon.

### 5.1 ChatGPT (`chatgpt`) — Tier 1

| Item | Candidate | Conf. |
|---|---|---|
| Hosts | `chatgpt.com` (`chat.openai.com` redirects here — include both in `hostPermissions`) | H |
| New chat | `https://chatgpt.com/` | H |
| Temporary chat | `https://chatgpt.com/?temporary-chat=true` | M |
| Thread URL | `https://chatgpt.com/c/<uuid>`; project/GPT chats: `/g/<gizmo-id>/c/<uuid>` | H |
| Composer input | `#prompt-textarea` — a ProseMirror `contenteditable` div. A hidden plain `<textarea>` may coexist: use `visible: true`. | H |
| Send button | `button[data-testid='send-button']`, `#composer-submit-button` | M |
| Stop button | `button[data-testid='stop-button']` | M |
| User turn | `[data-message-author-role='user']` | H |
| Assistant turn | `[data-message-author-role='assistant']` (one turn may contain several of these for multi-part answers — take the container `article[data-testid^='conversation-turn-']` as the turn and the last `.markdown` inside it as content) | H/M |
| Answer content | `.markdown` within the assistant turn | H |
| Completion | stop button disappears; turn action buttons appear (e.g. `[data-testid='copy-turn-action-button']`); net tap `[DONE]` | M |
| Code header | code blocks render a header bar with the language name and "Copy code" button above the `<pre>`'s code — exclude it and read the language from it or from `code[class*='language-']` | M |
| Net tap | `POST` to a path like `/backend-api/conversation` or `/backend-api/f/conversation`; SSE. The payload format has changed several times: older versions sent full message snapshots (`message.content.parts[0]` — emit `replace`), newer versions send a "delta encoding" of JSON-patch-like operations (`{"p": "/message/content/parts/0", "o": "append", "v": "…"}`, with abbreviated follow-ups `{"v": "…"}`), ending with `data: [DONE]`. The parser must support both and ignore unknown ops. Exclude title-generation and other endpoints. | M/L |
| States | logged out: login buttons (`[data-testid='login-button']`) on the home page; rate limit: text like "You've reached our limit" / "usage cap"; interrupt: A/B comparison "Which response do you prefer?" (two side-by-side answers) — policy in L-49. | M |
| Quirks | Reasoning models show a collapsible "Thought for Ns" section — exclude from answer. ChatGPT may show "Searching the web…" status rows inside the turn. Canvas answers render outside the turn. | M |

### 5.2 Claude (`claude`) — Tier 1

| Item | Candidate | Conf. |
|---|---|---|
| Host | `claude.ai` | H |
| New chat | `https://claude.ai/new` | H |
| Temporary chat | Incognito mode exists as a UI toggle; URL unknown → `null` until recon | L |
| Thread URL | `https://claude.ai/chat/<uuid>` | H |
| Composer input | `div.ProseMirror[contenteditable='true']` inside a `fieldset` | H |
| Send / Stop | `button[aria-label='Send message']` / `button[aria-label='Stop response']` (English UI) | M |
| User turn | `[data-testid='user-message']` | M |
| Assistant turn | element with `data-is-streaming` attribute (`"true"` while generating, `"false"` after) | M |
| Answer content | `.font-claude-response` / `.font-claude-message` (class names have changed before — keep both tiers) | M/L |
| Completion | `data-is-streaming="false"` (strong), stop disappears, net tap `message_stop` | M |
| Net tap | `POST /api/organizations/<org-uuid>/chat_conversations/<conv-uuid>/completion` (and `retry_completion`); SSE in an Anthropic-Messages-like shape: `message_start`, `content_block_start` (block `type`: `text`, `thinking`, `tool_use`), `content_block_delta` (`delta.type`: `text_delta` → text, `thinking_delta` → reasoning, `input_json_delta` → tool input, ignore), `content_block_stop`, `message_delta` (`stop_reason`), `message_stop`, plus `error` and possibly limit-related events. Older format: events with a `completion` string field. Support both. | M |
| States | logged out: redirect to `/login`; rate limit banners mention running out of messages / usage limit with a reset time. | M |
| Quirks | Artifacts render in a side panel; the stream carries their content inside tool-use or tagged blocks — v1 emits a warning `artifact_not_extracted` unless the parser can recover the text. Extended thinking appears as a collapsible block. | M/L |

### 5.3 Gemini (`gemini`) — Tier 1

| Item | Candidate | Conf. |
|---|---|---|
| Host | `gemini.google.com` | H |
| New chat | `https://gemini.google.com/app` (multi-account users: `/u/<n>/app` — keep the user's current account prefix: when the worker tab's URL has `/u/<n>/`, build new-chat URLs with it) | H |
| Thread URL | `https://gemini.google.com/app/<hex id>` (or `/u/<n>/app/<id>`) | H |
| Composer input | `rich-textarea .ql-editor[contenteditable='true']` (Quill) | H |
| Send / Stop | `button.send-button` / `button[aria-label*='Send']`; during generation the same area shows a stop control (`button[aria-label*='Stop']`) | M |
| User turn | `user-query` (custom element) | H |
| Assistant turn | `model-response` (custom element) | H |
| Answer content | `message-content .markdown` within `model-response` | M |
| Completion | stop control disappears; response footer/action buttons (`message-actions`) appear within the turn | M |
| Net tap | `StreamGenerate` endpoint under `/_/BardChatUi/data/…`; response starts with `)]}'` and contains length-prefixed chunks of nested JSON arrays whose inner strings are JSON-encoded again; each chunk tends to carry the **full text so far** (snapshot → `replace`). Hard to parse and highly volatile → **v1 is DOM-only** for Gemini (`netTap.enabled: false`). Revisit in v1.1. | L |
| States | logged out: a "Sign in" link to `accounts.google.com`; rate limit / quota messages appear inline in the response area. | M |
| Quirks | "Show drafts" alternatives (ignore, take the displayed draft); Deep Research and Canvas produce content outside the normal turn — out of scope, emit warning. Gemini sometimes renders images/cards inline. | M |

### 5.4 DeepSeek (`deepseek`) — Tier 2

| Item | Candidate | Conf. |
|---|---|---|
| Host / new chat | `chat.deepseek.com` / `https://chat.deepseek.com/` | H |
| Thread URL | `/a/chat/s/<id>` | M |
| Composer | `textarea#chat-input` (a real `<textarea>` → strategies `execCommand`, `nativeSetter`) | M |
| Send | a `div[role='button']` containing an icon, no stable label → use structural selector within the composer + `enter` strategy first | L |
| Net tap | `POST /api/v0/chat/completion`, SSE; JSON-patch-like events (`{"p": "response/content", "o": "APPEND", "v": "…"}`, short form `{"v": "…"}`), separate path for thinking content (`response/thinking_content`) when DeepThink is on | M/L |
| Quirks | "DeepThink" and "Search" toggles; server busy errors are common ("server is busy") → `states.error`. | M |

### 5.5 Grok (`grok`) — Tier 2

| Item | Candidate | Conf. |
|---|---|---|
| Host / new chat | `grok.com` / `https://grok.com/` | H |
| Thread URL | `/c/<id>` | M |
| Composer | `textarea` or a TipTap/ProseMirror editor (has changed) | L |
| Net tap | `POST /rest/app-chat/conversations/new` and `/rest/app-chat/conversations/<id>/responses`; **NDJSON** (one JSON object per line, not SSE) with tokens at a path like `result.response.token`; thinking tokens flagged separately | M/L |

### 5.6 Perplexity (`perplexity`) — Tier 2

| Item | Candidate | Conf. |
|---|---|---|
| Host / new chat | `www.perplexity.ai` / `https://www.perplexity.ai/` | H |
| Thread URL | `/search/<slug-or-id>` | M |
| Composer | `textarea` or Lexical `contenteditable` (has changed) | L |
| Net tap | SSE endpoint like `/rest/sse/perplexity_ask`; events carry **full snapshots** of a structured answer (blocks with markdown) → `replace` | L |
| Quirks | Answers contain citation markers `[1]` and a sources list; keep markers, optionally append sources as a markdown list (config flag). Search-first product: answers can take long before first token. | M |

### 5.7 Mistral Le Chat (`mistral`) — Tier 2

| Item | Candidate | Conf. |
|---|---|---|
| Host / new chat | `chat.mistral.ai` / `https://chat.mistral.ai/chat` | M |
| Thread URL | `/chat/<uuid>` | M |
| Composer | `textarea` or ProseMirror | L |
| Net tap | streaming fetch with a line-prefixed format (e.g. `0:"text"` lines in the style of a data-stream protocol) — confirm in recon | L |

### 5.8 Qwen (`qwen`) — Tier 2

| Item | Candidate | Conf. |
|---|---|---|
| Host / new chat | `chat.qwen.ai` / `https://chat.qwen.ai/` | M |
| Thread URL | `/c/<uuid>` | M |
| Composer | `textarea#chat-input` | M |
| Net tap | `/api/…/chat/completions` SSE in an OpenAI-like shape (`choices[0].delta.content`) with a `phase` field distinguishing thinking vs answer | M/L |

### 5.9 Kimi (`kimi`) — Tier 2

| Item | Candidate | Conf. |
|---|---|---|
| Host / new chat | `www.kimi.com` (older `kimi.moonshot.cn`) / home URL | M |
| Composer | `contenteditable` editor | L |
| Net tap | SSE with `{"event":"cmpl","text":"…"}`-style events historically; may have moved to a Connect/gRPC-web transport — confirm | L |

### 5.10 Tier 3 (later)

| Provider | Host | Notable |
|---|---|---|
| `copilot` | `copilot.microsoft.com` | Chat runs over a **WebSocket** with JSON events (`appendText`, `done`-like) → needs the WebSocket wrapper (`04` §6.3). |
| `meta` | `www.meta.ai` | GraphQL streaming responses; login via Meta/Facebook. |
| `huggingchat` | `huggingface.co/chat` | NDJSON stream with `{"type":"stream","token":…}`; open-source models. |
| `aistudio` | `aistudio.google.com` | gRPC-web style responses; DOM-only. Note: people often prefer the real Gemini API here, since AI Studio is a developer product. |
| `zai` | `chat.z.ai` | OpenAI-like SSE. |

---

## 6. Adding a new provider — checklist

1. Run the recon procedure (§4); commit fixtures and `RECON.md`.
2. Create `src/providers/<id>.json` from the closest existing config; fill every field.
3. If net tap: write `src/providers/parsers/<id>.js` and unit tests against the fixture streams.
4. Add `<id>` to `src/providers/index.json`.
5. `npm run build` (validates config, regenerates manifest permissions).
6. Add DOM-fixture tests (`09` §3) for `composer.input`, `turns.assistant`, `answer.content`, and
   markdown extraction against `dom-complete.html`.
7. Run the live smoke test (`09` §4) in Chrome and Firefox.
8. Default the provider to `enabled: false` until step 7 passes three times in a row.
