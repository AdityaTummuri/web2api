# 10 — Implementation Plan

The ordered task list. Each phase lists **tasks**, the **files** involved, and **acceptance criteria**
(AC). Do not start a phase until the previous phase's AC all pass. Commit after each task with a
conventional-commit message (`feat(extension): …`, `feat(bridge): …`, `test: …`, `chore: …`,
`docs: …`).

If something in the spec is contradictory, impossible, or turns out wrong on the live site, **stop,
write down what you found** (in `spec/OPEN_QUESTIONS.md`, creating it if needed) and continue with the
parts that are unaffected. Never silently diverge from the spec.

---

## Phase 0 — Repository housekeeping (½ day)

**Tasks**
1. Create `archive/playwright-gemini/` and `git mv` into it: `server.py`, `session_manager.py`,
   `setup_session.py`, `templates/`, `ask-gemini.sh`, `README.md`, `docs/`. Add
   `archive/README.md` (5–10 lines: what it was, why archived — link `spec/01` §4).
2. Leave `bridge_server.py`, `extension/`, `start.sh`, `requirements.txt` in place for now (the
   prototype keeps working until replaced). Rename `extension/` → `extension-prototype/` with `git mv`
   so the new `extension/` can be created cleanly. Update `.gitignore` (`extension/node_modules/`,
   `extension/dist/`, `bridge/.venv/`, `extension-prototype/node_modules/`).
3. Create the empty skeleton directories from `03` §5 with `.gitkeep` where needed.
4. Write a short placeholder `README.md` at the root: one paragraph + "see `spec/00-README.md`".

**AC**
- `git status` clean after commit; `git log --stat` shows moves (not delete+add) for archived files.
- Prototype still runs: `uv run --with-requirements requirements.txt python bridge_server.py` starts.

---

## Phase 1 — Recon & platform spike (1–2 days, needs the owner's browser)

The goal is to replace assumptions with facts **before** writing the driver. If you (the implementer)
have browser automation available (e.g. Claude in Chrome), you can do the DOM/network recon yourself
on the owner's logged-in browser; otherwise prepare exact instructions and ask the owner to run them.

