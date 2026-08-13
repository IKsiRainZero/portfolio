import { useState, useEffect } from 'react';
import type { TraceRecord } from '../../types';
import { api } from '../../api/client';
import TraceDetail from './TraceDetail';
import styles from './TraceTimeline.module.css';

interface Props {
  project?: string;
}

const opLabels: Record<string, string> = {
  'test.run': 'Test Run', 'file.write': 'File Write', 'git.commit': 'Git Commit',
  'tool.execute': 'Tool Execute', 'project.init': 'Project Init',
  'workspace.summary': 'Dashboard Load', 'projects.list': 'Projects Load',
  'projects.detail': 'Project Detail',
};

export default function TraceTimeline({ project }: Props) {
  const [traces, setTraces] = useState<TraceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<TraceRecord | null>(null);

  useEffect(() => {
    api.getTraces({ project }).then(r => { setTraces(r.traces); }).finally(() => setLoading(false));
  }, [project]);

  if (loading) return <div className={styles.loading}>Loading traces...</div>;
  if (traces.length === 0) return <div className={styles.empty}>No traces yet — start using the Console to generate them</div>;

  return (
    <div>
      <h3 className={styles.title}>Operation Traces ({traces.length})</h3>
      {traces.map(t => (
        <div key={t.id} className={styles.row} onClick={() => setSelected(t)}>
          <span className={`${styles.status} ${styles[t.status]}`}>{t.status === 'ok' ? '✓' : '✗'}</span>
          <span className={styles.op}>{opLabels[t.operation] || t.operation}</span>
          <span className={styles.target}>{t.target}</span>
          <span className={styles.time}>{t.timestamp?.slice(11, 19) || ''}</span>
          <span className={styles.dur}>{t.duration_ms}ms</span>
        </div>
      ))}
      {selected && <TraceDetail trace={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
