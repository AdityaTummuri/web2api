/// Data Models for Web2API Flutter / Dart SDK with Tool Calling Support

class FunctionCall {
  final String name;
  final String arguments;

  FunctionCall({required this.name, required this.arguments});

  factory FunctionCall.fromJson(Map<String, dynamic> json) => FunctionCall(
        name: json['name'] as String? ?? '',
        arguments: json['arguments'] as String? ?? '{}',
      );

  Map<String, dynamic> toJson() => {'name': name, 'arguments': arguments};
}

class ToolCall {
  final String id;
  final String type;
  final FunctionCall function;

  ToolCall({required this.id, this.type = 'function', required this.function});

  factory ToolCall.fromJson(Map<String, dynamic> json) => ToolCall(
        id: json['id'] as String? ?? '',
        type: json['type'] as String? ?? 'function',
        function: FunctionCall.fromJson(json['function'] as Map<String, dynamic>? ?? {}),
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'function': function.toJson(),
      };
}

class FunctionDefinition {
  final String name;
  final String? description;
  final Map<String, dynamic>? parameters;

  FunctionDefinition({required this.name, this.description, this.parameters});

  Map<String, dynamic> toJson() => {
        'name': name,
        if (description != null) 'description': description,
        if (parameters != null) 'parameters': parameters,
      };
}

class Tool {
  final String type;
  final FunctionDefinition function;

  Tool({this.type = 'function', required this.function});

  Map<String, dynamic> toJson() => {
        'type': type,
        'function': function.toJson(),
      };
}

class ChatMessage {
  final String role;
  final String? content;
  final String? name;
  final String? toolCallId;
  final List<ToolCall>? toolCalls;

  ChatMessage({
    required this.role,
    this.content,
    this.name,
    this.toolCallId,
    this.toolCalls,
  });

  factory ChatMessage.user(String content) => ChatMessage(role: 'user', content: content);
  factory ChatMessage.assistant(String content) => ChatMessage(role: 'assistant', content: content);
  factory ChatMessage.system(String content) => ChatMessage(role: 'system', content: content);
  factory ChatMessage.tool({required String toolCallId, required String name, required String content}) =>
      ChatMessage(role: 'tool', content: content, name: name, toolCallId: toolCallId);

  Map<String, dynamic> toJson() => {
        'role': role,
        if (content != null) 'content': content,
        if (name != null) 'name': name,
        if (toolCallId != null) 'tool_call_id': toolCallId,
        if (toolCalls != null) 'tool_calls': toolCalls!.map((t) => t.toJson()).toList(),
      };

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        role: json['role'] as String? ?? 'user',
        content: json['content'] as String?,
        name: json['name'] as String?,
        toolCallId: json['tool_call_id'] as String?,
        toolCalls: (json['tool_calls'] as List<dynamic>?)
            ?.map((tc) => ToolCall.fromJson(tc as Map<String, dynamic>))
            .toList(),
      );
}

class ChatCompletionRequest {
  final String model;
  final List<ChatMessage> messages;
  final double? temperature;
  final bool stream;
  final int? maxTokens;
  final List<Tool>? tools;
  final dynamic toolChoice;

  ChatCompletionRequest({
    this.model = 'gemini-pro',
    required this.messages,
    this.temperature = 0.7,
    this.stream = false,
    this.maxTokens,
    this.tools,
    this.toolChoice = 'auto',
  });

  Map<String, dynamic> toJson() => {
        'model': model,
        'messages': messages.map((m) => m.toJson()).toList(),
        if (temperature != null) 'temperature': temperature,
        'stream': stream,
        if (maxTokens != null) 'max_tokens': maxTokens,
        if (tools != null) 'tools': tools!.map((t) => t.toJson()).toList(),
        if (toolChoice != null) 'tool_choice': toolChoice,
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

  List<ToolCall> get toolCalls => choices.isNotEmpty ? choices.first.message?.toolCalls ?? [] : [];

  bool get isToolCall => choices.isNotEmpty && choices.first.finishReason == 'tool_calls';

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
