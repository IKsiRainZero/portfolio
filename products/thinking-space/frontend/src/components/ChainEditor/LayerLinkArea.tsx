import { useState } from 'react';
import type { Layer, LayerLink } from '../../types';
import styles from './ChainEditor.module.css';

interface Props {
  layers: Layer[];
  links: LayerLink[];
  onCreateLink: (sourceId: string, targetId: string) => void;
  onDeleteLink: (id: string) => void;
}

const NODE_H = 56;
const NODE_X = 40;
const NODE_W = 120;

export default function LayerLinkArea({ layers, links, onCreateLink, onDeleteLink }: Props) {
  const [pending, setPending] = useState<string | null>(null);
  const ordered = [...layers].sort((a, b) => a.level - b.level);
  const yOf = (id: string) => {
    const i = ordered.findIndex((l) => l.id === id);
    return 20 + i * NODE_H + 18;
  };

  const clickNode = (id: string) => {
    if (pending && pending !== id) { onCreateLink(pending, id); setPending(null); }
    else setPending(id);
  };

  const bez = (sy: number, ty: number) => {
    const sx = NODE_X + NODE_W, tx = NODE_X + NODE_W;
    const bulge = 60 + Math.abs(ty - sy) * 0.3;
    return `M ${sx} ${sy} C ${sx + bulge} ${sy}, ${tx + bulge} ${ty}, ${tx} ${ty}`;
  };

  const has = (id: string) => ordered.some((l) => l.id === id);

  return (
    <div className={`${styles.panel} ${styles.linkPanel}`}>
      <div className={styles.h}>层级逻辑链（点两个节点连线）</div>
      <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
        {links.map((k) => {
          if (!has(k.source_layer_id) || !has(k.target_layer_id)) return null;
          return (
            <path key={k.id} d={bez(yOf(k.source_layer_id), yOf(k.target_layer_id))} fill="none"
                  stroke="#0a84ff" strokeWidth={2} style={{ pointerEvents: 'stroke', cursor: 'pointer' }}
                  onClick={() => onDeleteLink(k.id)} />
          );
        })}
      </svg>
      {ordered.map((l, i) => (
        <div key={l.id} onClick={() => clickNode(l.id)}
             style={{ position: 'absolute', left: NODE_X, top: 20 + i * NODE_H, width: NODE_W,
                      padding: '8px 10px', borderRadius: 8, cursor: 'pointer',
                      background: pending === l.id ? '#0a84ff' : '#f0f0f2',
                      color: pending === l.id ? '#fff' : '#1d1d1f' }}>
          {l.name}
        </div>
      ))}
    </div>
  );
}
