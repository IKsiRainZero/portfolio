import type { Layer, Entry } from '../../types';
import styles from './TagPool.module.css';

interface Props { layers: Layer[]; entries: Entry[]; }

export default function TagPool({ layers, entries }: Props) {
  const count = (layerId: string) => entries.filter((e) => (e.tag_ids || []).includes(layerId)).length;
  return (
    <div className={styles.pool}>
      {layers.map((l) => {
        const c = count(l.id);
        return (
          <div key={l.id} className={`${styles.item} ${c === 0 ? styles.empty : ''}`} data-empty={c === 0}>
            <span>{l.name}</span>
            <span className={styles.count}>{c}</span>
          </div>
        );
      })}
    </div>
  );
}
