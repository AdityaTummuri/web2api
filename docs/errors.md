# Error codes

> Target-state guide (see README status note). Source of truth: `spec/06-bridge-protocol.md` §7 and
> `spec/13-api-keys-and-openai-compat.md` §1.4.

Every error body is `{"error": {"message", "type", "code", "param"}}` with the codes below in `code`.
Rule of thumb: **4xx = fix your request or key; 429 = slow down; 5xx = something in the browser or
provider needs attention.**

## Authentication and limits

| HTTP | Code | Fix |
|---|---|---|
| 401 | `missing_api_key` | Add `Authorization: Bearer sk-w2a-…`. |
| 401 | `invalid_api_key` | Key is wrong, revoked or expired. `web2api-bridge keys list`, then create/rotate. |
| 403 | `insufficient_scope` | Use a key with the `admin` scope for `/web2api/*`. |
| 403 | `provider_not_allowed` | The key is restricted to other providers. |
| 429 | `rate_limit_exceeded`, `concurrency_limit_exceeded` | Per-key limits; wait `Retry-After` seconds or raise the limits. |

## Request problems

| HTTP | Code | Meaning / fix |
|---|---|---|
| 400 | `invalid_request_error` | Malformed JSON or field; `param` names it. |
| 400 | `PROMPT_TOO_LONG` | Shorten the prompt (limit is shown in the message). |
| 400 | `UNSUPPORTED_CONTENT` | Images/files/tools/assistant-prefill aren't supported in 1.0. |
| 404 | `model_not_found` | Unknown or currently unavailable model (internally `MODEL_NOT_AVAILABLE`). `GET /v1/models` lists valid ones. |
| 404 | `unsupported_endpoint` | Only `/v1/chat/completions` and `/v1/models` exist. |

## Browser / provider problems

| HTTP | Code | What happened | What to do |
|---|---|---|---|
| 503 | `NO_EXTENSION` | No browser extension connected. | Open the browser (Chrome/Firefox) with the extension installed; popup should say *Connected*. |
| 503 | `PROVIDER_UNAVAILABLE` | That provider is disabled or not ready. | Enable it in the popup; check its status. |
| 503 | `NO_CAPACITY` | All worker tabs busy for 60 s. | Retry later; allow more tabs in the popup (pool size) for that provider. |
| 503 | `LOGIN_REQUIRED` | The site shows a login page. | Log in to the site in the browser profile with the extension. |
| 503 | `CAPTCHA_REQUIRED` | The site wants a human check. | Click *Show worker window* in the popup and solve it once. |
| 429 | `RATE_LIMITED` | The **provider** says you reached its usage limit (message includes reset time if shown). | Wait, or use another provider. Web2API pauses that provider until it clears. |
| 502 | `SELECTOR_NOT_FOUND`, `SELECTOR_AMBIGUOUS`, `INPUT_REJECTED`, `SUBMIT_FAILED`, `MODEL_SELECT_FAILED` | Web2API couldn't operate the page — usually the site changed. Safe to retry once (the prompt wasn't sent). | Check popup → *Health*; run `web2api-bridge doctor --probe`; report with a support bundle. A config update may already exist. |
| 502 | `SELECTOR_SUSPICIOUS` | A safety check refused to click a button that looked destructive (delete/log out/…). | Report it — a site change or bad config override moved something. |
| 502 | `PROVIDER_ERROR` | The site displayed or streamed an error (overloaded, "something went wrong"). | Retry later. |
| 502 | `PROVIDER_INTERRUPT` | The site asked for a decision (e.g. "which response do you prefer?"). | Retry; if frequent, choose the provider's default behaviour in its settings. |
| 502 | `TAB_LOST`, `PAGE_NAVIGATED` | The worker tab was closed or navigated away mid-request. | Don't close the worker window during requests. Retry. |
| 502 | `EXTENSION_RESTARTED`, `EXTENSION_DISCONNECTED` | Browser/extension restarted or connection dropped mid-request. | Retry. |
| 504 | `NO_RESPONSE` | The prompt was sent but no answer started within 60 s. | Check the tab manually; the site may be slow or down. |
| 504 | `GENERATION_STALLED`, `GENERATION_TIMEOUT` | Answer stopped progressing / exceeded the time limit. Partial text (if any) is in `error.web2api.partial_text`. | Retry with a shorter task or raise `timeouts.total_ms`. |
| 500 | `INTERNAL_ERROR` | A bug. | Run `web2api-bridge support-bundle` and report it. |

Whether a request that failed with a 502 had already been **sent to the provider** is tracked internally;
Web2API only retries automatically when the prompt definitely was not sent.

## Admin API only

| HTTP | Code | Meaning |
|---|---|---|
| 400 | `CONFIG_REJECTED` | A provider configuration override failed validation; the response lists the reasons. Nothing was applied. |

`CANCEL_FAILED` and `UNKNOWN_TYPE` are internal conditions between the bridge and extension; they are
logged and reflected in provider health but never returned to API clients directly.
