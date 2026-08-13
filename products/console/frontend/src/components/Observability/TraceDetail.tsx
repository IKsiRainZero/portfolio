import type { TraceRecord } from '../../types';
import styles from './TraceDetail.module.css';

interface Props {
  trace: TraceRecord;
  onClose: () => void;
}

export default function TraceDetail({ trace, onClose }: Props) {
  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.panel} onClick={e => e.stopPropagation()}>
        <div className={styles.header}>
          <h3>Trace Detail</h3>
          <button onClick={onClose}>&times;</button>
        </div>
        <dl className={styles.dl}>
          <dt>ID</dt><dd>{trace.id}</dd>
          <dt>Timestamp</dt><dd>{trace.timestamp}</dd>
          <dt>Operation</dt><dd>{trace.operation}</dd>
          <dt>Target</dt><dd>{trace.target}</dd>
          <dt>Status</dt><dd className={trace.status === 'ok' ? styles.ok : styles.err}>{trace.status}</dd>
          <dt>Duration</dt><dd>{trace.duration_ms}ms</dd>
          <dt>Input</dt><dd className={styles.pre}>{trace.input_summary || '(none)'}</dd>
          <dt>Output</dt><dd className={styles.pre}>{trace.output_summary || '(none)'}</dd>
          {trace.parent_trace_id && <><dt>Parent</dt><dd>{trace.parent_trace_id}</dd></>}
        </dl>
      </div>
    </div>
  );
}
