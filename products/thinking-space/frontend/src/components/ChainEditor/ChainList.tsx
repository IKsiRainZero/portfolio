import { useState } from 'react';
import type { Dimension } from '../../types';
import styles from './ChainEditor.module.css';

interface Props {
  dimensions: Dimension[];
  activeId: string;
  onSelect: (id: string) => void;
  onCreate: (name: string) => void;
  onRename: (id: string, name: string) => void;
  onDelete: (id: string) => void;
}

export default function ChainList({ dimensions, activeId, onSelect, onCreate, onRename, onDelete }: Props) {
  const [newName, setNewName] = useState('');
  const [localNames, setLocalNames] = useState<Record<string, string>>({});

  const create = () => { if (newName.trim()) { onCreate(newName.trim()); setNewName(''); } };

  const nameOf = (d: Dimension) => localNames[d.id] ?? d.name;

  const handleChange = (id: string, value: string) => {
    setLocalNames((prev) => ({ ...prev, [id]: value }));
  };

  const handleBlur = (id: string) => {
    const v = localNames[id];
    if (v !== undefined) onRename(id, v);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') e.currentTarget.blur();
  };

  return (
    <div className={`${styles.panel} ${styles.chainPanel}`}>
      <div className={styles.h}>思维链</div>
      {dimensions.map((d) => (
        <div key={d.id} className={`${styles.item} ${d.id === activeId ? styles.active : ''}`} onClick={() => onSelect(d.id)}>
          <input value={nameOf(d)} onClick={(e) => e.stopPropagation()}
                 onChange={(e) => handleChange(d.id, e.target.value)}
                 onBlur={() => handleBlur(d.id)}
                 onKeyDown={handleKeyDown} />
          <button className={styles.del} onClick={(e) => { e.stopPropagation(); onDelete(d.id); }}>×</button>
        </div>
      ))}
      <div className={styles.addRow}>
        <input placeholder="新链名称" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <button onClick={create}>新建链</button>
      </div>
    </div>
  );
}
