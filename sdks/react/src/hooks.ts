import { useState, useCallback, useRef, useEffect } from 'react';
import { Web2ApiClient } from './client';
import { ChatMessage, UseChatOptions, HealthStatus } from './types';

/**
 * Custom React Hook for live AI chat with real-time streaming.
 *
 * Example:
 * ```tsx
 * const { messages, sendMessage, isStreaming, reset } = useWeb2ApiChat({
 *   baseUrl: 'http://localhost:8000',
 *   model: 'gemini-pro'
 * });
 * ```
 */
export function useWeb2ApiChat(options: UseChatOptions = {}) {
  const {
    baseUrl = 'http://127.0.0.1:8000',
    apiKey,
    model = 'gemini-pro',
    initialMessages = [],
    onFinish,
    onError,
  } = options;

  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const clientRef = useRef<Web2ApiClient>(new Web2ApiClient({ baseUrl, apiKey }));
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    clientRef.current = new Web2ApiClient({ baseUrl, apiKey });
  }, [baseUrl, apiKey]);

  const sendMessage = useCallback(
    async (prompt: string, overrideModel?: string) => {
      if (!prompt.trim()) return;

      setError(null);
      setIsLoading(true);
      setIsStreaming(true);

      const userMessage: ChatMessage = { role: 'user', content: prompt };
      const assistantMessage: ChatMessage = { role: 'assistant', content: '' };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        let fullAnswer = '';
        await clientRef.current.chatStream(
          prompt,
          overrideModel || model,
          (token) => {
            fullAnswer += token;
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last && last.role === 'assistant') {
                updated[updated.length - 1] = { ...last, content: fullAnswer };
              }
              return updated;
            });
          },
          controller.signal
        );

        if (onFinish) onFinish(fullAnswer);
      } catch (err: any) {
        if (err.name === 'AbortError') return;
        const e = err instanceof Error ? err : new Error(String(err));
        setError(e);
        if (onError) onError(e);
      } finally {
        setIsLoading(false);
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    [model, onFinish, onError]
  );

  const abort = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsLoading(false);
      setIsStreaming(false);
    }
  }, []);

  const reset = useCallback(async () => {
    abort();
    try {
      await clientRef.current.resetConversation();
    } catch {
      // Ignore reset failure
    }
    setMessages([]);
    setError(null);
  }, [abort]);

  return {
    messages,
    sendMessage,
    isLoading,
    isStreaming,
    error,
    abort,
    reset,
  };
}

/**
 * Custom React Hook for monitoring Web2API server and extension status.
 */
export function useWeb2ApiStatus(options: { baseUrl?: string; apiKey?: string; pollIntervalMs?: number } = {}) {
  const { baseUrl = 'http://127.0.0.1:8000', apiKey, pollIntervalMs = 10000 } = options;

  const [status, setStatus] = useState<HealthStatus | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const check = useCallback(async () => {
    setIsChecking(true);
    try {
      const client = new Web2ApiClient({ baseUrl, apiKey });
      const health = await client.checkHealth();
      setStatus(health);
      setError(null);
    } catch (err: any) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setStatus(null);
    } finally {
      setIsChecking(false);
    }
  }, [baseUrl, apiKey]);

  useEffect(() => {
    check();
    if (pollIntervalMs > 0) {
      const interval = setInterval(check, pollIntervalMs);
      return () => clearInterval(interval);
    }
  }, [check, pollIntervalMs]);

  return {
    status,
    isChecking,
    error,
    isOnline: status?.status === 'online',
    isExtensionConnected: !!status?.extension_connected,
    refresh: check,
  };
}
