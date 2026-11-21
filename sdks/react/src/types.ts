/**
 * Type definitions for Web2API Client & React Hooks with Tool Calling
 */

export interface Web2ApiOptions {
  baseUrl?: string;
  apiKey?: string;
  timeoutMs?: number;
}

export interface FunctionCall {
  name: string;
  arguments: string;
}

export interface ToolCall {
  id: string;
  type: 'function';
  function: FunctionCall;
}

export interface FunctionDefinition {
  name: string;
  description?: string;
  parameters?: Record<string, any>;
}

export interface Tool {
  type: 'function';
  function: FunctionDefinition;
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content?: string | null;
  name?: string;
  tool_call_id?: string;
  tool_calls?: ToolCall[];
}

export interface ChatCompletionRequest {
  model?: string;
  messages: ChatMessage[];
  temperature?: number;
  stream?: boolean;
  max_tokens?: number;
  tools?: Tool[];
  tool_choice?: 'auto' | 'none' | 'required' | { type: 'function'; function: { name: string } };
}

export interface ChatChoice {
  index: number;
  message?: ChatMessage;
  delta?: {
    role?: string;
    content?: string;
    tool_calls?: Array<{
      index: number;
      id?: string;
      type?: 'function';
      function?: {
        name?: string;
        arguments?: string;
      };
    }>;
  };
  finish_reason?: 'stop' | 'tool_calls' | 'length' | null;
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
  tools?: Tool[];
  onFinish?: (fullText: string) => void;
  onError?: (err: Error) => void;
}
