# 09 — Testing Strategy

Four layers, from fastest to slowest. Layers 1–3 run in CI/`npm test`/`uv run pytest` with no browser
and no network. Layer 4 needs the real browser and real accounts and is run by a human (and later by
the maintainer).

| Layer | What | Tooling | Runs |
|---|---|---|---|
| 1. Unit | Pure functions: markdown conversion, SSE splitter, stream parsers, diff/stable-prefix, config merge/validation, fingerprints, transcript builder, error mapping. | `node:test` (extension), `pytest` (bridge) | Every change |
| 2. DOM fixture | Driver pieces against captured provider HTML: selector resolution, turn identification, completion signals, extraction, state detection, injector strategies (where jsdom allows). | `node:test` + `jsdom` | Every change |
| 3. Integration | Bridge with a **fake extension** over a real WebSocket; extension background modules with a fake bridge and fake tabs. | `pytest` + `httpx` + `websockets` client from Starlette's `TestClient`; Node with stubbed `chrome.*` | Every change |
| 4. Live smoke | Real browser, real logged-in accounts, real sites. | Manual script + checklist; later automated by the maintainer | Before each release; after any provider config change |

---

## 1. Conventions

* Extension tests: `extension/tests/unit/*.test.js`, `extension/tests/dom/*.test.js`. Run with
  `npm test` (`node --test tests/unit tests/dom`).
* Content scripts are classic scripts attaching to `globalThis.W2A`. To test them in Node, load them
  into a jsdom window: `const dom = new JSDOM(html, { url, runScripts: "outside-only" });
  dom.window.eval(fs.readFileSync(file, "utf8"))` — in load order — then call `dom.window.W2A.*`.
  Write a helper `tests/helpers/load-content.js` that does this for the standard script list.
* Bridge tests: `bridge/tests/test_*.py`, `pytest-asyncio` in auto mode.
* No test may hit the real network.

## 2. Layer 1 — unit tests (minimum required set)

### 2.1 Markdown (`content/extract/markdown.js`)
Each case: HTML input string → expected markdown string. At least:
- paragraphs and line breaks; whitespace collapsing; NBSP handling
- headings h1–h6
- nested unordered list 3 levels; ordered list with `start="3"`; list item containing a paragraph and
  a code block
- inline code containing a backtick (uses double-backtick fence)
- code block with `language-python` class; with `data-language`; with a header label element
  configured via `codeHeader`/`codeLanguageLabel` (label must not leak into output); code containing
  ``` (uses ```` fence); leading indentation preserved
- table with header, escaped pipes, `colspan`
- links: relative → absolute; `javascript:` dropped
- images (http src kept, data: src dropped)
- KaTeX inline and display math (with `annotation[encoding="application/x-tex"]`) → `$…$` / `$$…$$`
- strikethrough
- excluded elements (thinking block, buttons, svg) removed
- the 4 existing tests from `extension/test_parser.js` ported where still applicable

### 2.2 SSE splitter (`providers/parsers/sse.js`)
- multi-line `data:` concatenation; `event:` names; comments; CRLF/LF/CR line endings
- chunk boundaries at every byte position of a sample (loop over split points)
- trailing event without final blank line is flushed only by `end()`

### 2.3 Stream parsers (`providers/parsers/<id>.js`)
For each provider with net tap:
- Feed `tests/fixtures/<id>/stream-*.txt` in random-sized chunks (seeded); assert the concatenated
  `text` events (with `replace` applied) equal `tests/fixtures/<id>/stream-*.expected.md`.
- Assert a `done` event exists with the right `finishReason`.
- Assert reasoning text is separated (fixture with thinking).
- Assert unknown event types don't throw (inject a synthetic unknown event into the sample).
- Assert malformed JSON line is skipped and counted.

### 2.4 Stable-prefix / delta logic (`content/observer.js` helper)
- growing text → correct deltas
- text with an unclosed code fence → tail withheld until fence closes
- earlier text changes → no further deltas + `stream_divergence` warning

### 2.5 Config (`background/config-store.js`, schema validator)
- every bundled provider config validates
- merge patch: object merge, array replace, null delete
- override rejected when: wrong `baseConfigVersion`; touches `match`/`netTap.parsers`/`id`; invalid
  CSS; invalid regex; regex > 500 chars; URL outside host permissions; contains `javascript:`
- `(?i)` prefix converted to the `i` flag

### 2.6 Bridge units (pytest)
- `conversations.normalize`: string / parts / null content; unsupported parts → error
- fingerprint stability (whitespace/CRLF variations map to the same fp)
- `plan()`:
  - single user → new, verbatim prompt
  - system + user → new, system template
  - multi-turn with no record → new, transcript template, tag escaping
  - prefix matches record → continue, prompt = tail only
  - prefix matches but record busy → new
  - assistant-last → 400
  - explicit `thread: "new"` / `"current"` / URL
  - after `record_done`, a follow-up request continues
- router: aliases, `auto` ordering, unknown provider → 404 model_not_found, variant missing
- errors: code → status/type mapping; OpenAI body shape
- stop-sequence truncation incl. sequences spanning chunk boundaries
- `protocol.py` constants equal to those in `extension/src/shared/protocol.js` (parse the JS file with a
  regex over `MSG` and `ERR` objects)
- JSON schema copy identical to `extension/src/providers/schema.json`

## 3. Layer 2 — DOM fixture tests

Fixtures per provider (from recon, `05` §4): `dom-complete.html`, `dom-streaming.html`,
`dom-logged-out.html` (if captured), `dom-rate-limited.html` (if captured).

For each provider:
- `resolve("composer.input")` finds exactly the expected element (fixture marks it with a test-only
  attribute added during capture, e.g. `data-w2a-expect="composer.input"`; the test asserts the
  resolved element has it; the resolver must not *use* that attribute).
- Same for `composer.send`, `composer.stop` (streaming fixture), `turns.user`, `turns.assistant`,
  `answer.content`.
- Tier-fallback test: remove the attribute tier 0 relies on (via DOM manipulation in the test) and
  assert tier 1 still resolves and reports `tier: 1`.
- Completion: on `dom-streaming.html` the engine reports not-done; mutate the DOM to the completed
  state (or load `dom-complete.html`) and assert done with the expected strong signal.
- Extraction: markdown of the last assistant turn in `dom-complete.html` equals
  `dom-complete.expected.md` (hand-verified once against the provider's own "copy" button output).
- States: logged-out/rate-limited fixtures → correct state.
- Turn identification: given `before` captured on a fixture, append a new user turn and assistant turn
  (cloned nodes) and assert the observer picks the new assistant turn, not an old one, not the user turn.
- Destructive-action guard (`08` §4.3).

jsdom limitations to account for: no layout (`getBoundingClientRect` returns zeros) — stub
`isVisible` via a test hook that treats elements without `hidden`/`display:none` inline style as
visible; `execCommand` is not implemented — injector tests cover the strategy *selection and
verification logic* with a fake editor; the real insertion is covered by Layer 4.

## 4. Layer 4 — live smoke tests

### 4.1 Manual script (Phase 4 onwards)

`bridge/scripts/smoke.py` (uses only `httpx`): for each provider id given on the command line:
1. `GET /web2api/providers` — provider routable.
2. Non-streaming: "Reply with exactly the word PONG." → content contains `PONG`; record latency.
3. Streaming: "Count from 1 to 30, one number per line." → ≥ 3 chunks received; final text has 30
   lines; concatenated chunks == final text.
4. Markdown fidelity: "Return a python code block that prints hello, then a 2x2 markdown table." →
   response contains a ```python fence and a table separator row.
