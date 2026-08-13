import { useState, useCallback, WheelEvent } from 'react';

export function useCanvasZoom(initialScale = 1, min = 0.1, max = 3) {
  const [scale, setScale] = useState(initialScale);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  const onWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    setScale((s) => {
      const factor = e.deltaY > 0 ? 0.9 : 1.1;
      const next = Math.min(max, Math.max(min, s * factor));
      setPosition((p) => ({
        x: mx - (mx - p.x) * (next / s),
        y: my - (my - p.y) * (next / s),
      }));
      return next;
    });
  }, [min, max]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) {
      e.preventDefault();
      setIsPanning(true);
      setPanStart({ x: e.clientX - position.x, y: e.clientY - position.y });
    }
  }, [position]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return;
    setPosition({ x: e.clientX - panStart.x, y: e.clientY - panStart.y });
  }, [isPanning, panStart]);

  const onMouseUp = useCallback(() => setIsPanning(false), []);

  const screenToCanvas = useCallback((clientX: number, clientY: number, rect: { left: number; top: number }) => ({
    x: (clientX - rect.left - position.x) / scale,
    y: (clientY - rect.top - position.y) / scale,
  }), [position, scale]);

  return { scale, position, isPanning, onWheel, onMouseDown, onMouseMove, onMouseUp, screenToCanvas };
}
