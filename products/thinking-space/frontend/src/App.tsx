import { useState, useEffect, useCallback } from 'react';
import Canvas from './components/Canvas/Canvas';
import TagPool from './components/Canvas/TagPool';
import Dock from './components/Dock/Dock';
import ChainEditorView from './components/ChainEditor/ChainEditorView';
import { useUndoRedo, CardOp } from './hooks/useUndoRedo';
import {
  fetchDimensions, fetchEntries, createEntry, updateEntry, deleteEntry, updateGeometry,
  confirmEntry, ignoreEntry, triggerIndexScan, createCrossLink, deleteCrossLink,
  fetchLayerLinks, createLayerLink, deleteLayerLink,
  createDimension, updateDimension, deleteDimension,
  createLayer, updateLayer, deleteLayer, reorderLayers,
} from './api/client';
import type { Dimension, Entry, LayerLink } from './types';

export default function App() {
  const [dimensions, setDimensions] = useState<Dimension[]>([]);
  const [activeId, setActiveId] = useState<string>('');
  const [entries, setEntries] = useState<Entry[]>([]);
  const [crossLinks, setCrossLinks] = useState<{ id: string; source_entry_id: string; target_entry_id: string }[]>([]);
  const [layerLinks, setLayerLinks] = useState<LayerLink[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<'canvas' | 'chains'>('canvas');
  const undoRedo = useUndoRedo();

  const active = dimensions.find((d) => d.id === activeId) || null;
  const layers = active?.layers || [];

  const loadDimensions = useCallback(async () => {
    const dims = await fetchDimensions();
    setDimensions(dims);
    if (dims.length > 0 && !dims.find((d) => d.id === activeId)) setActiveId(dims[0].id);
  }, [activeId]);

  const loadEntries = useCallback(async (dimId: string) => {
    setEntries(await fetchEntries({ dimension_id: dimId }));
  }, []);

  const loadLayerLinks = useCallback(async (dimId: string) => {
    setLayerLinks(await fetchLayerLinks(dimId));
  }, []);

  useEffect(() => { loadDimensions().catch(console.error); }, [loadDimensions]);
  useEffect(() => {
    if (!activeId) return;
    loadEntries(activeId).catch(console.error);
    loadLayerLinks(activeId).catch(console.error);
  }, [activeId, loadEntries, loadLayerLinks]);

  // ---- card ops ----
  const applyOp = useCallback(async (op: CardOp, inverse: boolean) => {
    const kind = op.kind;
    if ((kind === 'create' && !inverse) || (kind === 'delete' && inverse)) {
      const e = (op as any).entry as Entry;
      const created = await createEntry(e).catch(console.error);
      if (created) {
        setEntries((prev) => [...prev, created]);
        (op as any).entry = created;
      }
    } else if ((kind === 'delete' && !inverse) || (kind === 'create' && inverse)) {
      const e = (op as any).entry as Entry;
      setEntries((prev) => prev.filter((x) => x.id !== e.id));
      await deleteEntry(e.id).catch(console.error);
    } else if (kind === 'update') {
      const target = inverse ? op.before : op.after;
      setEntries((prev) => prev.map((x) => (x.id === target.id ? target : x)));
      await updateEntry(target.id, target).catch(console.error);
    } else if (kind === 'geometry') {
      const target = inverse ? op.before : op.after;
      setEntries((prev) => prev.map((x) => (x.id === target.id ? target : x)));
      await updateGeometry(target.id, { x: target.x, y: target.y, width: target.width, height: target.height, z_depth: target.z_depth }).catch(console.error);
    } else if (kind === 'connect') {
      if (inverse) {
        setCrossLinks((prev) => prev.filter((l) => l.id !== op.link.id));
        await deleteCrossLink(op.link.id).catch(console.error);
      } else {
        const link = await createCrossLink({ source_entry_id: op.link.source_entry_id, target_entry_id: op.link.target_entry_id }).catch(console.error);
        if (link) {
          setCrossLinks((prev) => [...prev, { id: link.id, source_entry_id: op.link.source_entry_id, target_entry_id: op.link.target_entry_id }]);
          (op as any).link = link;
        }
      }
    }
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !e.shiftKey) {
        e.preventDefault();
        const op = undoRedo.undo();
        if (op) applyOp(op, true);
      } else if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'y' || (e.shiftKey && e.key.toLowerCase() === 'z'))) {
        e.preventDefault();
        const op = undoRedo.redo();
        if (op) applyOp(op, false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [undoRedo, applyOp]);

  const handleCreateAt = async (x: number, y: number) => {
    if (!active) return;
    const created = await createEntry({ title: '新想法', dimension_id: active.id, x, y } as Partial<Entry>);
    setEntries((prev) => [...prev, created]);
    undoRedo.record({ kind: 'create', entry: created });
    setSelectedId(created.id);
  };

  const flushGeom = useCallback((id: string, geo: Partial<Entry>) => {
    updateGeometry(id, geo).catch(console.error);
  }, []);

  const handleDragEnd = (id: string, x: number, y: number) => {
    const before = entries.find((e) => e.id === id);
    if (!before) return;
    const after = { ...before, x, y };
    setEntries((prev) => prev.map((e) => (e.id === id ? after : e)));
    flushGeom(id, { x, y });
    undoRedo.record({ kind: 'geometry', before, after });
  };
  const handleResizeEnd = (id: string, width: number, height: number) => {
    const before = entries.find((e) => e.id === id);
    if (!before) return;
    const after = { ...before, width, height };
    setEntries((prev) => prev.map((e) => (e.id === id ? after : e)));
    flushGeom(id, { width, height });
    undoRedo.record({ kind: 'geometry', before, after });
  };

  const handleSave = async (id: string, patch: Partial<Entry>) => {
    const before = entries.find((e) => e.id === id);
    const updated = await updateEntry(id, patch);
    setEntries((prev) => prev.map((e) => (e.id === id ? updated : e)));
    if (before) undoRedo.record({ kind: 'update', before, after: updated });
  };

  const handleDelete = async (id: string) => {
    const before = entries.find((e) => e.id === id);
    await deleteEntry(id);
    setEntries((prev) => prev.filter((e) => e.id !== id));
    setSelectedId(null);
    if (before) undoRedo.record({ kind: 'delete', entry: before });
  };

  const handleConnect = async (sourceId: string, targetId: string) => {
    const link = await createCrossLink({ source_entry_id: sourceId, target_entry_id: targetId });
    setCrossLinks((prev) => [...prev, { id: link.id, source_entry_id: sourceId, target_entry_id: targetId }]);
    undoRedo.record({
      kind: 'connect',
      link: { id: link.id, source_entry_id: sourceId, target_entry_id: targetId },
    });
  };
  const handleDeleteCrossLink = async (id: string) => {
    await deleteCrossLink(id);
    setCrossLinks((prev) => prev.filter((l) => l.id !== id));
  };

  const handleConfirm = async (id: string) => { const u = await confirmEntry(id); setEntries((p) => p.map((e) => e.id === id ? u : e)); };
  const handleIgnore = async (id: string) => { const u = await ignoreEntry(id); setEntries((p) => p.map((e) => e.id === id ? u : e)); };
  const handleScan = async () => { await triggerIndexScan(); if (activeId) loadEntries(activeId); };

  // ---- chain editor ops ----
  const handleCreateChain = async (name: string) => { const d = await createDimension({ name }); await loadDimensions(); setActiveId(d.id); };
  const handleRenameChain = async (id: string, name: string) => { await updateDimension(id, { name }); loadDimensions(); };
  const handleDeleteChain = async (id: string) => { await deleteDimension(id); await loadDimensions(); };
  const handleCreateLayer = async (name: string) => { await createLayer(activeId, { name }); loadDimensions(); };
  const handleRenameLayer = async (id: string, name: string) => { await updateLayer(id, { name }); loadDimensions(); };
  const handleUpdateLayerDesc = async (id: string, description: string) => { await updateLayer(id, { description }); loadDimensions(); };
  const handleDeleteLayer = async (id: string) => { await deleteLayer(id); loadDimensions(); };
  const handleReorderLayers = async (ids: string[]) => { await reorderLayers(activeId, ids); loadDimensions(); };
  const handleCreateLayerLink = async (s: string, t: string) => { const k = await createLayerLink({ source_layer_id: s, target_layer_id: t }); setLayerLinks((p) => [...p, k]); };
  const handleDeleteLayerLink = async (id: string) => { await deleteLayerLink(id); setLayerLinks((p) => p.filter((l) => l.id !== id)); };

  if (view === 'chains') {
    return (
      <>
        <ChainEditorView
          dimensions={dimensions} activeId={activeId} layers={layers} layerLinks={layerLinks}
          onSelectChain={setActiveId} onCreateChain={handleCreateChain} onRenameChain={handleRenameChain}
          onDeleteChain={handleDeleteChain} onCreateLayer={handleCreateLayer} onRenameLayer={handleRenameLayer}
          onUpdateLayerDesc={handleUpdateLayerDesc} onDeleteLayer={handleDeleteLayer}
          onReorderLayers={handleReorderLayers} onCreateLayerLink={handleCreateLayerLink}
          onDeleteLayerLink={handleDeleteLayerLink} />
        <Dock onAdd={handleCreateAtCenter} onScan={handleScan} onToggleView={() => setView('canvas')} view="chains" />
      </>
    );
  }

  function handleCreateAtCenter() { handleCreateAt(200, 200); }

  return (
    <>
      <Canvas
        entries={entries} layers={layers} crossLinks={crossLinks} selectedId={selectedId}
        onSelect={setSelectedId} onDragEnd={handleDragEnd} onResizeEnd={handleResizeEnd}
        onCreateAt={handleCreateAt} onSave={handleSave} onDelete={handleDelete}
        onConnect={handleConnect} onDeleteCrossLink={handleDeleteCrossLink}
        onConfirm={handleConfirm} onIgnore={handleIgnore} />
      <TagPool layers={layers} entries={entries} />
      <Dock onAdd={handleCreateAtCenter} onScan={handleScan} onToggleView={() => setView('chains')} view="canvas" />
    </>
  );
}
