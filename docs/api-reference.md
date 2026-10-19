# API reference

> Target-state guide (see README status note). Normative design: `spec/07-bridge-server-spec.md` and
> `spec/13-api-keys-and-openai-compat.md`.

Base URL: `http://127.0.0.1:8787/v1` · Auth: `Authorization: Bearer sk-w2a-…` ([API keys](api-keys.md)) ·
JSON in, JSON or Server-Sent Events out.

## Supported endpoints

| Endpoint | Status |
|---|---|
| `POST /v1/chat/completions` | ✔ streaming and non-streaming |
| `GET /v1/models`, `GET /v1/models/{model}` | ✔ |
| `GET /healthz` | ✔ no auth, returns `{"ok": true}` |
| `/web2api/*` admin endpoints | ✔ need an `admin`-scope key |
| `/v1/completions`, `/v1/embeddings`, images, audio, files, assistants, batches | ✘ → 404 `unsupported_endpoint` |
| `/v1/responses` | ✘ in 1.0 (planned); use chat completions |

## `POST /v1/chat/completions`

### Request

| Field | Support |
|---|---|
| `model` (required) | `claude`, `chatgpt`, `gemini`, `provider/variant`, `auto`, or an alias like `gpt-4o`. See `GET /v1/models`. |
| `messages` (required) | Roles `system`/`developer`, `user`, `assistant`. `content` is a string or an array of `{"type":"text"}` parts. Images/audio/files → 400 `UNSUPPORTED_CONTENT`. The **last** message must be from `user`. |
| `stream` | ✔ SSE (below). `stream_options.include_usage` ✔. |
| `stop` | ✔ applied to the final text after generation (up to 4 strings). |
| `response_format` | `text` ✔. `json_object`/`json_schema`: Web2API asks the model for pure JSON and unwraps code fences; invalid JSON is returned as-is with warning `json_invalid`. |
| `n` | only 1 |
| `temperature`, `top_p`, `max_tokens`, `max_completion_tokens`, penalties, `seed`, `logit_bias`, `user`, `metadata` | accepted and **ignored** (the web UI has no such controls); the response header `X-Web2API-Ignored-Params` lists what was ignored |
| `logprobs`, `top_logprobs` | 400 if truthy |
| `tools`, `tool_choice` | 400 in 1.0 (planned) |
| `web2api` (via the SDK's `extra_body`) | `{"thread": "new" \| "current" \| "<thread URL>", "history_mode": "normal" \| "temporary", "include_reasoning": false, "timeouts": {"total_ms": 300000}, "extract": ["code_blocks"]}` |

Header alternatives: `X-Web2API-Thread`, `X-Web2API-History-Mode`. Unknown fields are ignored.

### Response (non-streaming)

```json
{
  "id": "chatcmpl-job01JAZ…", "object": "chat.completion", "created": 1760960000,
  "model": "claude/default",
  "choices": [{ "index": 0, "message": {"role": "assistant", "content": "PONG"}, "finish_reason": "stop" }],
  "usage": { "prompt_tokens": 9, "completion_tokens": 2, "total_tokens": 11, "estimated": true },
  "web2api": {
    "provider": "claude", "model_label": "Claude Sonnet 4.5",
    "thread_url": "https://claude.ai/chat/…", "continued": false,
    "source": "net", "warnings": [], "timings": {"queued_ms": 0, "first_token_ms": 1650, "total_ms": 3100}
  }
}
```
* `usage` is an **estimate** (≈ 4 characters per token); `estimated: true` marks it.
* `web2api` is an extra object; ignore it if you don't need it.
* `message.content` is Markdown, as the site rendered it (code fences, tables, lists, math as `$…$`).
* With `include_reasoning`, thinking text (when the site shows it) is in `message.reasoning_content`.

### Streaming

`"stream": true` returns `text/event-stream`: a role chunk, content chunks (`delta.content`), a final
chunk with `finish_reason`, optionally a usage chunk, then `data: [DONE]`. While the site is thinking or
queued you get SSE comments (`: keepalive`) that compliant clients ignore. If an error happens after
streaming started, you receive `data: {"error": {…}}` followed by `[DONE]`.
If your client disconnects, Web2API stops the generation in the browser.

### Conversation handling

Web chats are stateful; OpenAI's API is not. Web2API bridges the gap:

* **Continuation:** if your `messages` equal a conversation Web2API already ran plus new user
  message(s), only the new message(s) are typed into the same web chat (`web2api.continued: true`).
* **Fresh start:** otherwise a new web chat is opened and the whole conversation is sent once as a
  clearly-delimited transcript (system prompt first).
* **Override:** `web2api.thread` = `"new"` always starts fresh; a thread URL continues that exact
  chat; `"current"` uses the provider's assigned tab as-is.
* Trimming or editing earlier messages (e.g. a client that shortens history) causes a fresh chat —
  correct, just less efficient.
* Everything appears in your provider's history unless `history_mode = "temporary"` and the provider
  supports temporary chats.

## `GET /v1/models`

```json
{ "object": "list", "data": [ {"id": "claude/default", "object": "model", "created": 0, "owned_by": "web2api:claude"} ] }
```
Lists providers that are ready now and that your key may use, plus `auto` and aliases. Empty list →
no extension connected / nothing ready (not an error). `GET /v1/models/{id}` returns one entry or 404.

## Errors

Always OpenAI-shaped:
```json
{ "error": { "message": "Claude is showing a login page. Log in to claude.ai in your browser.",
             "type": "web2api_error", "code": "LOGIN_REQUIRED", "param": null,
             "web2api": {"provider": "claude", "partial_text": null} } }
```
Status codes: 400 bad request, 401/403 auth, 404 unknown model/endpoint, 429 rate limits (with
`Retry-After`), 502/503/504 browser/provider problems. Every code and its fix:
[Error codes](errors.md). Timeouts return an **error** (with any partial text in
`error.web2api.partial_text`) — never a silent truncated "success".

## Limits

* Body ≤ 5 MB; prompt ≤ 200 000 characters (configurable).
* One prompt per worker tab at a time; extra requests queue (up to 60 s, then 503 `NO_CAPACITY`).
* Answer time limit 5 minutes by default (`timeouts.total_ms`).
* Minimum delay between prompts to the same provider (default 3 s) to stay human-plausible.

## Admin endpoints (`admin` scope)

`GET /web2api/status`, `/web2api/providers`, `/web2api/jobs`, `/web2api/health/reports`,
`/web2api/threads`, key management under `/web2api/keys`, config overrides under
`/web2api/config/{provider}`. Responses never contain prompts or answers. Full list: `spec/07` §9.
