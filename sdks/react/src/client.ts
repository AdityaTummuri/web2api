import {
  Web2ApiOptions,
  Web2ApiChatResponse,
  ChatCompletionRequest,
  ChatCompletionResponse,
  HealthStatus,
} from './types';

/**
 * Universal Web2API Client for Browser, Node.js, Next.js, and React Native.
 */
export class Web2ApiClient {
  readonly baseUrl: string;
  readonly apiKey?: string;
  readonly timeoutMs: number;

  constructor(options: Web2ApiOptions = {}) {
    this.baseUrl = (options.baseUrl || 'http://127.0.0.1:8000').replace(/\/+$/, '');
    this.apiKey = options.apiKey;
    this.timeoutMs = options.timeoutMs || 120000;
  }

  private getHeaders(contentType = 'application/json'): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': contentType,
      Accept: 'application/json',
    };
    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
      headers['X-API-Key'] = this.apiKey;
    }
    return headers;
  }

  /**
   * Health check: verifies server availability and extension connection.
   */
  async checkHealth(): Promise<HealthStatus> {
    const res = await fetch(`${this.baseUrl}/health`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Health check failed: HTTP ${res.status}`);
    }
    return (await res.json()) as HealthStatus;
  }

  /**
   * Executes a direct prompt query.
   */
  async chat(prompt: string, model = 'gemini-pro'): Promise<string> {
    const full = await this.chatFull(prompt, model);
    return full.response;
  }

  /**
   * Executes a direct prompt query and returns the full response object with latency metrics.
   */
  async chatFull(prompt: string, model = 'gemini-pro'): Promise<Web2ApiChatResponse> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const res = await fetch(`${this.baseUrl}/api/chat`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify({
          prompt,
          model,
          timeout: this.timeoutMs / 1000,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const body = await res.text();
        throw new Error(`Web2API error (${res.status}): ${body}`);
      }

      return (await res.json()) as Web2ApiChatResponse;
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * Real-time Server-Sent Events (SSE) streaming.
   * Calls onToken for each token delta as it arrives from the browser session.
   */
  async chatStream(
    prompt: string,
    model = 'gemini-pro',
    onToken?: (token: string) => void,
    signal?: AbortSignal
  ): Promise<string> {
    const res = await fetch(`${this.baseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        ...this.getHeaders(),
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({
        model,
        messages: [{ role: 'user', content: prompt }],
        stream: true,
      }),
      signal,
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`Streaming failed (${res.status}): ${body}`);
    }

    if (!res.body) {
      throw new Error('Response body is null, streaming unsupported by environment.');
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let accumulatedText = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data: ')) {
          const data = trimmed.slice(6).trim();
          if (data === '[DONE]') {
            return accumulatedText;
          }
          try {
            const parsed = JSON.parse(data);
            const content = parsed.choices?.[0]?.delta?.content;
            if (content) {
              accumulatedText += content;
              if (onToken) onToken(content);
            }
          } catch {
            // Ignore incomplete JSON chunks
          }
        }
      }
    }

    return accumulatedText;
  }

  /**
   * Standard OpenAI-compatible chat completions.
   */
  async createChatCompletion(request: ChatCompletionRequest): Promise<ChatCompletionResponse> {
    const res = await fetch(`${this.baseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(request),
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`Chat completion error (${res.status}): ${body}`);
    }

    return (await res.json()) as ChatCompletionResponse;
  }

  /**
   * Resets active browser conversation tab.
   */
  async resetConversation(): Promise<boolean> {
    const res = await fetch(`${this.baseUrl}/api/reset`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: '{}',
    });
    if (!res.ok) return false;
    const data = await res.json();
    return data.status === 'success';
  }
}
