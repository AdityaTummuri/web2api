# Web2API Tool Calling & Function Emulation Guide

Web2API provides a **lightweight, resilient Tool Calling & Function Emulation Engine** ([`tool_parser.py`](file:///home/suzaykid/Projects/web2api/tool_parser.py)) that translates consumer browser AI sessions (Gemini, ChatGPT, Claude) into standard OpenAI-compatible `tool_calls`.

---

## 1. How It Works

Consumer web interfaces (like Gemini web, Claude web, or ChatGPT web) do not natively support API function calling schemas. Web2API bridges this gap automatically:

```
┌─────────────────────────────────┐
│ Your Agent / App / LangChain    │
│ Sends `tools` + messages       │
└────────────────┬────────────────┘
                 │ HTTP POST /v1/chat/completions
                 ▼
┌────────────────────────────────────────────────────────┐
│ Web2API Bridge Server                                  │
│ 1. `tool_parser.format_conversation_with_tools()`      │
│    Injects coherent tool schema & contract into prompt │
│ 2. Dispatches prompt to browser extension via WS       │
└────────────────┬───────────────────────────────────────┘
                 │ WebSocket
                 ▼
┌─────────────────────────────────┐
│ Browser Extension               │
│ Types prompt in Gemini/Claude   │
│ Model outputs ```tool_call ...  │
└────────────────┬────────────────┘
                 │ WebSocket (raw text)
                 ▼
┌────────────────────────────────────────────────────────┐
│ Web2API Bridge Server                                  │
│ 3. `tool_parser.parse_tool_calls()`                    │
│    - Extracts tool calls from markdown / XML / JSON    │
│    - Repairs trailing commas, single quotes, etc.      │
│    - Validates against declared tool parameter schema  │
│ 4. Formats into standard OpenAI `tool_calls` payload   │
└────────────────┬───────────────────────────────────────┘
                 │ HTTP Response
                 ▼
┌─────────────────────────────────┐
│ Your Application receives:      │
│ - `finish_reason: "tool_calls"` │
│ - `tool_calls[0].function`      │
└─────────────────────────────────┘
```

---

## 2. Tool Definition & Contract

When `tools` are supplied in `/v1/chat/completions`, Web2API instructs the model with a strict output contract:

```markdown
If you decide to invoke a tool, reply ONLY with one or more fenced `tool_call` blocks:
```tool_call
{"name": "<function_name>", "arguments": {"<param_key>": "<param_value>"}}
```
If NO tool is needed, respond with standard conversational text and DO NOT output any ```tool_call``` block.
```

### Parser Resilience
The lightweight parser handles various model output styles:
1. **Fenced Blocks**: ```` ```tool_call {"name": "...", "arguments": {...}} ``` ```` or ```` ```json ````
2. **Tag Style**: `<tool_call>{"name": "...", "arguments": {...}}</tool_call>`
3. **Fuzzy JSON**: Automatically repairs trailing commas, single quotes, or escaped braces.
4. **Coherence & Security**: Rejects any tool call whose name was not declared in `tools`, preventing hallucinated function invocations.

---

## 3. Multi-Turn Tool Continuation

When the model calls a tool, execute the function locally in your application, then return the result as a `tool` role message:

```
Turn 1: User asks "What is the weather in Tokyo?"
Turn 2: Model returns finish_reason="tool_calls", name="get_weather", args={"location": "Tokyo"}
Turn 3: You run your local weather API -> {"temp": 18, "condition": "sunny"}
Turn 4: You send message: {"role": "tool", "name": "get_weather", "tool_call_id": "call_123", "content": '{"temp": 18, "condition": "sunny"}'}
Turn 5: Model reads the tool result and responds: "The weather in Tokyo is currently 18°C and sunny!"
```

---

## 4. Code Examples

### 🤖 Android (Kotlin)
```kotlin
val request = ChatCompletionRequest(
    messages = listOf(ChatMessage.user("What is the weather in Paris?")),
    tools = listOf(
        Tool(
            function = FunctionDefinition(
                name = "get_weather",
                description = "Get current weather",
                parameters = mapOf(
                    "type" to "object",
                    "properties" to mapOf("city" to mapOf("type" to "string")),
                    "required" to listOf("city")
                )
            )
        )
    )
)

val response = client.createChatCompletion(request)

if (response.isToolCall) {
    val call = response.toolCalls.first()
    println("Call tool: ${call.function.name} with args ${call.function.arguments}")
} else {
    println("Normal answer: ${response.text}")
}
```

### 🐍 Python
```python
from web2api import Web2ApiClient, ChatMessage

client = Web2ApiClient(base_url="http://localhost:8000")

tools = [
    {
        "type": "function",
        "function": {
            "name": "lookup_customer",
            "description": "Find customer record by ID",
            "parameters": {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"]
            }
        }
    }
]

res = client.create_chat_completion(
    messages=[{"role": "user", "content": "Find details for customer C-9821"}],
    tools=tools,
    tool_choice="auto"
)

choice = res["choices"][0]
if choice["finish_reason"] == "tool_calls":
    for tool_call in choice["message"]["tool_calls"]:
        print("Invoking:", tool_call["function"]["name"], tool_call["function"]["arguments"])
```

### 💙 Flutter / Dart
```dart
final request = ChatCompletionRequest(
  messages: [ChatMessage.user('Search for order 1045')],
  tools: [
    Tool(
      function: FunctionDefinition(
        name: 'search_order',
        description: 'Lookup order by orderId',
        parameters: {
          'type': 'object',
          'properties': {'orderId': {'type': 'int'}},
          'required': ['orderId']
        },
      ),
    ),
  ],
);

final res = await client.createChatCompletion(request);
if (res.isToolCall) {
  print('Tool requested: ${res.toolCalls.first.function.name}');
}
```

### ⚛️ React / TypeScript
```typescript
import { Web2ApiClient } from '@web2api/react';

const client = new Web2ApiClient({ baseUrl: 'http://localhost:8000' });

const response = await client.createChatCompletion({
  messages: [{ role: 'user', content: 'Calculate 15 * 94' }],
  tools: [{
    type: 'function',
    function: {
      name: 'calc',
      description: 'Calculator',
      parameters: { type: 'object', properties: { expr: { type: 'string' } } }
    }
  }]
});

if (response.choices[0].finish_reason === 'tool_calls') {
  console.log(response.choices[0].message?.tool_calls);
}
```

### cURL
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-pro",
    "messages": [{"role": "user", "content": "Check stock for TSLA"}],
    "tools": [{
      "type": "function",
      "function": {
        "name": "get_stock_price",
        "description": "Stock price lookup",
        "parameters": {
          "type": "object",
          "properties": {"symbol": {"type": "string"}},
          "required": ["symbol"]
        }
      }
    }]
  }'
```
