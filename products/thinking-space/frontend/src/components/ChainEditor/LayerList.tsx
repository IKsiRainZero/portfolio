import { useState, useRef } from 'react';
import type { Layer } from '../../types';
import styles from './ChainEditor.module.css';

interface Props {
  layers: Layer[];
  onCreate: (name: string) => void;
  onRename: (id: string, name: string) => void;
  onUpdateDesc: (id: string, desc: string) => void;
  onDelete: (id: string) => void;
  onReorder: (orderedIds: string[]) => void;
}

export default function LayerList({ layers, onCreate, onRename, onUpdateDesc, onDelete, onReorder }: Props) {
  const [newName, setNewName] = useState('');
  const dragId = useRef<string | null>(null);
  const [localNames, setLocalNames] = useState<Record<string, string>>({});
  const [localDescs, setLocalDescs] = useState<Record<string, string>>({});

  const create = () => { if (newName.trim()) { onCreate(newName.trim()); setNewName(''); } };

  const onDrop = (targetId: string) => {
    const from = dragId.current;
    if (!from || from === targetId) return;
    const ids = layers.map((l) => l.id);
    const next = ids.filter((i) => i !== from);
    next.splice(next.indexOf(targetId), 0, from);
    onReorder(next);
    dragId.current = null;
  };

  const nameOf = (l: Layer) => localNames[l.id] ?? l.name;
  const descOf = (l: Layer) => localDescs[l.id] ?? l.description;

  const handleNameChange = (id: string, value: string) => {
    setLocalNames((prev) => ({ ...prev, [id]: value }));
  };
  const handleDescChange = (id: string, value: string) => {
    setLocalDescs((prev) => ({ ...prev, [id]: value }));
  };
  const handleNameBlur = (id: string) => {
    const v = localNames[id];
    if (v !== undefined) onRename(id, v);
  };
  const handleDescBlur = (id: string) => {
    const v = localDescs[id];
    if (v !== undefined) onUpdateDesc(id, v);
  };
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') e.currentTarget.blur();
  };

  return (
    <div className={`${styles.panel} ${styles.layerPanel}`}>
      <div className={styles.h}>层级（拖拽重排）</div>
      {layers.map((l) => (
        <div key={l.id} className={`${styles.item} ${styles.dragItem}`} draggable
             onDragStart={() => (dragId.current = l.id)}
             onDragOver={(e) => e.preventDefault()}
             onDrop={() => onDrop(l.id)}>
          <div style={{ flex: 1 }}>
            <input value={nameOf(l)}
                   onChange={(e) => handleNameChange(l.id, e.target.value)}
                   onBlur={() => handleNameBlur(l.id)}
                   onKeyDown={handleKeyDown} />
            <input value={descOf(l)} placeholder="描述" style={{ fontSize: 12, color: '#86868b' }}
                   onChange={(e) => handleDescChange(l.id, e.target.value)}
                   onBlur={() => handleDescBlur(l.id)}
                   onKeyDown={handleKeyDown} />
          </div>
          <button className={styles.del} onClick={() => onDelete(l.id)}>×</button>
        </div>
      ))}
      <div className={styles.addRow}>
        <input placeholder="新层级名称" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <button onClick={create}>新增层级</button>
      </div>
    </div>
  );
}
