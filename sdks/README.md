# Web2API Universal Client SDKs

Welcome to the **Web2API SDK Ecosystem**. Web2API enables you to use your logged-in browser AI sessions (Gemini, ChatGPT, Claude) as a high-speed, local or remote OpenAI-compatible REST & WebSocket API without paid API tokens.

These SDKs allow you to connect any application or service to your independent Web2API server across **Android**, **Python**, **Flutter**, and **React / TypeScript**.

---

## SDK Feature Matrix

| Feature | 🤖 Android (Kotlin) | 🐍 Python | 💙 Flutter (Dart) | ⚛️ React & TypeScript |
|---|---|---|---|---|
| **Directory** | [`sdks/android`](android/) | [`sdks/python`](python/) | [`sdks/flutter`](flutter/) | [`sdks/react`](react/) |
| **Priority** | ⭐ **Top Priority** | Standard | Standard | Standard |
| **Language Target** | Kotlin (Coroutines/Flow) | Python 3.8+ (Sync/Async) | Dart 3 / Flutter 3 | TypeScript / React / Node |
| **Real-time SSE Streaming** | ✅ `Flow<String>` | ✅ `Generator` & `AsyncGen` | ✅ `Stream<String>` | ✅ `chatStream` / Hook |
| **OpenAI Compatibility** | ✅ Full Schema | ✅ Native + OpenAI wrapper | ✅ Full Schema | ✅ Full Schema |
| **Auth Support** | ✅ Bearer / X-API-Key | ✅ Bearer / X-API-Key | ✅ Bearer / X-API-Key | ✅ Bearer / X-API-Key |
| **Pre-built UI Components** | ✅ Jetpack Compose Sample | N/A (CLI / REPL) | ✅ Chat Widget Screen | ✅ `<Web2ApiChatBox />` |
| **Error Handling** | Typed Exceptions | Typed Exceptions | Typed Exceptions | Error callbacks |

---

## 1. 🤖 Android SDK (`sdks/android`) - Most Important

Designed specifically for modern Android architectures (MVVM, Kotlin Coroutines, Jetpack Compose, OkHttp, Flow).

### Adding to your Android App:
```kotlin
// In settings.gradle.kts:
includeBuild("../web2api/sdks/android")

// In app/build.gradle.kts:
dependencies {
    implementation("com.web2api:web2api-android:2.0.0")
}
```

### Kotlin Quickstart:
```kotlin
val client = Web2ApiClient.Builder()
    .baseUrl("http://10.0.2.2:8000") // Emulator loopback or https://api.yourdomain.com
    .apiKey("sk-w2a-your-secret-key")
    .build()

// Real-time token streaming with Kotlin Flow
lifecycleScope.launch {
    client.chatStream("Write an Android coroutine worker", model = "gemini-pro")
        .collect { token ->
            messageTextView.append(token)
        }
}
```
👉 [Full Android SDK Documentation & Jetpack Compose Sample](android/README.md)

---

## 2. 🐍 Python SDK (`sdks/python`)

Lightweight, modern client featuring both synchronous (`Web2ApiClient`) and asynchronous (`AsyncWeb2ApiClient`) interfaces powered by `httpx` and `urllib`.

### Installation:
```bash
pip install -e sdks/python
```

### Python Quickstart:
```python
from web2api import Web2ApiClient

client = Web2ApiClient(base_url="http://localhost:8000")

# Synchronous streaming
for chunk in client.chat_stream("Explain Python GIL in 2 bullet points"):
    print(chunk, end="", flush=True)
print()
```
👉 [Full Python SDK Documentation](python/README.md)

---

## 3. 💙 Flutter / Dart Package (`sdks/flutter`)

Standard Flutter & Dart package with sound null-safety, `Stream<String>` support, and full Material 3 sample chat screen.

### Installation:
```yaml
dependencies:
  web2api:
    path: ../web2api/sdks/flutter
```

### Flutter Quickstart:
```dart
import 'package:web2api/web2api.dart';

final client = Web2ApiClient(baseUrl: 'http://10.0.2.2:8000');

// Stream chunks into your widget state
client.chatStream('Explain Flutter InheritedWidget').listen((token) {
  setState(() => responseText += token);
});
```
👉 [Full Flutter SDK Documentation & Example Widget](flutter/README.md)

---

## 4. ⚛️ React & TypeScript SDK (`sdks/react`)

Versatile library for React, Next.js, React Native, and Node.js. Includes the `useWeb2ApiChat` streaming hook and drop-in `<Web2ApiChatBox />` component.

### Installation:
```bash
npm install ../web2api/sdks/react
```

### React Quickstart:
```tsx
import { useWeb2ApiChat } from '@web2api/react';

export function Chat() {
  const { messages, sendMessage, isStreaming } = useWeb2ApiChat({
    baseUrl: 'http://localhost:8000',
    model: 'gemini-pro'
  });

  return (
    <div>
      {messages.map((m, i) => <p key={i}><b>{m.role}:</b> {m.content}</p>)}
      <button onClick={() => sendMessage('Hello AI!')}>
        {isStreaming ? 'Thinking...' : 'Send'}
      </button>
    </div>
  );
}
```
👉 [Full React SDK Documentation](react/README.md)

---

## Cross-Project Integration Strategies

To make Web2API accessible across all your personal and team projects without code duplication:

1. **Monorepo / Local Path Reference**:
   Reference the SDKs directly via local path in `package.json`, `pubspec.yaml`, `build.gradle.kts`, or `pyproject.toml`.
2. **Git Submodule**:
   Add this repository as a submodule to your other projects:
   ```bash
   git submodule add https://github.com/seeramsujay/web2api.git external/web2api
   ```
3. **Internal Server Access**:
   Deploy the server once on your local network (e.g. `http://192.168.1.50:8000`) or cloud VPS (`https://api.yourdomain.com`), and all your apps (Android phone, Flutter app, web dashboard, Python scripts) can query it simultaneously!
