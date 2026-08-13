import styles from './Header.module.css';

interface Props {
  onRefresh: () => void;
  loading: boolean;
}

export default function Header({ onRefresh, loading }: Props) {
  return (
    <header className={styles.header}>
      <h1 className={styles.title}>Console</h1>
      <div className={styles.actions}>
        {loading && <span className={styles.spinner}>&#x27F3;</span>}
        <button className={styles.btn} onClick={onRefresh} disabled={loading}>
          Refresh
        </button>
      </div>
    </header>
  );
}
