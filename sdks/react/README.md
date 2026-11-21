# Web2API React, Next.js & TypeScript SDK

Production-ready TypeScript client and React Hooks for **Web2API**, enabling zero-cost AI chat queries (ChatGPT, Gemini, Claude) with live streaming in React, Next.js, React Native, and Node.js.

---

## 1. Installation

```bash
# In your React / Next.js app:
npm install @web2api/react
# Or install from local path in monorepo:
npm install ../web2api/sdks/react
```

---

## 2. React Hooks Quickstart

### Live Streaming Chat Hook
```tsx
import React, { useState } from 'react';
import { useWeb2ApiChat } from '@web2api/react';

export function ChatApp() {
  const [input, setInput] = useState('');
  const { messages, sendMessage, isStreaming, reset } = useWeb2ApiChat({
    baseUrl: 'http://localhost:8000', // Standalone Web2API server
    apiKey: 'sk-w2a-secret-key',     // Optional
    model: 'gemini-pro',
  });

  return (
    <div>
      <div>
        {messages.map((m, i) => (
          <p key={i}><strong>{m.role}:</strong> {m.content}</p>
        ))}
      </div>

      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Ask Gemini..."
      />
      <button onClick={() => { sendMessage(input); setInput(''); }}>
        {isStreaming ? 'Streaming...' : 'Send'}
      </button>
      <button onClick={reset}>Clear</button>
    </div>
  );
}
```

### Pre-Built UI Component
Drop the `<Web2ApiChatBox />` directly into any page:
```tsx
import { Web2ApiChatBox } from '@web2api/react';

export default function Page() {
  return (
    <main style={{ padding: '40px' }}>
      <Web2ApiChatBox
        baseUrl="http://localhost:8000"
        model="claude-3-5-sonnet"
        title="My Project Assistant"
      />
    </main>
  );
}
```

---

## 3. Pure TypeScript / Node.js Usage

You can also use `Web2ApiClient` without React in Node.js, CLI scripts, and backend services:

```typescript
import { Web2ApiClient } from '@web2api/react';

const client = new Web2ApiClient({
  baseUrl: 'http://127.0.0.1:8000',
  apiKey: 'sk-w2a-secret-key'
});

// 1. One-shot chat
const answer = await client.chat('Explain TypeScript Generics');
console.log(answer);

// 2. Real-time streaming
await client.chatStream('Write a haiku about code', 'gemini-pro', (token) => {
  process.stdout.write(token);
});
```
