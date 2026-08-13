import { useState } from 'react';
import type { Entry, Layer } from '../../types';
import styles from './CardEditor.module.css';

interface Props {
  entry: Entry;
  layers: Layer[];
  onSave: (patch: Partial<Entry>) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
  onConfirm?: (id: string) => void;
  onIgnore?: (id: string) => void;
}

export default function CardEditor({ entry, layers, onSave, onDelete, onClose, onConfirm, onIgnore }: Props) {
  const [title, setTitle] = useState(entry.title);
  const [content, setContent] = useState(entry.content);
  const [entryType, setEntryType] = useState(entry.entry_type);
  const [tagIds, setTagIds] = useState<string[]>(entry.tag_ids || []);
  const [zDepth, setZDepth] = useState(entry.z_depth || 0);

  const toggleTag = (id: string) =>
    setTagIds((t) => (t.includes(id) ? t.filter((x) => x !== id) : [...t, id]));

  const save = () => {
    onSave({ title, content, entry_type: entryType, tag_ids: tagIds, z_depth: zDepth });
    onClose();
  };

  return (
    <div className={styles.editor} style={{ left: entry.x + entry.width + 8, top: entry.y }} onMouseDown={(e) => e.stopPropagation()}>
      {entry.status === 'pending' && (
        <div className={styles.row}>
          <span>待确认</span>
          <button onClick={() => onConfirm?.(entry.id)}>确认</button>
          <button onClick={() => onIgnore?.(entry.id)}>忽略</button>
        </div>
      )}
      <input placeholder="标题" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea placeholder="内容" rows={3} value={content} onChange={(e) => setContent(e.target.value)} />
      <select value={entryType} onChange={(e) => setEntryType(e.target.value as Entry['entry_type'])}>
        <option value="known">已知</option>
        <option value="unknown">未知缺口</option>
        <option value="question">问题</option>
      </select>
      <div className={styles.tags}>
        {layers.map((l) => (
          <span key={l.id} className={`${styles.tag} ${tagIds.includes(l.id) ? styles.tagOn : ''}`}
                onClick={() => toggleTag(l.id)}>{l.name}</span>
        ))}
      </div>
      <div className={styles.row}>
        <span>纵深</span>
        <input type="range" min={0} max={1} step={0.1} value={zDepth}
               onChange={(e) => setZDepth(parseFloat(e.target.value))} />
      </div>
      <div className={styles.actions}>
        <button className={styles.del} onClick={() => onDelete(entry.id)}>删除</button>
        <div>
          <button onClick={onClose}>取消</button>
          <button onClick={save}>保存</button>
        </div>
      </div>
    </div>
  );
}
