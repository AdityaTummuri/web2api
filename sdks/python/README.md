# Web2API Python Client SDK

Fast, lightweight, zero-boilerplate Python library to connect to any standalone Web2API server.

---

## 1. Installation

```bash
# Direct install from local directory:
pip install -e sdks/python

# Or from git:
pip install git+https://github.com/seeramsujay/web2api.git#subdirectory=sdks/python
```

---

## 2. Usage Examples

### Synchronous Client
```python
from web2api import Web2ApiClient

client = Web2ApiClient(
    base_url="http://localhost:8000", # Or remote server URL
    api_key="sk-w2a-your-secret-key"  # Optional
)

# 1. Health check
status = client.check_health()
print(f"Extension connected: {status.extension_connected}")

# 2. Simple chat
answer = client.chat("Explain Python metaclasses in 2 sentences", model="gemini-pro")
print(answer)

# 3. Real-time streaming
for chunk in client.chat_stream("Count from 1 to 5", model="gemini-pro"):
    print(chunk, end="", flush=True)
print()
```

### Asynchronous Client
```python
import asyncio
from web2api import AsyncWeb2ApiClient

async def main():
    client = AsyncWeb2ApiClient(base_url="http://localhost:8000")

    # Async chat
    answer = await client.chat("Hello async world!")
    print(answer)

    # Async streaming
    async for chunk in client.chat_stream("List 3 design patterns"):
        print(chunk, end="", flush=True)

asyncio.run(main())
```

### Using with the Official OpenAI SDK
Because Web2API exposes standard OpenAI endpoints (`/v1/chat/completions`), you can also use `openai-python`:
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-w2a-your-secret-key"  # Any non-empty string if auth disabled
)

response = client.chat.completions.create(
    model="gemini-pro",
    messages=[{"role": "user", "content": "Hello via official OpenAI SDK!"}]
)
print(response.choices[0].message.content)
```
