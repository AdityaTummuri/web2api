import React, { useState } from 'react';
import { useWeb2ApiChat, useWeb2ApiStatus } from '../hooks';

export interface ChatBoxProps {
  baseUrl?: string;
  apiKey?: string;
  model?: string;
  title?: string;
}

/**
 * Ready-to-use plug-and-play Chat UI component.
 */
export const Web2ApiChatBox: React.FC<ChatBoxProps> = ({
  baseUrl = 'http://127.0.0.1:8000',
  apiKey,
  model = 'gemini-pro',
  title = 'Web2API AI Assistant',
}) => {
  const [input, setInput] = useState('');
  const { messages, sendMessage, isStreaming, reset, error } = useWeb2ApiChat({
    baseUrl,
    apiKey,
    model,
  });

  const { isOnline, isExtensionConnected } = useWeb2ApiStatus({ baseUrl, apiKey });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    sendMessage(input);
    setInput('');
  };

  return (
    <div style={{
      maxWidth: '650px',
      margin: '0 auto',
      border: '1px solid #e2e8f0',
      borderRadius: '12px',
      display: 'flex',
      flexDirection: 'column',
      height: '520px',
      backgroundColor: '#ffffff',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: '#f8fafc'
      }}>
        <div>
          <strong style={{ fontSize: '15px' }}>{title}</strong>
          <div style={{ fontSize: '12px', color: '#64748b' }}>
            Model: <span style={{ color: '#2563eb' }}>{model}</span> |
            Server: <span style={{ color: isOnline ? '#16a34a' : '#dc2626' }}>{isOnline ? 'Online' : 'Offline'}</span> |
            Browser: <span style={{ color: isExtensionConnected ? '#16a34a' : '#d97706' }}>
              {isExtensionConnected ? 'Linked' : 'Waiting Extension'}
            </span>
          </div>
        </div>
        <button
          onClick={reset}
          style={{
            fontSize: '12px',
            padding: '4px 8px',
            borderRadius: '6px',
            border: '1px solid #cbd5e1',
            background: '#ffffff',
            cursor: 'pointer'
          }}
        >
          Reset Thread
        </button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, padding: '16px', overflowY: 'auto' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#94a3b8', marginTop: '120px' }}>
            Ask Gemini, ChatGPT, or Claude anything through your standalone bridge!
          </div>
        )}
        {messages.map((m, idx) => (
          <div
            key={idx}
            style={{
              marginBottom: '12px',
              display: 'flex',
              justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start'
            }}
          >
            <div style={{
              maxWidth: '80%',
              padding: '10px 14px',
              borderRadius: '12px',
              fontSize: '14px',
              lineHeight: '1.5',
              backgroundColor: m.role === 'user' ? '#2563eb' : '#f1f5f9',
              color: m.role === 'user' ? '#ffffff' : '#1e293b'
            }}>
              {m.content || (isStreaming ? 'Thinking...' : '')}
            </div>
          </div>
        ))}
        {error && (
          <div style={{ color: '#dc2626', fontSize: '12px', padding: '8px', background: '#fee2e2', borderRadius: '6px' }}>
            Error: {error.message}
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} style={{ padding: '12px', borderTop: '1px solid #e2e8f0', display: 'flex', gap: '8px' }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question..."
          style={{
            flex: 1,
            padding: '10px 14px',
            borderRadius: '8px',
            border: '1px solid #cbd5e1',
            outline: 'none',
            fontSize: '14px'
          }}
        />
        <button
          type="submit"
          disabled={isStreaming}
          style={{
            padding: '10px 18px',
            backgroundColor: isStreaming ? '#94a3b8' : '#2563eb',
            color: '#ffffff',
            border: 'none',
            borderRadius: '8px',
            fontWeight: 600,
            cursor: isStreaming ? 'not-allowed' : 'pointer'
          }}
        >
          {isStreaming ? 'Streaming...' : 'Send'}
        </button>
      </form>
    </div>
  );
};
