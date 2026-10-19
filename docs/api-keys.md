# API keys

> Target-state guide (see README status note). Design: `spec/13-api-keys-and-openai-compat.md`.

Web2API issues real API keys that look like OpenAI keys — `sk-w2a-` followed by 48 letters/digits — so
OpenAI-compatible tools accept them. Every request needs one.

## Two different secrets — don't mix them up

| Secret | Looks like | Used by | Where it goes |
|---|---|---|---|
| **API key** | `sk-w2a-…` | Your tools/scripts calling the API | `Authorization: Bearer …` or `OPENAI_API_KEY` |
| **Pairing token** | `w2a_pair_…` | The browser extension connecting to the bridge | Extension popup only |

Leaking an API key lets someone use your AI accounts through your bridge (only from your computer, since
the bridge listens locally) — but it can never impersonate the extension.

## Create, list, revoke

```bash
# create a chat-only key for one tool (recommended)
web2api-bridge keys create --name cursor

# restrict a key to some providers, limit its speed, make it expire
web2api-bridge keys create --name ci-bot --providers claude,chatgpt --rpm 20 --concurrent 1 --expires 30d

# explicit scopes (e.g. for the MCP server: chat + tasks)
web2api-bridge keys create --name mcp --scopes chat,tasks

# a key that can also use the admin API (status, health, config, key management)
web2api-bridge keys create --name admin-tool --admin

web2api-bridge keys list              # shows id, name, scopes, last used, status — never the key itself
web2api-bridge keys revoke cursor     # takes effect on the next request
web2api-bridge keys rotate cursor     # new key, same settings; old one revoked (use --grace 10m to overlap)
```
* The full key is displayed **once**, at creation. Only a hash is stored. If you lose it, rotate it.
* On first start the bridge creates a key named `default` (chat + admin) and shows it once.
  Create narrower keys for your tools and rotate/revoke `default` if you don't need it.

## Scopes

| Scope | Allows |
|---|---|
| `chat` (default) | `/v1/chat/completions`, `/v1/models` |
| `tasks` *(v2.0.0)* | The tasks API and the MCP server (`web2api-bridge mcp install` creates a key with `chat,tasks`) |
| `admin` | `/web2api/*` — status, health, config overrides, jobs, key management |

## Limits per key

Default 60 requests/minute and 4 concurrent requests per key; change with `--rpm` / `--concurrent`.
Responses carry `x-ratelimit-*` headers; going over returns HTTP 429 with `Retry-After`, which the
official SDKs honour automatically. Because the web UI handles one prompt per tab at a time, the real
throughput is much lower than these limits — they exist to stop a runaway script from burning your
provider quota.

## Using a key

```bash
curl http://127.0.0.1:8787/v1/models -H "Authorization: Bearer sk-w2a-…"
```
`X-API-Key: sk-w2a-…` is accepted too. Keys in URLs/query strings are never accepted.

## Auth errors

| HTTP | `error.code` | Meaning / fix |
|---|---|---|
| 401 | `missing_api_key` | Send the `Authorization` header. |
| 401 | `invalid_api_key` | Wrong, revoked or expired key (the message says which; keys are shown masked). Create/rotate one. |
| 403 | `insufficient_scope` | Key lacks `admin`; create an admin key. |
| 403 | `provider_not_allowed` | Key is restricted to other providers. |
| 429 | `rate_limit_exceeded` / `concurrency_limit_exceeded` | Slow down or raise the key's limits. |
| 429 | (after many bad keys) | Too many failed attempts from your address; wait a minute. |

## Good practice
* One key per tool, so you can revoke one without breaking the rest.
* Keep keys out of git; `sk-w2a-` makes them easy for secret scanners to flag.
* Where a tool offers an "API key" box, paste the key; where it wants a "base URL", use
  `http://127.0.0.1:8787/v1`.
* Environment-variable option for containers/CI: set `WEB2API_API_KEY=sk-…` (must follow the key
  format) to add an extra in-memory key with all scopes.
