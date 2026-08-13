import styles from './AmbientLight.module.css'

export default function AmbientLight() {
  return (
    <div className={styles.layer} aria-hidden="true">
      <div className={styles.orb1} />
      <div className={styles.orb2} />
      <div className={styles.orb3} />
      <div className={styles.orb4} />
      <div className={styles.orb5} />
      <div className={styles.orb6} />
    </div>
  )
}
