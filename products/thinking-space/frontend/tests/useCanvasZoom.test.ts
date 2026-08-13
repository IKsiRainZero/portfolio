import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useCanvasZoom } from '../src/hooks/useCanvasZoom';

describe('useCanvasZoom', () => {
  it('screenToCanvas inverts translate+scale', () => {
    const { result } = renderHook(() => useCanvasZoom(1, 0.1, 3));
    const rect = { left: 0, top: 0 } as DOMRect;
    // position {0,0}, scale 1 → identity
    expect(result.current.screenToCanvas(50, 60, rect)).toEqual({ x: 50, y: 60 });
  });

  it('clamps scale within [min,max]', () => {
    const { result } = renderHook(() => useCanvasZoom(3, 0.1, 3));
    act(() => result.current.onWheel({ deltaY: -1, clientX: 0, clientY: 0, preventDefault() {}, currentTarget: { getBoundingClientRect: () => ({ left: 0, top: 0 }) } } as any));
    expect(result.current.scale).toBeLessThanOrEqual(3);
  });
});
