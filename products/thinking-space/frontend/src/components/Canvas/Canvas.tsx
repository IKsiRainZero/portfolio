import { useState, useRef } from 'react';
import { useCanvasZoom } from '../../hooks/useCanvasZoom';
import type { Entry, Layer } from '../../types';
import CardNode from './CardNode';
import CardEditor from './CardEditor';
import ConnectionLayer from './ConnectionLayer';
import styles from './Canvas.module.css';

interface CrossLinkShape { id: string; source_entry_id: string; target_entry_id: string; }
interface Props {
  entries: Entry[];
  layers: Layer[];
  crossLinks: CrossLinkShape[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onDragEnd: (id: string, x: number, y: number) => void;
  onResizeEnd: (id: string, width: number, height: number) => void;
  onCreateAt: (x: number, y: number) => void;
  onSave: (id: string, patch: Partial<Entry>) => void;
  onDelete: (id: string) => void;
  onConnect: (sourceId: string, targetId: string) => void;
  onDeleteCrossLink: (id: string) => void;
  onConfirm: (id: string) => void;
  onIgnore: (id: string) => void;
}

export default function Canvas(props: Props) {
  const { entries, layers, crossLinks, selectedId } = props;
  const { scale, position, isPanning, onWheel, onMouseDown, onMouseMove, onMouseUp, screenToCanvas } = useCanvasZoom(1, 0.1, 3);
  const containerRef = useRef<HTMLDivElement>(null);
  const [connectFrom, setConnectFrom] = useState<string | null>(null);

  const rect = () => containerRef.current?.getBoundingClientRect() ?? { left: 0, top: 0 };

  const handleSurfaceMouseDown = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget || (e.target as HTMLElement).dataset.canvasSurface !== undefined) {
      props.onSelect(null);
      onMouseDown(e);
    }
  };

  const handleDoubleClick = (e: React.MouseEvent) => {
    const p = screenToCanvas(e.clientX, e.clientY, rect());
    props.onCreateAt(p.x, p.y);
  };

  const handleStartConnect = (sourceId: string) => setConnectFrom(sourceId);
  const handleCardSelect = (id: string) => {
    if (connectFrom && connectFrom !== id) {
      props.onConnect(connectFrom, id);
      setConnectFrom(null);
    } else {
      props.onSelect(id);
    }
  };

  const selected = entries.find((e) => e.id === selectedId) || null;

  return (
    <div ref={containerRef} className={styles.container}
         onWheel={onWheel} onMouseMove={onMouseMove} onMouseUp={onMouseUp}
         style={{ cursor: isPanning ? 'grabbing' : 'default' }}>
      <div className={styles.surface} data-canvas-surface
           style={{ transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`, width: 1, height: 1 }}
           onMouseDown={handleSurfaceMouseDown}
           onDoubleClick={handleDoubleClick}>
        <ConnectionLayer entries={entries} links={crossLinks} onDeleteLink={props.onDeleteCrossLink} />
        {entries.map((entry) => (
          <CardNode key={entry.id} entry={entry} scale={scale} selected={entry.id === selectedId}
            onSelect={handleCardSelect} onDragEnd={props.onDragEnd} onResizeEnd={props.onResizeEnd}
            onStartConnect={handleStartConnect} />
        ))}
        {selected && (
          <CardEditor entry={selected} layers={layers}
            onSave={(patch) => props.onSave(selected.id, patch)} onDelete={props.onDelete}
            onClose={() => props.onSelect(null)} onConfirm={props.onConfirm} onIgnore={props.onIgnore} />
        )}
      </div>
    </div>
  );
}
