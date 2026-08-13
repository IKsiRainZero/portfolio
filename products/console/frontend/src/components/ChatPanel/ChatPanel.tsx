import { useState, useRef, useEffect } from 'react';
import type { ChatMessage } from '../../types';
import ToolCallCard from './ToolCallCard';
import styles from './ChatPanel.module.css';

interface Props {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  sending: boolean;
  sseDisconnected: boolean;
  onReconnect: () => void;
}

export default function ChatPanel({ messages, onSend, sending, sseDisconnected, onReconnect }: Props) {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (text && !sending) { onSend(text); setInput(''); }
  };

  return (
    <div className={styles.panel}>
      {sseDisconnected && (
        <div className={styles.disconnectBanner}>Connection lost. <button onClick={onReconnect}>Reconnect</button></div>
      )}
      <div className={styles.messages}>
        {messages.length === 0 && (
          <div className={styles.welcome}>
            <p>Welcome to Portfolio Console.</p>
            <p>Try: "Show me all projects" or "Run Crescent's tests"</p>
          </div>
        )}
        {messages.map(m => (
          <div key={m.id} className={`${styles.bubble} ${styles[m.role]}`}>
            {m.role === 'tool' && m.toolCall
              ? <ToolCallCard toolCall={m.toolCall} />
              : <div className={styles.content}>{m.content}</div>
            }
          </div>
        ))}
        {sending && <div className={`${styles.bubble} ${styles.assistant}`}><span className={styles.cursor}>▌</span></div>}
        <div ref={bottomRef} />
      </div>
      <div className={styles.inputArea}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleSend(); }}
          placeholder="Type a message..."
          disabled={sending}
          className={styles.input}
        />
        <button onClick={handleSend} disabled={sending || !input.trim()} className={styles.sendBtn}>Send</button>
      </div>
    </div>
  );
}
