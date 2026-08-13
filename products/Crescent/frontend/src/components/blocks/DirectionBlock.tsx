import type { MockDirection } from '../../data/mockContent'
import styles from './DirectionBlock.module.css'

interface Props {
  data: Record<string, unknown>
  state: string
}

const OUTLOOK_LABELS: Record<string, string> = {
  growing: '增长中',
  stable: '稳定',
  declining: '下降',
}

export default function DirectionBlock({ data, state }: Props) {
  const d = data as { directions?: MockDirection[] } & Record<string, unknown>
  const directions = d.directions || []
  const confirmed = state === 'CONFIRMED'

  return (
    <section className={`${styles.block} ${confirmed ? styles.confirmed : ''}`}>
      <header className={styles.header}>
        <h2 className={styles.title}>匹配方向</h2>
        {confirmed && <span className={styles.badge}>已确认</span>}
        {state === 'READY_FOR_REVIEW' && <span className={`${styles.badge} ${styles.badgePending}`}>待确认</span>}
        {state === 'EMPTY' && <span className={`${styles.badge} ${styles.badgeEmpty}`}>等待数据</span>}
      </header>

      {directions.length > 0 ? (
        <div className={styles.grid}>
          {directions.map((dir: MockDirection, i: number) => (
            <div key={i} className={styles.card}>
              <div className={styles.cardTop}>
                <h3 className={styles.dirName}>{dir.name}</h3>
                <span className={`${styles.score} ${dir.matchScore >= 80 ? styles.scoreHigh : dir.matchScore >= 65 ? styles.scoreMid : styles.scoreLow}`}>
                  {dir.matchScore}% 匹配
                </span>
              </div>
              <p className={styles.reason}>{dir.reason}</p>
              <div className={styles.lists}>
                <div className={styles.listCol}>
                  <span className={styles.listLabel}>重叠技能</span>
                  {dir.overlaps.map((s: string, j: number) => (
                    <span key={j} className={styles.skillTag + ' ' + styles.overlap}>{s}</span>
                  ))}
                </div>
                <div className={styles.listCol}>
                  <span className={styles.listLabel}>需要学习</span>
                  {dir.gaps.map((s: string, j: number) => (
                    <span key={j} className={styles.skillTag + ' ' + styles.gap}>{s}</span>
                  ))}
                </div>
              </div>
              <span className={`${styles.outlook} ${styles[`outlook_${dir.outlook}`] || ''}`}>
                {OUTLOOK_LABELS[dir.outlook] || dir.outlook}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className={styles.empty}>完成能力画像后，系统将匹配适合你的产业方向</div>
      )}
    </section>
  )
}