5. Continuation: send 2-turn conversation using the previous answer → `web2api.continued == true`
   and the answer references the earlier turn (prompt: "What number did you end on?" → contains 30).
6. Cancel: start a long streaming prompt ("Write 1500 words about rivers"), disconnect after 3
   chunks → `GET /web2api/jobs` shows the job `cancelled`; a following short prompt succeeds (tab
   recovered).
7. Print a table: provider × test → pass/fail/latency.

### 4.2 Manual checklist per release

- [ ] Chrome and Firefox: install from `dist/`, pair, connect.
- [ ] Each tier-1 provider passes `smoke.py`.
- [ ] Worker tab not created in the user's active tab; user's own open chat untouched.
- [ ] Hidden-tab behaviour: run smoke with the worker window minimized (expect slower or documented
      behaviour) and in dedicated mode (expect normal).
- [ ] Log out of one provider → requests fail fast with `LOGIN_REQUIRED` and a helpful message.
- [ ] Kill the bridge mid-job → extension reconnects; job failed with clear error; next job succeeds.
- [ ] Reload the extension mid-job → bridge reports `EXTENSION_RESTARTED`; next job succeeds.
- [ ] Health check from popup shows all providers healthy.
- [ ] Apply a deliberately broken override (wrong `composer.send`) → `SELECTOR_NOT_FOUND`, health
      report + snapshot produced; revert restores function.

## 5. Security tests

Automate the checklist in `08-security.md` §7 in `bridge/tests/test_security.py` (HTTP and WS) and
`extension/tests/dom/guard.test.js` (destructive-action guard).

## 6. Fake extension (bridge integration tests)

`bridge/tests/fake_extension.py`: an async client using Starlette's `TestClient.websocket_connect`
(or the `websockets` library against a live uvicorn on a random port) that:
- sends `HELLO` (configurable token/version/origin header),
- sends `PROVIDERS_UPDATE` with configurable providers,
- on `JOB_START`, plays a scripted scenario: `accept → progress → deltas → done`, or errors at a given
  phase with `submitted` true/false, or stalls, or disconnects mid-job,
- records received frames for assertions (e.g. that `JOB_CANCEL` arrived after the HTTP client
  disconnected).

Integration tests must cover: non-streaming success; streaming success (exact SSE byte format
including role chunk, `[DONE]`, usage chunk); error before stream → proper HTTP status; error mid-stream →
error event + `[DONE]`; auto-retry happens only when `submitted=false`; client disconnect → `JOB_CANCEL`;
duplicate instance replacement doesn't drop the new connection (L-05 regression test); `/v1/models` with
0 and 2 connections.
