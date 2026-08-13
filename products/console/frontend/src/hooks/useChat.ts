import { useState, useCallback, useRef } from 'react';
import type { ChatMessage } from '../types';
import { api } from '../api/client';

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [sseDisconnected, setSseDisconnected] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);

  const send = useCallback((text: string, context: Record<string, unknown> = {}) => {
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: text };
    const assistantMsg: ChatMessage = { id: crypto.randomUUID(), role: 'assistant', content: '' };
    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setSending(true);
    setSseDisconnected(false);

    controllerRef.current = api.chatStream(
      text,
      context,
      (type, data: any) => {
        switch (type) {
          case 'message_delta':
            setMessages(prev => prev.map(m =>
              m.id === assistantMsg.id ? { ...m, content: m.content + (data.content || '') } : m
            ));
            break;
          case 'tool_start':
            setMessages(prev => [...prev, {
              id: crypto.randomUUID(), role: 'tool', content: '',
              toolCall: { name: data.tool, traceId: data.trace_id, status: 'running' as const }
            }]);
            break;
          case 'tool_end':
            setMessages(prev => prev.map(m =>
              m.toolCall?.traceId === data.trace_id
                ? { ...m, toolCall: { ...m.toolCall!, status: data.result?.status === 'error' ? 'error' as const : 'done' as const, result: data.result } }
                : m
            ));
            break;
          case 'error':
            setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'system', content: `Error: ${data.message}` }]);
            setSseDisconnected(true);
            break;
          case 'message_end':
            setSending(false);
            break;
        }
      },
      () => { setSending(false); setSseDisconnected(true); }
    );
  }, []);

  return { messages, sending, sseDisconnected, send, setMessages };
}
