# Using Web2API with other tools

> Target-state guide (see README status note). The table at the bottom is filled in with real test
> results during the compatibility pass in `spec/13` §3; entries below are *expected* setups.

Any tool that lets you set an **OpenAI base URL** and **API key** works. Values to use everywhere:

* Base URL: `http://127.0.0.1:8787/v1`
* API key: your `sk-w2a-…` key ([API keys](api-keys.md))
* Model: `claude`, `chatgpt`, `gemini`, or any alias (`gpt-4o`, …) — see `GET /v1/models`

Tips for all tools:
* If a tool insists on a model name from its own dropdown, type a custom name or use an alias
  (aliases are configurable with `model_aliases` in `config.toml`).
* Turn **off** features that need unsupported APIs: tool/function calling, image input, embeddings,
  structured-output schemas (best-effort only).
* Tools that fire many parallel requests will queue; set their concurrency to 1–2.
* Some tools send a hidden "generate a title" request after the first message — this uses a second
  prompt on the provider. Disable auto-titles if you can.

## Recipes

### Environment-variable tools (`llm`, Aider, many scripts)
```bash
export OPENAI_API_KEY=sk-w2a-…
export OPENAI_BASE_URL=http://127.0.0.1:8787/v1      # some tools use OPENAI_API_BASE
aider --model openai/chatgpt
```

### Cursor / editors with an OpenAI override
Settings → Models → OpenAI API key = your key; override base URL = `http://127.0.0.1:8787/v1`;
add a custom model named `claude` (or `chatgpt`/`gemini`). Features that use tool calling (agents) will
not work yet; plain chat and edits will.

### Continue (VS Code / JetBrains)
```json
{ "models": [ { "title": "Web2API Claude", "provider": "openai", "model": "claude",
                "apiBase": "http://127.0.0.1:8787/v1", "apiKey": "sk-w2a-…" } ] }
```

### Open WebUI
Admin → Settings → Connections → OpenAI API: URL `http://127.0.0.1:8787/v1`, key = your key. (If Open
WebUI runs in Docker, use `http://host.docker.internal:8787/v1` and note the bridge listens on
`127.0.0.1` only — see below.)

### LangChain (Python)
```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="claude", base_url="http://127.0.0.1:8787/v1", api_key="sk-w2a-…")
```

### LiteLLM
```python
import litellm
litellm.completion(model="openai/claude", api_base="http://127.0.0.1:8787/v1",
                   api_key="sk-w2a-…", messages=[{"role": "user", "content": "hi"}])
```

### Tools running in Docker or on another machine
The bridge only accepts connections to `127.0.0.1` by design. Prefer running the tool on the same
machine. If you must reach it from a container, use host networking, or an SSH tunnel; exposing the
bridge on other interfaces (`allow_remote = true`) requires keys and is **not recommended** — see
`spec/08-security.md` §3.4.

## Tested matrix

| Tool | Version | Chat | Streaming | Notes | Date |
|---|---|---|---|---|---|
| openai Python SDK | | — | — | pending | |
| openai JS SDK | | — | — | pending | |
| Cursor | | — | — | pending | |
| Continue | | — | — | pending | |
| Open WebUI | | — | — | pending | |
| LangChain | | — | — | pending | |
| LiteLLM | | — | — | pending | |
| Aider | | — | — | pending | |
