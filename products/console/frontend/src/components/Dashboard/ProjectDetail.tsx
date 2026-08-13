import type { Project } from '../../types';
import styles from './ProjectDetail.module.css';

interface Props {
  project: Project;
  onClose: () => void;
}

export default function ProjectDetail({ project, onClose }: Props) {
  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.panel} onClick={e => e.stopPropagation()}>
        <div className={styles.header}>
          <h2>{project.name}</h2>
          <button onClick={onClose}>&times;</button>
        </div>
        <div className={styles.body}>
          <div className={styles.section}>
            <h3>Status</h3>
            <p>Phase: {project.phase || '—'} &middot; {project.tests.total > 0 ? `${project.tests.passed}/${project.tests.total} tests` : 'no tests'} &middot; {project.status}</p>
          </div>
          <div className={styles.section}>
            <h3>Activity Timeline</h3>
            {project.activity.length === 0 && <p className={styles.empty}>No recent activity</p>}
            {project.activity.map((a, i) => (
              <div key={i} className={styles.line}><span className={styles.type}>{a.type}</span> {a.summary}</div>
            ))}
          </div>
          <div className={styles.section}>
            <h3>Risks</h3>
            {project.risks.length === 0 && <p className={styles.empty}>No risks</p>}
            {project.risks.map((r, i) => <div key={i} className={styles.risk}>{'⚠'} {r.text} <span className={styles.src}>{r.source}</span></div>)}
          </div>
          <div className={styles.section}>
            <h3>Constitution Files</h3>
            {project.constitution_files.map(f => <code key={f} className={styles.file}>{f}</code>)}
          </div>
        </div>
      </div>
    </div>
  );
}
