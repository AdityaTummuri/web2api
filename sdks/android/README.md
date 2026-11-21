# Web2API Android / Kotlin Client SDK

First-class Android & Kotlin client for **Web2API**, allowing any Android app to execute AI chat queries (ChatGPT, Gemini, Claude) through your standalone Web2API server with zero API subscription costs and real-time streaming.

---

## Features

- **Idiomatic Kotlin & Coroutines**: Built from the ground up for modern Android.
- **Real-Time Token Streaming**: High performance Server-Sent Events (SSE) streaming via `Kotlin Flow`.
- **OpenAI Compatible**: Direct support for standard OpenAI chat completions.
- **Server Agnostic**: Connects to localhost emulator (`10.0.2.2`), LAN IP (`192.168.x.x`), or remote cloud/VPS server over HTTPS.
- **Security Ready**: Built-in support for Bearer tokens (`WEB2API_API_KEY`).
- **Resilient**: Typed exceptions for disconnected extensions (HTTP 503), timeouts (504), and auth errors (401).

---

## 1. Installation

### Option A: Gradle Composite Build / Subproject (Recommended for Multi-Project Repos)
In your Android app's `settings.gradle.kts`:
```kotlin
includeBuild("../web2api/sdks/android")
```
And in your app's `build.gradle.kts`:
```kotlin
dependencies {
    implementation("com.web2api:web2api-android:2.0.0")
}
```

### Option B: Local Jar / Maven Publish
```bash
cd sdks/android
gradle publishToMavenLocal
```
Then add `mavenLocal()` to your root `build.gradle.kts` repositories.

### Option C: Direct Source Copy
Simply copy `com/web2api/client/` directly into your Android app's `src/main/kotlin/` directory!

---

## 2. Android Manifest Configuration

Ensure your app has internet access in `AndroidManifest.xml`:
```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
</manifest>
```

> **Note on Local Development (HTTP)**: If connecting to a local LAN server or emulator (`http://`), add `android:usesCleartextTraffic="true"` to your `<application>` tag or configure a Network Security Config for your local IP.

---

## 3. Quickstart Examples

### Initialize Client
```kotlin
import com.web2api.client.Web2ApiClient

val client = Web2ApiClient.Builder()
    // For Android Emulator -> PC host:
    .baseUrl("http://10.0.2.2:8000")
    // For Physical Device on Wi-Fi:
    // .baseUrl("http://192.168.1.100:8000")
    // For Remote Server:
    // .baseUrl("https://api.yourdomain.com")
    .apiKey("sk-w2a-your-secret-key") // Optional if server doesn't require key
    .build()
```

### Direct Chat (One-Shot)
```kotlin
lifecycleScope.launch {
    try {
        val answer = client.chat(
            prompt = "Explain Android WorkManager in simple words",
            model = "gemini-pro" // or "gpt-4o", "claude-3-5-sonnet"
        )
        println("AI Answer: $answer")
    } catch (e: Web2ApiExtensionUnavailableException) {
        println("Browser extension is not active on the server!")
    }
}
```

### Real-Time Streaming with Kotlin Flow
```kotlin
lifecycleScope.launch {
    val stringBuilder = StringBuilder()
    client.chatStream(
        prompt = "Write a quick Jetpack Compose button example",
        model = "gemini-pro"
    ).collect { token ->
        stringBuilder.append(token)
        // Update live TextView / Compose text state
        chatTextView.text = stringBuilder.toString()
    }
}
```

### OpenAI-Compatible Chat Completion
```kotlin
val request = ChatCompletionRequest(
    model = "claude-3-5-sonnet",
    messages = listOf(
        ChatMessage.system("You are an expert Kotlin engineer."),
        ChatMessage.user("How do I avoid memory leaks in Coroutines?")
    )
)

val response = client.createChatCompletion(request)
println(response.text)
```

---

## 4. Jetpack Compose Integration Example

See [`SampleComposeChat.kt`](src/main/kotlin/com/web2api/client/sample/SampleComposeChat.kt) for a full ViewModel and UI pattern that plugs directly into Jetpack Compose with streaming state management.
