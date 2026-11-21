/// Data Models for Web2API Flutter / Dart SDK

class ChatMessage {
  final String role;
  final String content;

  ChatMessage({required this.role, required this.content});

  factory ChatMessage.user(String content) => ChatMessage(role: 'user', content: content);
  factory ChatMessage.assistant(String content) => ChatMessage(role: 'assistant', content: content);
  factory ChatMessage.system(String content) => ChatMessage(role: 'system', content: content);

  Map<String, dynamic> toJson() => {'role': role, 'content': content};

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        role: json['role'] as String? ?? 'user',
        content: json['content'] as String? ?? '',
      );
}

class ChatCompletionRequest {
  final String model;
  final List<ChatMessage> messages;
  final double? temperature;
  final bool stream;
  final int? maxTokens;

  ChatCompletionRequest({
    this.model = 'gemini-pro',
    required this.messages,
    this.temperature = 0.7,
    this.stream = false,
    this.maxTokens,
  });

  Map<String, dynamic> toJson() => {
        'model': model,
        'messages': messages.map((m) => m.toJson()).toList(),
        if (temperature != null) 'temperature': temperature,
        'stream': stream,
        if (maxTokens != null) 'max_tokens': maxTokens,
      };
}

class ChatChoice {
  final int index;
  final ChatMessage? message;
  final String? finishReason;

  ChatChoice({required this.index, this.message, this.finishReason});

  factory ChatChoice.fromJson(Map<String, dynamic> json) => ChatChoice(
        index: json['index'] as int? ?? 0,
        message: json['message'] != null
            ? ChatMessage.fromJson(json['message'] as Map<String, dynamic>)
            : null,
        finishReason: json['finish_reason'] as String?,
      );
}

class ChatCompletionResponse {
  final String id;
  final String model;
  final List<ChatChoice> choices;
  final double? latencySeconds;

  ChatCompletionResponse({
    required this.id,
    required this.model,
    required this.choices,
    this.latencySeconds,
  });

  String get text => choices.isNotEmpty ? choices.first.message?.content ?? '' : '';

  factory ChatCompletionResponse.fromJson(Map<String, dynamic> json) => ChatCompletionResponse(
        id: json['id'] as String? ?? '',
        model: json['model'] as String? ?? '',
        choices: (json['choices'] as List<dynamic>? ?? [])
            .map((c) => ChatChoice.fromJson(c as Map<String, dynamic>))
            .toList(),
        latencySeconds: (json['latency_seconds'] as num?)?.toDouble(),
      );
}

class Web2ApiChatResponse {
  final String response;
  final double latencySeconds;
  final String status;
  final Map<String, dynamic> extracted;

  Web2ApiChatResponse({
    required this.response,
    required this.latencySeconds,
    required this.status,
    required this.extracted,
  });

  factory Web2ApiChatResponse.fromJson(Map<String, dynamic> json) => Web2ApiChatResponse(
        response: json['response'] as String? ?? '',
        latencySeconds: (json['latency_seconds'] as num?)?.toDouble() ?? 0.0,
        status: json['status'] as String? ?? 'success',
        extracted: json['extracted'] as Map<String, dynamic>? ?? {},
      );
}

class HealthStatus {
  final String status;
  final bool extensionConnected;
  final bool authRequired;
  final String? timestamp;

  HealthStatus({
    required this.status,
    required this.extensionConnected,
    required this.authRequired,
    this.timestamp,
  });

  factory HealthStatus.fromJson(Map<String, dynamic> json) => HealthStatus(
        status: json['status'] as String? ?? 'unknown',
        extensionConnected: json['extension_connected'] as bool? ?? false,
        authRequired: json['auth_required'] as bool? ?? false,
        timestamp: json['timestamp'] as String?,
      );
}
