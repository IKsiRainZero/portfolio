import { useState } from 'react';
import type { Entry } from '../types';

export type CardOp =
  | { kind: 'create'; entry: Entry }
  | { kind: 'delete'; entry: Entry }
  | { kind: 'update'; before: Entry; after: Entry }
  | { kind: 'geometry'; before: Entry; after: Entry }
  | { kind: 'connect'; link: { id: string; source_entry_id: string; target_entry_id: string } };

export function useUndoRedo() {
  const [past, setPast] = useState<CardOp[]>([]);
  const [future, setFuture] = useState<CardOp[]>([]);

  const record = (op: CardOp) => {
    setPast((p) => [...p, op]);
    setFuture([]);
  };

  const undo = (): CardOp | null => {
    if (past.length === 0) return null;
    const popped = past[past.length - 1];
    setPast((p) => p.slice(0, -1));
    setFuture((f) => [...f, popped]);
    return popped;
  };

  const redo = (): CardOp | null => {
    if (future.length === 0) return null;
    const popped = future[future.length - 1];
    setFuture((f) => f.slice(0, -1));
    setPast((p) => [...p, popped]);
    return popped;
  };

  return { record, undo, redo, canUndo: past.length > 0, canRedo: future.length > 0 };
}
