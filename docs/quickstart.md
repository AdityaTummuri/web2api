# Quick start

> Target-state guide (see README status note).

You need: the bridge running, the extension installed and paired, and at least one provider logged in
and enabled. If not, do these first:
[bridge](install-bridge.md) → [Chrome](install-chrome.md) or [Firefox](install-firefox.md).

## 1. Get your API key and base URL

```bash
web2api-bridge keys create --name my-tool
```
prints a key like `sk-w2a-9fKq…` (shown once) and:
```bash
export OPENAI_API_KEY=sk-w2a-9fKq…
export OPENAI_BASE_URL=http://127.0.0.1:8787/v1
```
Most OpenAI-compatible tools read exactly those two variables. (First run also created a `default` key.)
More about keys: [API keys](api-keys.md).

## 2. Check that everything is connected

```bash
web2api-bridge doctor
```
Every line should be ✔ (bridge running, extension connected, at least one provider *ready*). Or:
```bash
curl -s http://127.0.0.1:8787/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"
```
lists the models currently available, e.g. `claude/default`, `chatgpt/default`, `gemini/default`, `auto`.
An empty list means no extension is connected or no provider is ready.

## 3. First call

### curl
```bash
curl http://127.0.0.1:8787/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"claude","messages":[{"role":"user","content":"Reply with exactly: PONG"}]}'
```
The first request to a provider may take a few seconds longer because Web2API opens a worker tab.

### Python (official `openai` package)
```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8787/v1", api_key="sk-w2a-…")

r = client.chat.completions.create(
    model="chatgpt",
    messages=[{"role": "user", "content": "Write a haiku about rivers."}],
)
print(r.choices[0].message.content)

# streaming
for chunk in client.chat.completions.create(
        model="claude", stream=True,
        messages=[{"role": "user", "content": "Count from 1 to 10."}]):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

### JavaScript / TypeScript (official `openai` package)
```js
import OpenAI from "openai";
const client = new OpenAI({ baseURL: "http://127.0.0.1:8787/v1", apiKey: process.env.OPENAI_API_KEY });

const stream = await client.chat.completions.create({
  model: "gemini", stream: true,
  messages: [{ role: "user", content: "Explain closures in two sentences." }],
});
for await (const part of stream) process.stdout.write(part.choices[0]?.delta?.content ?? "");
```

## 4. Choosing a model

| `model` | Meaning |
|---|---|
| `claude`, `chatgpt`, `gemini` | That site, with whatever model the site is currently set to |
| `claude/default` | Same thing, explicit |
| `auto` | The first available provider (order configurable) |
| `gpt-4o`, `claude-sonnet-4-5`, … | Aliases mapped to a provider so tools with fixed model names work |

The web UI decides which underlying model answers; Web2API reports it in `web2api.model_label` when
the page shows it. Choosing a specific model variant is a later feature.

## 5. Conversations

OpenAI clients resend the whole history every call. Web2API recognises when a request simply continues a
conversation it already ran and sends **only the new message** into the same web chat. If you edit or
trim history, it starts a fresh web chat with a transcript instead. Everything you send shows up in
that provider's chat history (use `history_mode = "temporary"` to avoid that where supported).
Control it per request: `"extra_body": {"web2api": {"thread": "new"}}`.
Details: [API reference](api-reference.md#conversation-handling).

## Next
[API keys](api-keys.md) · [API reference](api-reference.md) · [Other tools](compatibility.md) ·
[Troubleshooting](troubleshooting.md)
