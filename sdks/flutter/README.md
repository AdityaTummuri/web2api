# Web2API Flutter & Dart Package

Production-grade Flutter and Dart client for **Web2API**, enabling zero-cost AI chat (Gemini, ChatGPT, Claude) with real-time streaming directly in mobile, desktop, and web apps.

---

## 1. Installation

In your Flutter app's `pubspec.yaml`:

```yaml
dependencies:
  web2api:
    path: ../web2api/sdks/flutter  # Local monorepo path
    # Or via git:
    # git:
    #   url: https://github.com/seeramsujay/web2api.git
    #   path: sdks/flutter
```

Then run:
```bash
flutter pub get
```

---

## 2. Quickstart

### Connect to Server
```dart
import 'package:web2api/web2api.dart';

final client = Web2ApiClient(
  // For Android Emulator to host machine:
  baseUrl: 'http://10.0.2.2:8000',
  // For iOS Simulator / macOS / Linux / Windows:
  // baseUrl: 'http://127.0.0.1:8000',
  // For LAN / Wi-Fi Device:
  // baseUrl: 'http://192.168.1.100:8000',
  // For Remote Production Server:
  // baseUrl: 'https://api.yourdomain.com',
  apiKey: 'sk-w2a-your-secret-key', // Optional
);
```

### Direct Chat
```dart
try {
  final answer = await client.chat('Explain state management in Flutter', model: 'gemini-pro');
  print('AI: $answer');
} on Web2ApiExtensionUnavailableException {
  print('Please make sure your browser extension is active on the server!');
}
```

### Real-Time Streaming
```dart
client.chatStream('Write a haiku about Dart', model: 'gemini-pro').listen(
  (token) {
    stdout.write(token); // Or append to your stateful widget text
  },
  onDone: () => print('\nStream finished!'),
  onError: (e) => print('Stream error: $e'),
);
```

### Full Example App
Check [`example/lib/main.dart`](example/lib/main.dart) for a complete Material 3 chat screen with real-time streaming and reset thread actions.
