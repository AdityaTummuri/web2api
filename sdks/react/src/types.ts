/**
 * Type definitions for Web2API Client & React Hooks
 */

export interface Web2ApiOptions {
  baseUrl?: string;
  apiKey?: string;
  timeoutMs?: number;
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ChatCompletionRequest {
  model?: string;
  messages: ChatMessage[];
  temperature?: number;
  stream?: boolean;
  max_tokens?: number;
}

export interface ChatChoice {
  index: number;
  message?: ChatMessage;
  delta?: {
    role?: string;
    content?: string;
  };
  finish_reason?: string | null;
}

export interface ChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: ChatChoice[];
  latency_seconds?: number;
}

export interface Web2ApiChatResponse {
  response: string;
  latency_seconds: number;
  status: string;
  extracted?: Record<string, any>;
}

export interface HealthStatus {
  status: string;
  extension_connected: boolean;
  auth_required: boolean;
  timestamp?: string;
  stats?: Record<string, any>;
}

export interface UseChatOptions extends Web2ApiOptions {
  model?: string;
  initialMessages?: ChatMessage[];
  onFinish?: (fullText: string) => void;
  onError?: (err: Error) => void;
}
