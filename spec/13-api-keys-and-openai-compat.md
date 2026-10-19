# 13 — API Keys and the OpenAI Compatibility Contract

Supersedes the single "API token" in `07` §2 and `08` §3.1/§3.5. The bridge issues **real API keys**
that look and behave like OpenAI keys, so any OpenAI-compatible tool accepts them. This document also
fixes the exact OpenAI compatibility surface and how it is verified.

---

## 1. API keys

### 1.1 Format

```
sk-w2a-<48 characters from [A-Za-z0-9]>        e.g.  sk-w2a-9fKq2ZxT4mNb7VcL0aRyH3uWdEj8PsGt5QoIe1XkMn6BvAy
```
* Prefix `sk-` because several clients and UIs validate it (OpenAI-style); `w2a` identifies the issuer
  so leaked keys are recognisable (secret scanners can match `sk-w2a-`).
* Random part: 48 chars from `secrets` (e.g. `"".join(secrets.choice(ALPHABET) for _ in range(48))`),
  ≈ 285 bits.
* **Never confused with the pairing token** (`w2a_pair_…`, extension ↔ bridge only, `08` §3.2). A key
  must never be accepted on the WebSocket and the pairing token never on HTTP.
* Each key also has a public **key id**: `key_` + 8 chars (used in logs, CLI, admin API; safe to
  show). Logs and errors only ever show the id or a masked form `sk-w2a-…Kn6B` (last 4 chars).

### 1.2 Storage (`keys.json`, config dir, 0600)

```json
{
  "schema": 1,
  "keys": [
    {
      "id": "key_a1b2c3d4",
      "name": "cursor",
      "hash": "sha256:<64 hex>",
      "prefixHint": "sk-w2a-9fKq",
      "createdAt": "2026-10-21T10:00:00Z",
      "expiresAt": null,
      "revokedAt": null,
      "scopes": ["chat"],
      "providers": ["*"],
      "rateLimit": { "requestsPerMinute": 30, "maxConcurrent": 2 },
      "lastUsedAt": null,
      "stats": { "requests": 0, "errors": 0 }
    }
  ]
}
```
* Only the **SHA-256 hash** is stored (keys are high-entropy random strings, so a fast hash is
  appropriate; no password-hashing KDF needed). The plaintext key is shown **once** at creation.
* Writes are atomic (temp → fsync → `os.replace`, `12` §5.1) and serialised with the same advisory
  lock as other state (`12` §5.2).
* `lastUsedAt`/`stats` are updated in memory and flushed at most every 60 s and on shutdown (don't
  write the file on every request).
* Hot reload: the bridge re-stats `keys.json` (cheap `os.stat`) at most once per second when a request
  arrives; if mtime changed it reloads. So `keys revoke` on the CLI takes effect on the next request
  without restarting, and a revoked key can never be used again.

### 1.3 Scopes and provider restrictions

| Scope | Allows |
|---|---|
| `chat` | `/v1/chat/completions`, `/v1/models*` |
| `tasks` | the tasks API (`/web2api/tasks*`) and the MCP server (`/mcp`, `web2api-bridge mcp`) — added in v2.0.0, see `14` §8 |
| `admin` | everything else under `/web2api/*` (status, health, config overrides, keys management, jobs) |

`providers`: `["*"]` or a list of provider ids; a request for a model whose provider isn't allowed →
403 (`permission_error`, code `provider_not_allowed`), and `/v1/models` lists only allowed models.
Least privilege by default: `keys create` makes `chat`-only keys unless `--admin` is given.

### 1.4 Authentication behaviour

