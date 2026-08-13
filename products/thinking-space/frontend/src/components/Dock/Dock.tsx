import { motion, AnimatePresence } from 'framer-motion';
import { useDockAutoHide } from '../../hooks/useDockAutoHide';
import styles from './Dock.module.css';

interface Props {
  onAdd: () => void;
  onScan: () => void;
  onToggleView: () => void;
  view: 'canvas' | 'chains';
}

export default function Dock({ onAdd, onScan, onToggleView, view }: Props) {
  const { visible, show, hide } = useDockAutoHide(2000);
  return (
    <div className={styles.dockArea} onMouseEnter={show} onMouseLeave={hide}>
      <AnimatePresence>
        {visible && (
          <motion.div className={styles.dock}
            initial={{ y: 80, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 80, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}>
            <button className={styles.action} title="切换视图" onClick={onToggleView}>
              {view === 'canvas' ? '层级' : '画布'}
            </button>
            <div className={styles.divider} />
            <button className={styles.action} title="扫描知识库" onClick={onScan}>&#8631;</button>
            <button className={styles.action} title="添加条目" onClick={onAdd}>+</button>
          </motion.div>
        )}
      </AnimatePresence>
      {!visible && <div className={styles.handle} />}
    </div>
  );
}
