import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import 'exceptions.dart';
import 'models.dart';

/// Production-ready Web2API Client for Flutter and Dart.
///
/// Connects to a standalone Web2API server to query ChatGPT, Gemini, or Claude
/// with zero token costs and real-time streaming.
///
/// ```dart
/// final client = Web2ApiClient(
///   baseUrl: 'http://10.0.2.2:8000', // For Android Emulator
///   apiKey: 'sk-w2a-your-secret-key', // Optional
/// );
///
/// // One-shot prompt:
/// final answer = await client.chat('Explain Flutter widgets in 2 sentences');
///
/// // Real-time token streaming:
/// client.chatStream('Count to 10').listen((token) {
///   stdout.write(token);
/// });
/// ```
class Web2ApiClient {
  final String baseUrl;
  final String? apiKey;
  final Duration timeout;
  final http.Client _httpClient;

  Web2ApiClient({
    String baseUrl = 'http://127.0.0.1:8000',
    this.apiKey,
    this.timeout = const Duration(seconds: 120),
    http.Client? httpClient,
  })  : baseUrl = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl,
        _httpClient = httpClient ?? http.Client();

  Map<String, String> _headers([String contentType = 'application/json']) {
    final headers = {
      'Content-Type': contentType,
      'Accept': 'application/json',
    };
    if (apiKey != null && apiKey!.isNotEmpty) {
      headers['Authorization'] = 'Bearer $apiKey';
      headers['X-API-Key'] = apiKey!;
    }
    return headers;
  }

  void _handleHttpError(int statusCode, String body) {
    switch (statusCode) {
      case 401:
        throw Web2ApiAuthException();
      case 503:
        throw Web2ApiExtensionUnavailableException();
      case 504:
        throw Web2ApiTimeoutException();
      default:
        throw Web2ApiException('Server returned HTTP $statusCode: $body', statusCode: statusCode);
    }
  }

  /// Checks server health and browser extension connection.
  Future<HealthStatus> checkHealth() async {
    try {
      final res = await _httpClient.get(
        Uri.parse('$baseUrl/health'),
        headers: _headers(),
      ).timeout(const Duration(seconds: 10));

      if (res.statusCode != 200) {
        _handleHttpError(res.statusCode, res.body);
      }

      final json = jsonDecode(res.body) as Map<String, dynamic>;
      return HealthStatus.fromJson(json);
    } on Web2ApiException {
      rethrow;
    } catch (e) {
      throw Web2ApiConnectionException(e.toString());
    }
  }

  /// Sends a prompt and returns the AI string response directly.
  Future<String> chat(String prompt, {String model = 'gemini-pro'}) async {
    final full = await chatFull(prompt, model: model);
    return full.response;
  }

  /// Sends a prompt and returns the full response object with latency metrics.
  Future<Web2ApiChatResponse> chatFull(String prompt, {String model = 'gemini-pro'}) async {
    final payload = jsonEncode({
      'prompt': prompt,
      'model': model,
      'timeout': timeout.inSeconds.toDouble(),
    });

    try {
      final res = await _httpClient.post(
        Uri.parse('$baseUrl/api/chat'),
        headers: _headers(),
        body: payload,
      ).timeout(timeout);

      if (res.statusCode != 200) {
        _handleHttpError(res.statusCode, res.body);
      }

      final json = jsonDecode(res.body) as Map<String, dynamic>;
      return Web2ApiChatResponse.fromJson(json);
    } on Web2ApiException {
      rethrow;
    } catch (e) {
      throw Web2ApiConnectionException(e.toString());
    }
  }

  /// Streams tokens in real-time using Server-Sent Events (SSE).
  Stream<String> chatStream(String prompt, {String model = 'gemini-pro'}) async* {
    final payload = jsonEncode({
      'model': model,
      'messages': [
        {'role': 'user', 'content': prompt}
      ],
      'stream': true,
    });

    final request = http.Request('POST', Uri.parse('$baseUrl/v1/chat/completions'));
    request.headers.addAll(_headers());
    request.headers['Accept'] = 'text/event-stream';
    request.body = payload;

    try {
      final streamedResponse = await _httpClient.send(request).timeout(timeout);

      if (streamedResponse.statusCode != 200) {
        final body = await streamedResponse.stream.bytesToString();
        _handleHttpError(streamedResponse.statusCode, body);
      }

      final lineStream = streamedResponse.stream
          .transform(utf8.decoder)
          .transform(const LineSplitter());

      await for (final line in lineStream) {
        final trimmed = line.trim();
        if (trimmed.startsWith('data: ')) {
          final data = trimmed.substring(6).trim();
          if (data == '[DONE]') {
            break;
          }
          try {
            final json = jsonDecode(data) as Map<String, dynamic>;
            final choices = json['choices'] as List<dynamic>?;
            if (choices != null && choices.isNotEmpty) {
              final delta = choices[0]['delta'] as Map<String, dynamic>?;
              final content = delta?['content'] as String?;
              if (content != null && content.isNotEmpty) {
                yield content;
              }
            }
          } catch (_) {
            // Ignore incomplete chunks
          }
        }
      }
    } on Web2ApiException {
      rethrow;
    } catch (e) {
      throw Web2ApiConnectionException(e.toString());
    }
  }

  /// Executes OpenAI-compatible chat completion.
  Future<ChatCompletionResponse> createChatCompletion(ChatCompletionRequest request) async {
    try {
      final res = await _httpClient.post(
        Uri.parse('$baseUrl/v1/chat/completions'),
        headers: _headers(),
        body: jsonEncode(request.toJson()),
      ).timeout(timeout);

      if (res.statusCode != 200) {
        _handleHttpError(res.statusCode, res.body);
      }

      final json = jsonDecode(res.body) as Map<String, dynamic>;
      return ChatCompletionResponse.fromJson(json);
    } on Web2ApiException {
      rethrow;
    } catch (e) {
      throw Web2ApiConnectionException(e.toString());
    }
  }

  /// Resets the conversation tab in the active browser.
  Future<bool> resetConversation() async {
    try {
      final res = await _httpClient.post(
        Uri.parse('$baseUrl/api/reset'),
        headers: _headers(),
        body: '{}',
      ).timeout(const Duration(seconds: 10));

      if (res.statusCode != 200) {
        _handleHttpError(res.statusCode, res.body);
      }

      final json = jsonDecode(res.body) as Map<String, dynamic>;
      return json['status'] == 'success';
    } on Web2ApiException {
      rethrow;
    } catch (e) {
      throw Web2ApiConnectionException(e.toString());
    }
  }

  void close() {
    _httpClient.close();
  }
}
