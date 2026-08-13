import styles from './ToolCallCard.module.css';

interface Props {
  toolCall: {
    name: string;
    traceId: string;
    status: 'running' | 'done' | 'error';
    result?: unknown;
  };
}

export default function ToolCallCard({ toolCall }: Props) {
  const { name, status, result } = toolCall;
  return (
    <div className={`${styles.card} ${styles[status]}`}>
      <div className={styles.header}>
        <span className={styles.icon}>{status === 'running' ? '◌' : status === 'done' ? '✓' : '✗'}</span>
        <span className={styles.name}>{name}</span>
        {status === 'running' && <span className={styles.progress}>running...</span>}
      </div>
      {result != null && (
        <pre className={styles.result}>{JSON.stringify(result, null, 2).slice(0, 300)}</pre>
      )}
    </div>
  );
}
