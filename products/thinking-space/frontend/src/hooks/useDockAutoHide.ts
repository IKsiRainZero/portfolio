import { useState, useRef, useCallback, useEffect } from 'react';

export function useDockAutoHide(delay = 2000) {
  const [visible, setVisible] = useState(true);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  const show = useCallback(() => {
    clearTimeout(timer.current);
    setVisible(true);
  }, []);

  const hide = useCallback(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setVisible(false), delay);
  }, [delay]);

  useEffect(() => () => clearTimeout(timer.current), []);

  return { visible, show, hide };
}
