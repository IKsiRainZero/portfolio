import { useState, useCallback, type ReactNode } from 'react';
import styles from './SplitPane.module.css';

interface Props {
  left: ReactNode;
  right: ReactNode;
  defaultRatio?: number;
}

export default function SplitPane({ left, right, defaultRatio = 0.6 }: Props) {
  const [ratio, setRatio] = useState(defaultRatio);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startRatio = ratio;
    const onMove = (ev: MouseEvent) => {
      const dx = ev.clientX - startX;
      const containerWidth = (e.target as HTMLElement).parentElement?.clientWidth ?? window.innerWidth;
      const newRatio = Math.min(0.8, Math.max(0.2, startRatio + dx / containerWidth));
      setRatio(newRatio);
    };
    const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [ratio]);

  return (
    <div className={styles.container}>
      <div className={styles.left} style={{ width: `${ratio * 100}%` }}>{left}</div>
      <div className={styles.divider} onMouseDown={onMouseDown} />
      <div className={styles.right} style={{ width: `${(1 - ratio) * 100}%` }}>{right}</div>
    </div>
  );
}
