import { useState } from 'react';
import type { Project } from '../../types';
import ProjectCard from './ProjectCard';
import styles from './ProjectGroup.module.css';

interface Props {
  title: string;
  projects: Project[];
  onSelect: (name: string) => void;
}

export default function ProjectGroup({ title, projects, onSelect }: Props) {
  const [open, setOpen] = useState(true);
  return (
    <div className={styles.group}>
      <div className={styles.header} onClick={() => setOpen(!open)}>
        <span>{open ? '▾' : '▸'}</span> {title} ({projects.length})
      </div>
      {open && (
        <div className={styles.cards}>
          {projects.map(p => <ProjectCard key={p.name} project={p} onSelect={onSelect} />)}
        </div>
      )}
    </div>
  );
}
