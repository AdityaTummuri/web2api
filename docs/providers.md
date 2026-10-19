# Providers

> Target-state guide (see README status note). Statuses below are the **plan**; each provider is
> marked *verified* only after it passes the live smoke test (`spec/09-testing-strategy.md` §4) on the
> date shown. Until then every entry is *not yet verified*.

| Provider | `model` | Tier | Exact streaming | Status | Last verified |
|---|---|---|---|---|---|
| ChatGPT (chatgpt.com) | `chatgpt` | 1 | yes (planned) | not yet verified | — |
| Claude (claude.ai) | `claude` | 1 | yes (planned) | not yet verified | — |
| Gemini (gemini.google.com) | `gemini` | 1 | no — reads the page | not yet verified | — |
| DeepSeek | `deepseek` | 2 | planned | planned (v1.1) | — |
| Grok | `grok` | 2 | planned | planned (v1.1) | — |
| Perplexity | `perplexity` | 2 | planned | planned (v1.1) | — |
| Mistral Le Chat | `mistral` | 2 | planned | planned (v1.1) | — |
| Qwen | `qwen` | 2 | planned | planned (v1.1) | — |
| Kimi | `kimi` | 2 | planned | planned (v1.1) | — |
| Copilot, Meta AI, HuggingChat, AI Studio, Z.ai | — | 3 | — | later | — |

"Exact streaming" means Web2API reads the site's own data stream (precise Markdown, true token
streaming). Otherwise it reads the rendered page, which is slightly less precise but works everywhere.

## What Web2API needs from you
* A normal, **logged-in** account in the browser profile that has the extension.
* English or other UI language is fine, but if a site's interface is in an unusual language, report
  problems — some detection uses on-screen text.
* The provider's own **limits still apply** (free-tier message caps, "usage limit" windows). Web2API
  reports them as `RATE_LIMITED`.

## Per-provider notes
* **ChatGPT:** reasoning models show a "Thought for…" section — excluded from the answer by default.
  Occasionally the site shows two answers to compare; Web2API takes the first or returns
  `PROVIDER_INTERRUPT`. Temporary chats are used when `history_mode = "temporary"`.
* **Claude:** artifacts (side-panel documents) may not be extracted in 1.0; you'll see the warning
  `artifact_not_extracted`. Extended thinking is excluded unless `include_reasoning` is set.
* **Gemini:** page-reading only; multi-account users keep their `/u/N/` account. "Show drafts",
  Canvas and Deep Research content outside the normal reply aren't captured.
* **Search-style providers (Perplexity):** answers include citation markers like `[1]`; first token can
  take a while because the site searches first.

## When a site changes
Sites change their pages often. When that breaks a provider you'll see `SELECTOR_NOT_FOUND`, the provider
turns *Unhealthy* in the popup, and a health report with a content-free page snapshot is saved. Fixes
ship as small configuration updates (new extension release, or a hot configuration override) — other
providers keep working meanwhile. See [Troubleshooting](troubleshooting.md).
