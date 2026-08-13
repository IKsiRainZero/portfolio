import { useRef, useState } from 'react';
import type { Entry } from '../../types';
import styles from './CardNode.module.css';

const TYPE_COLORS: Record<string, string> = { known: '#34c759', unknown: '#ff3b30', question: '#ffcc00' };
const COLLAPSE_WIDTH = 120;

interface Props {
  entry: Entry;
  scale: number;
  selected: boolean;
  onSelect: (id: string) => void;
  onDragEnd: (id: string, x: number, y: number) => void;
  onResizeEnd: (id: string, width: number, height: number) => void;
  onStartConnect: (id: string) => void;
}

export default function CardNode({ entry, scale, selected, onSelect, onDragEnd, onResizeEnd, onStartConnect }: Props) {
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number; moved: boolean; finalX: number; finalY: number } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; origW: number; origH: number; finalW: number; finalH: number } | null>(null);
  const [localPos, setLocalPos] = useState<{ x: number; y: number } | null>(null);
  const [localSize, setLocalSize] = useState<{ w: number; h: number } | null>(null);

  const depth = entry.z_depth || 0;
  const displayW = localSize?.w ?? entry.width;
  const collapsed = displayW < COLLAPSE_WIDTH;

  const onCardMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation();
    dragRef.current = { startX: e.clientX, startY: e.clientY, origX: entry.x, origY: entry.y, moved: false, finalX: entry.x, finalY: entry.y };
    window.addEventListener('mousemove', onDragMove);
    window.addEventListener('mouseup', onDragUp);
  };
  const onDragMove = (e: MouseEvent) => {
    const d = dragRef.current;
    if (!d) return;
    const dx = (e.clientX - d.startX) / scale;
    const dy = (e.clientY - d.startY) / scale;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) d.moved = true;
    d.finalX = d.origX + dx;
    d.finalY = d.origY + dy;
    setLocalPos({ x: d.finalX, y: d.finalY });
  };
  const onDragUp = () => {
    const d = dragRef.current;
    window.removeEventListener('mousemove', onDragMove);
    window.removeEventListener('mouseup', onDragUp);
    if (d) {
      if (d.moved) {
        onDragEnd(entry.id, d.finalX, d.finalY);
      } else {
        onSelect(entry.id);
      }
    }
    setLocalPos(null);
    dragRef.current = null;
  };

  const onResizeMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation();
    resizeRef.current = { startX: e.clientX, startY: e.clientY, origW: entry.width, origH: entry.height, finalW: entry.width, finalH: entry.height };
    window.addEventListener('mousemove', onResizeMove);
    window.addEventListener('mouseup', onResizeUp);
  };
  const onResizeMove = (e: MouseEvent) => {
    const r = resizeRef.current;
    if (!r) return;
    r.finalW = Math.max(80, r.origW + (e.clientX - r.startX) / scale);
    r.finalH = Math.max(60, r.origH + (e.clientY - r.startY) / scale);
    setLocalSize({ w: r.finalW, h: r.finalH });
  };
  const onResizeUp = () => {
    const r = resizeRef.current;
    window.removeEventListener('mousemove', onResizeMove);
    window.removeEventListener('mouseup', onResizeUp);
    if (r) {
      onResizeEnd(entry.id, r.finalW, r.finalH);
    }
    setLocalSize(null);
    resizeRef.current = null;
  };

  return (
    <div
      className={`${styles.card} ${selected ? styles.selected : ''}`}
      style={{
        left: localPos?.x ?? entry.x, top: localPos?.y ?? entry.y,
        width: localSize?.w ?? entry.width, height: localSize?.h ?? entry.height,
        borderLeft: `3px solid ${TYPE_COLORS[entry.entry_type] || '#86868b'}`,
        filter: depth > 0 ? `blur(${depth * 1.5}px)` : undefined,
        opacity: 1 - depth * 0.5,
      }}
      onMouseDown={onCardMouseDown}
    >
      <span className={styles.title}>
        {entry.title}
        {entry.status === 'pending' && <span className={styles.badge}>待确认</span>}
      </span>
      {!collapsed && entry.content && <span className={styles.content}>{entry.content}</span>}
      <div className={styles.connectDot} onMouseDown={(e) => { e.stopPropagation(); onStartConnect(entry.id); }} />
      <div className={styles.resizeHandle} onMouseDown={onResizeMouseDown} />
    </div>
  );
}