* Accept `Authorization: Bearer <key>` (primary) and `X-API-Key: <key>` (for clients that mimic
  Anthropic's header). Case-insensitive scheme. Query-string keys are **never** accepted.
* Lookup: hash the presented key, find the record whose hash matches using
  `hmac.compare_digest` over all active records (a handful), so timing doesn't reveal which prefix
  matched.
* Failure responses (OpenAI-shaped, with `WWW-Authenticate: Bearer realm="web2api"`):
  | Case | Status | `error.code` | message |
  |---|---|---|---|
  | No key | 401 | `missing_api_key` | "You didn't provide an API key. Pass `Authorization: Bearer sk-w2a-…`. Create one with `web2api-bridge keys create`." |
  | Unknown/malformed | 401 | `invalid_api_key` | "Incorrect API key provided: sk-w2a-…Kn6B." (masked, like OpenAI) |
  | Revoked | 401 | `invalid_api_key` | "This API key has been revoked." |
  | Expired | 401 | `invalid_api_key` | "This API key has expired." |
  | Missing scope | 403 | `insufficient_scope` | "This key does not have the `admin` scope." |
  | Provider not allowed | 403 | `provider_not_allowed` | "This key may not use provider `claude`." |
  | Rate limited | 429 | `rate_limit_exceeded` | "Rate limit reached for this key (30/min). Retry in 12 s." + `Retry-After` |
  | Too many concurrent | 429 | `concurrency_limit_exceeded` | |
* **Brute-force damping:** after 10 failed authentications within 60 s from the same peer address,
  answer every request from it with 429 for the next 60 s (loopback-only bridge makes this mostly
  defence in depth).
* `GET /healthz` stays unauthenticated and returns only `{"ok": true}`.

### 1.5 Rate limiting

Per key, in memory: token bucket (`requestsPerMinute`, burst = same value) and a semaphore for
`maxConcurrent` (counts running + queued jobs). Defaults: 60 req/min, 4 concurrent. Because the
real bottleneck is the web UI (one prompt per tab), these limits mostly protect the user from a
runaway client burning through their provider quota. Rate-limit response headers on every
authenticated response: `x-ratelimit-limit-requests`, `x-ratelimit-remaining-requests`,
`x-ratelimit-reset-requests` (seconds), mirroring OpenAI's header names.

### 1.6 CLI

```
web2api-bridge keys create --name NAME [--scopes chat,tasks,admin | --admin] [--providers claude,chatgpt]
                           # --admin is shorthand for --scopes chat,admin; default scopes: chat
                           [--rpm N] [--concurrent N] [--expires 30d|2026-12-31]
        → prints the key ONCE, plus ready-to-paste env vars:
            export OPENAI_API_KEY=sk-w2a-…
            export OPENAI_BASE_URL=http://127.0.0.1:8787/v1
web2api-bridge keys list                 # id, name, scopes, providers, created, last used, status; never the key
web2api-bridge keys revoke ID|NAME       # immediate
web2api-bridge keys rotate ID|NAME       # creates a replacement with same settings, revokes the old after --grace (default 0)
web2api-bridge pairing show|rotate       # the extension pairing token (replaces `tokens ...`)
```
* First run (no `keys.json`): create a key named `default` with scopes `chat` and `admin`, and print
  it in the startup banner **once** (with a note: "create narrower keys with `keys create`").
  Subsequent runs never print keys. A lost key is replaced with `keys rotate default`.
* Optional env var `WEB2API_API_KEY` (for containers/CI): if set, that exact value is accepted as an
  additional in-memory key named `env` with all scopes; it must match the key format (≥ 32 chars after
  `sk-`) or the bridge refuses to start.
* The CLI edits `keys.json` directly (taking the lock) when the bridge isn't running; when it is
  running the file edit plus hot reload (§1.2) is sufficient — no IPC needed.

### 1.7 Admin API additions (`admin` scope)

| Method & path | Purpose |
|---|---|
| `GET /web2api/keys` | List key metadata (never hashes or keys). |
| `POST /web2api/keys` | Body `{name, scopes?, providers?, rateLimit?, expiresAt?}` → `{id, key}` (**key returned once**). |
| `DELETE /web2api/keys/{id}` | Revoke. A key cannot revoke itself if it is the last admin key (409). |

### 1.8 Security notes
* Keys never appear in logs, the support bundle (`12` §6.2), health reports, or error bodies
  (masked only).
* The popup does **not** store or need an API key (only the pairing token).
* Rotating the pairing token doesn't affect API keys and vice versa.
* Add `sk-w2a-` to the "secrets" grep test in `09` §5 (logs must not contain it).

---

## 2. OpenAI compatibility contract

Goal: the **official OpenAI SDKs and mainstream OpenAI-compatible tools work unchanged** by setting a
base URL and key.

### 2.1 Endpoints

| Endpoint | v1 | Notes |
|---|---|---|
| `POST /v1/chat/completions` | ✔ | `07` §6. Non-streaming and SSE streaming. |
| `GET /v1/models` | ✔ | `07` §6.5. |
| `GET /v1/models/{model}` | ✔ (**add to `07` §6.5**) | Returns the same object shape for a single model; unknown → 404 `model_not_found`. Model ids contain `/` (`claude/default`): the route must be a catch-all path param (`/v1/models/{model:.+}`) and clients may URL-encode it. |
| `POST /v1/completions` (legacy) | ✘ | 404 `unsupported_endpoint` with a message pointing to chat completions. |
| `POST /v1/responses` | ✘ in v1 | Newer OpenAI SDK default for some tools. Planned post-1.0 as a thin adapter over the same job pipeline (design in `10` Phase 9). Until then return 404 `unsupported_endpoint` with the message "Use /v1/chat/completions". |
| `/v1/embeddings`, `/v1/images/*`, `/v1/audio/*`, `/v1/files`, `/v1/assistants*`, `/v1/batches` | ✘ | Same 404 body. |
| `OPTIONS *` | ✘ | 405, no CORS headers (`08` §3.1). |

Unsupported-endpoint body (any `/v1/*` path not implemented):
```json
{ "error": { "message": "The endpoint /v1/embeddings is not supported by Web2API. Supported: /v1/chat/completions, /v1/models.", "type": "invalid_request_error", "code": "unsupported_endpoint", "param": null } }
```

### 2.2 Request/response conformance rules

1. `Content-Type: application/json` required for POST (else 415, OpenAI-shaped).
2. Response header `x-request-id` on every response; `openai-processing-ms` on completions.
3. `id` format `chatcmpl-<22+ chars>`; `object`, `created` (int seconds), `model`, `choices[0].index`,
   `message.role/content`, `finish_reason ∈ {stop, length, content_filter, tool_calls}`, `usage` all present
   in non-streaming responses (`usage.estimated` is an additive extra).
4. Streaming: first chunk has `delta.role`; chunks share the same `id` and `created`; final content
   chunk has `finish_reason` and an empty `delta`; `data: [DONE]` last (`07` §6.3).
5. `stream_options.include_usage` honoured (final chunk with `choices: []`).
6. Error bodies always `{"error": {message, type, code, param}}`; `type` ∈
   `invalid_request_error | authentication_error | permission_error | rate_limit_error | api_error`.
7. Unknown request fields are ignored; documented ignored params get `X-Web2API-Ignored-Params`.
8. `model` names: `provider`, `provider/variant`, `auto`, and `model_aliases` (`07` §4.3). Recommended
   alias defaults (shipped, overridable) so tools with hard-coded model names work:
   `gpt-4o`, `gpt-4`, `gpt-4o-mini`, `gpt-5` → `chatgpt/default`; `claude-3-5-sonnet-latest`,
   `claude-sonnet-4-5` → `claude/default`; `gemini-2.5-pro`, `gemini-1.5-pro` → `gemini/default`.
   The response `model` echoes what the client sent.
9. Streaming heartbeat comments (`: keepalive`) are valid SSE and ignored by compliant clients; verify
   against the SDKs (§3).
10. `Connection`/`Transfer-Encoding` correct for SSE (aiohttp handles chunked).

### 2.3 Honest limits (documented in `docs/api-reference.md`)
Sampling parameters have no effect; token counts are estimates; tool calling and images are not
supported in v1; context is limited by the provider's web UI limits; latency is that of the web UI.

---

## 3. Verifying compatibility (must exist before 1.0)

A **conformance suite** in `bridge/tests/conformance/` that starts the bridge with the fake extension on
a random port and drives it with the **official clients**, which are *dev-only* tools (run with
`uv run --with openai pytest tests/conformance` — never a project dependency, never imported by the
bridge):

| Test | Client |
|---|---|
| Non-streaming chat completion; fields parse into SDK types without validation errors | `openai` Python SDK (`base_url`, `api_key=sk-w2a-…`) |
| Streaming iteration to completion; `include_usage`; final `[DONE]` handled | `openai` Python SDK |
| `client.models.list()` and `client.models.retrieve("claude/default")` | `openai` Python SDK |
| Error mapping: bad key → `openai.AuthenticationError`; 429 → `RateLimitError` (SDK retries honour `Retry-After`); unknown model → `NotFoundError`; unsupported endpoint → `NotFoundError` | `openai` Python SDK |
| Same happy paths | `openai` JS SDK (`npx`, Node) |
| curl-based raw SSE byte format assertions (no SDK) | stdlib client |
| Optional manual compat matrix (smoke, `09` §4): Cursor, Continue, Open WebUI, LangChain (`ChatOpenAI`), LiteLLM, `llm` CLI, Aider | human |

Acceptance for the matrix: each tool can chat (and stream where it streams) after setting only base URL
+ key + a model name. Record results (tool, version, date, notes) in `docs/compatibility.md`.