**Tasks**
1. **Provider recon** for `chatgpt`, `claude`, `gemini` following `05` §4 exactly. Output per provider:
   `extension/tests/fixtures/<id>/RECON.md`, `dom-complete.html`, `dom-streaming.html`,
   `stream-basic.txt` (+ `stream-thinking.txt` if available), and an expected-markdown file for each
   (`*.expected.md`, produced by clicking the provider's own "Copy" button on the answer and pasting).
2. **Platform spike** — a throwaway mini extension in `spikes/platform/` (delete or archive after) that
   answers, in both Chrome and Firefox:
   a. Does a WebSocket from the background to a local echo server stay open for 10 minutes with a
      20 s ping? Does the background survive? (Chrome service worker, Firefox event page.) If Firefox
      suspends, does calling `chrome.runtime.getPlatformInfo()` every 20 s prevent it?
   b. Does a `world: "MAIN"`, `run_at: "document_start"` content script run before the page's own
      scripts on each tier-1 provider, so that wrapping `fetch` catches the completion request?
   c. Does the MessageChannel handshake (`04` §6.4) work in both browsers?
   d. Does `ClipboardEvent` with `clipboardData` init work for synthetic paste in Firefox on each
      provider? (Known risk.)
   e. Hidden-tab behaviour per provider: with the worker tab in the background for 6+ minutes, does
      (i) the network stream complete, (ii) the DOM update, (iii) `MutationObserver` fire? Same with a
      dedicated non-minimized window.
   f. Is a host permission needed for `ws://127.0.0.1` from the background in each browser?
3. Write `spikes/platform/RESULTS.md` with a yes/no table and notes, and update the spec where the
   facts differ (e.g. if Firefox needs a different keepalive, edit `04` §3.3; record the change in
   `spec/OPEN_QUESTIONS.md` → "resolved").

**AC**
- Fixtures exist for all three tier-1 providers and contain **no** personal data (grep for the owner's
  email, name, org ids; must find nothing).
- `RESULTS.md` answers every question a–f for Chrome and Firefox.
- Any spec changes are committed separately with a message explaining the evidence.

---

## Phase 2 — Extension foundation + DOM driver, popup test only (3–5 days)

No bridge yet. The popup "Test" section drives jobs locally so the driver can be validated in isolation.

**Tasks**
1. `extension/package.json`, `scripts/build.mjs`, `manifests/*.json` per `04` §2. Generated files:
   manifest permissions/content scripts, `content/provider-hosts.js`,
   `providers/generated/<id>.nettap.js` (can be empty arrays until Phase 4).
2. `src/shared/protocol.js` (all constants from `06`), `logger.js` (redaction), `util.js`.
3. `src/providers/schema.json` and the tier-1 provider configs, filled from Phase 1 recon (not from
   the candidates in `05` §5). `netTap.enabled: false` for all in this phase.
4. Config validation + merge (`background/config-store.js` without overrides UI yet) + unit tests
   (`09` §2.5).
5. `content/dom.js` (resolve, tiers, visibility, scoring, waitFor) + DOM fixture tests.
6. `content/extract/markdown.js` (port + fix the prototype parser per `04` §5.7) + unit tests (`09` §2.1)
   + fixture extraction tests.
7. `content/injector.js` (port from inspo with clear + verify), `submitter.js`, `observer.js`,
   `completion.js`, `states.js`, `driver.js`, `bootstrap.js` per `04` §5.
8. `background/main.js`, `settings.js`, `tab-pool.js` (single tab per provider is enough in this
   phase, but implement the claiming rules — opened vs assigned — and never touch unclaimed tabs),
   `job-runner.js` with a local entry point used by the popup.
9. `popup/` minimal: Providers section (open worker tab / use current tab) + Test section (run,
   stream text into a `<pre>`, stop).

**AC**
- `npm test` passes (unit + DOM fixture tests from `09` §2.1, 2.4, 2.5, §3).
- `npm run build` produces loadable extensions; loading in Chrome and Firefox shows no errors in the
  extension error pages.
- Manual: for each tier-1 provider in Chrome, the popup Test runs "Reply with exactly PONG" and
  "Write a python hello world and a 2x2 table" and shows correct markdown; multi-line prompts arrive
  with newlines intact; a long answer (≥ 1000 words) is complete (compare with the page); the user's
  own open chat tab on the same provider is never used.
- Manual: Firefox — same, at least for one provider (record gaps in `OPEN_QUESTIONS.md`).
- Manual: logged-out provider → `LOGIN_REQUIRED` shown in the popup within 5 s.

---

## Phase 3 — Bridge v1 (non-streaming) + extension bridge client (3–4 days)

**Tasks**
1. `bridge/pyproject.toml`, package skeleton, `cli.py` (tokens, banner), `config.py`.
2. `security.py` (Host check, bearer auth, WS origin/token) + `test_security.py`.
3. `protocol.py`, `errors.py` + tests (incl. constants parity test with `protocol.js`).
4. `hub.py` (connections, handshake, duplicate instance handling, jobs, request/response,
   heartbeat), `router.py`, `fake_extension.py` + integration tests.
5. `openai_compat/schemas.py`, `chat.py` (non-streaming only, conversation mapping stubbed to "always
   fresh start" with the transcript template), `models.py`.
6. Extension: `background/bridge-client.js` (state machine, backoff, keepalive, close-code handling),
   wire `job-runner.js` to bridge `JOB_*` frames, `PROVIDERS_UPDATE`, popup Connection section
   (bridge URL, pairing token, status).
7. Remove the root `bridge_server.py`, `requirements.txt`, and the old `start.sh`; replace `start.sh`
   with a 10-line wrapper (`cd bridge && exec uv run web2api-bridge "$@"`) or remove it. Remove
   `extension-prototype/` (its useful parts are ported) — keep it if the owner prefers; ask in
   `OPEN_QUESTIONS.md`.

**AC**
- `uv run pytest` passes, including all integration scenarios from `09` §6 that don't involve
  streaming, and the security tests.
- Manual: `curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8787/v1/chat/completions -d
  '{"model":"claude","messages":[{"role":"user","content":"Reply with exactly PONG"}]}'` returns a
  valid `chat.completion` for each tier-1 provider.
- Manual: the official OpenAI Python SDK works with `base_url="http://127.0.0.1:8787/v1"`,
  `api_key=<api token>`, `model="chatgpt"` (non-streaming).
- Manual: killing and restarting the bridge → extension reconnects within 30 s without user action.
- Manual: wrong pairing token → popup shows "Pairing token rejected" and stops retrying.

---

## Phase 4 — Streaming, net tap, cancellation (4–6 days)

**Tasks**
1. `providers/parsers/sse.js` + tests (`09` §2.2).
2. `providers/parsers/chatgpt.js`, `claude.js` + tests against Phase 1 stream fixtures (`09` §2.3).
3. `main-world/net-tap.js` (fetch/XHR wrappers, Proxy, MessageChannel, registration hook cleanup) and
   `content/nettap-relay.js`; arm/bind logic; enable `netTap` in chatgpt/claude configs.
4. Driver: net-tap-first extraction, DOM fallback, debug-mode divergence check (`04` §5.7); DOM-path
   deltas with stable-prefix policy (`04` §5.9); delta relay through job-runner and bridge client.
5. Cancellation end to end (`04` §5.8, `06` §5.7, bridge client-disconnect detection `07` §6.3).
6. Bridge: SSE streaming exactly per `07` §6.3 (role chunk, keepalives, deltas, suffix on done, final
   chunk, usage chunk, web2api chunk, `[DONE]`, error events), stop-sequence handling, auto-retry rule
   (`06` §7).

**AC**
- All tests pass, including streaming integration tests (exact SSE format) and parser fixture tests.
- Manual: OpenAI SDK `stream=True` prints tokens progressively for chatgpt and claude (net tap) and
  gemini (DOM deltas).
- Manual: for chatgpt and claude, `web2api.source == "net"`; markdown equals the provider's own Copy
  output for the Phase 1 test prompt (exact match or documented whitespace-only differences).
- Manual: Ctrl-C a streaming client mid-answer → the provider's generation stops in the tab within
  5 s; the next request works.
- Manual: in a provider page, `window.fetch.toString()` still prints `function fetch() { [native code] }`
  and `Object.keys(window).filter(k => k.includes("w2a"))` is empty.

---

## Phase 5 — Conversation mapping, full tab pool, states (3–4 days)

**Tasks**
1. `conversations.py` fully per `07` §5 + tests (`09` §2.6); thread URL/`tabId` recording from
   `JOB_DONE`; `persist_threads` option.
2. Extension: thread URL capture (`urls.threadPattern`), `target.mode = continue/current` navigation
   (`04` §4.4), temporary history mode where the provider supports it.
3. Tab pool: pool sizes > 1, FIFO queue with timeout, thread affinity, min delay, dirty-tab recovery,
   dedicated worker window mode (`04` §4.5), content-script presence/injection (`04` §4.7),
   `PROVIDERS_UPDATE` debounce.
4. States: full `states.js` coverage incl. rate-limit `retryAfterSec` parsing where the banner shows a
   time; interrupt handling policy for ChatGPT A/B comparisons.
5. Extension restart recovery (`04` §3.2): jobs failed with `EXTENSION_RESTARTED`, tabs re-verified.

**AC**
- Tests pass.
- Manual: a 4-turn conversation via the OpenAI SDK (client keeps history) results in **one** web chat
  thread with 4 user messages (not a growing transcript); `web2api.continued` true for turns 2–4.
- Manual: editing an earlier message in the client history → a new web chat with a transcript.
- Manual: with `poolSize: 2` for claude, two concurrent requests run in two tabs in parallel; a third
  waits and then runs.
- Manual: smoke script (`09` §4.1) passes for all tier-1 providers in Chrome.

---

## Phase 6 — Health, overrides, admin API, docs (3 days)

**Tasks**
1. `background/health.js` (passive metrics, probes, reports), `content/snapshot.js` (redaction per
   `04` §9.3), storage ring buffers.
2. Overrides: config-store `applyOverride/revert`, bridge `CONFIG_*` frames, popup import/revert.
3. Admin API per `07` §9.
4. Popup Health and Settings sections; badge states.
5. Root `README.md`: what it is, ToS/account-risk warning (L-47), install (bridge + extension for
   Chrome and Firefox), pairing, using with OpenAI SDK / curl / common tools, model ids, thread
   behaviour and its limitations, troubleshooting by error code, privacy notes (history mode,
   logging).
6. `docs/` (new): `providers.md` (status table, per-provider quirks for users), `troubleshooting.md`.

**AC**
- Tests pass, including snapshot redaction tests (a fixture containing the text "SECRET-CONVERSATION"
  produces a snapshot without it, while button labels like "Send message" remain).
- Manual: break `composer.send` via an override → next job returns `SELECTOR_NOT_FOUND`, a health
  report and a snapshot appear in the popup and in `GET /web2api/health/reports`; revert fixes it.
- Manual: a fresh person can follow the README from zero to a working curl call.

**→ v1 complete.**

---

## Phase 7 — Tier-2 providers (v1.1, ~1 day per provider)

For each of `deepseek`, `grok`, `perplexity`, `mistral`, `qwen`, `kimi`: follow `05` §6 (recon →
config → optional parser → tests → smoke). Ship each with `enabled: false` default until it passes
smoke three times. Gemini net tap can be attempted here too.

---

## Phase 8 — Later (not v1; design notes exist)

| Item | Where designed |
|---|---|
| Tool-calling emulation | `07` §8 |
| Model variant selection | `04` §5.12 |
| Image/file inputs | L-48 |
| Firefox `webRequest.filterResponseData` net-tap transport | `04` §6.6 |
| Anthropic Messages-compatible endpoint (`/v1/messages`) | — (mirror §6 of `07`) |
| MCP server | `11` |
| Maintainer agent | `11` |
| Native Messaging transport | `03` D2 |

---

## Effort summary

| Phase | Estimate |
|---|---|
| 0 Housekeeping | 0.5 d |
| 1 Recon & spike | 1–2 d |
| 2 Extension + DOM driver | 3–5 d |
| 3 Bridge v1 | 3–4 d |
| 4 Streaming + net tap | 4–6 d |
| 5 Conversations + pool | 3–4 d |
| 6 Health + docs | 3 d |
| **v1 total** | **~18–25 working days** of focused implementation |
