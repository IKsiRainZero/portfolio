import styles from './GlowBar.module.css'

export default function GlowBar() {
  return (
    <div className={styles.container} aria-hidden="true">
      <div className={styles.line} />
      <div className={styles.glow} />
      <div className={styles.glow2} />
    </div>
  )
}
