import type { Project } from '../../types';
import styles from './ProjectCard.module.css';

interface Props {
  project: Project;
  onSelect: (name: string) => void;
}

const statusColors: Record<string, string> = { active: '#22c55e', dormant: '#9ca3af', ready: '#3b82f6', archived: '#6b7280', unknown: '#9ca3af' };
const testColor = (p: Project) => p.tests.total === 0 ? '#9ca3af' : p.tests.failed > 0 ? '#ef4444' : '#22c55e';

export default function ProjectCard({ project, onSelect }: Props) {
  return (
    <div className={styles.card} onClick={() => onSelect(project.name)}>
      <div className={styles.top}>
        <span className={styles.dot} style={{ background: statusColors[project.status] }} />
        <strong>{project.name}</strong>
        <span className={styles.phase}>{project.phase || '—'}</span>
      </div>
      <div className={styles.meta}>
        <span style={{ color: testColor(project) }}>
          {project.tests.total > 0 ? `${project.tests.passed}/${project.tests.total} tests` : 'no tests'}
        </span>
        {project.git_status && (
          <span>{project.git_status.uncommitted > 0 ? `${project.git_status.uncommitted} uncommitted` : 'clean'}</span>
        )}
      </div>
      {project.activity.length > 0 && (
        <div className={styles.activity}>
          {project.activity.slice(0, 3).map((a, i) => (
            <div key={i} className={styles.activityItem}>{a.summary}</div>
          ))}
        </div>
      )}
      {project.risks.length > 0 && (
        <div className={styles.risks}>
          <span className={styles.riskBadge}>{'⚠'} {project.risks.length}</span>
          {project.risks.map((r, i) => <span key={i} className={styles.riskText}>{r.text}</span>)}
        </div>
      )}
    </div>
  );
}
