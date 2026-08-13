import styles from './StatusLights.module.css'

const INDICATORS = [
  { label: '匹配引擎', status: 'online' as const },
  { label: '智能教师', status: 'soon' as const },
  { label: '行动树', status: 'soon' as const },
  { label: '自编辑', status: 'soon' as const },
]

export default function StatusLights() {
  return (
    <div className={styles.strip} aria-hidden="true">
      {INDICATORS.map((item) => (
        <div key={item.label} className={styles.row}>
          <span className={`${styles.dot} ${styles[`dot_${item.status}`]}`} />
          <span className={styles.label}>{item.label}</span>
        </div>
      ))}
    </div>
  )
}
