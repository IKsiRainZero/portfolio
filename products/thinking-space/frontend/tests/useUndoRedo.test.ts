import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useUndoRedo } from '../src/hooks/useUndoRedo';

const entry = (id: string) => ({ id, title: id } as any);

describe('useUndoRedo', () => {
  it('records and undoes in LIFO order', () => {
    const { result } = renderHook(() => useUndoRedo());
    act(() => result.current.record({ kind: 'create', entry: entry('a') }));
    act(() => result.current.record({ kind: 'create', entry: entry('b') }));
    expect(result.current.canUndo).toBe(true);
    let op: any;
    act(() => { op = result.current.undo(); });
    expect(op.entry.id).toBe('b');
  });

  it('redo returns last undone op', () => {
    const { result } = renderHook(() => useUndoRedo());
    act(() => result.current.record({ kind: 'create', entry: entry('a') }));
    act(() => { result.current.undo(); });
    let op: any;
    act(() => { op = result.current.redo(); });
    expect(op.entry.id).toBe('a');
    expect(result.current.canRedo).toBe(false);
  });

  it('record clears redo stack', () => {
    const { result } = renderHook(() => useUndoRedo());
    act(() => result.current.record({ kind: 'create', entry: entry('a') }));
    act(() => { result.current.undo(); });
    act(() => result.current.record({ kind: 'create', entry: entry('c') }));
    expect(result.current.canRedo).toBe(false);
  });

  it('records geometry op and undoes it (LIFO)', () => {
    const { result } = renderHook(() => useUndoRedo());
    const e = entry('g');
    act(() => result.current.record({ kind: 'geometry', before: e, after: { ...e, x: 50, y: 60 } }));
    expect(result.current.canUndo).toBe(true);
    let op: any;
    act(() => { op = result.current.undo(); });
    expect(op.kind).toBe('geometry');
  });
});
