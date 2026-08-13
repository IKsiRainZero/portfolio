import type { MockGapItem } from '../../data/mockContent'
import styles from './GapBlock.module.css'

interface Props {
  data: Record<string, unknown>
  state: string
}

const DIFF_LABELS: Record<string, string> = {
  easy: '入门',
  moderate: '中等',
  hard: '进阶',
}

export default function GapBlock({ data, state }: Props) {
  const d = data as { mustLearn?: MockGapItem[]; recommend?: MockGapItem[] } & Record<string, unknown>
  const mustLearn = d.mustLearn || []
  const recommend = d.recommend || []
  const confirmed = state === 'CONFIRMED'

  return (
    <section className={`${styles.block} ${confirmed ? styles.confirmed : ''}`}>
      <header className={styles.header}>
        <h2 className={styles.title}>差距分析</h2>
        {confirmed && <span className={styles.badge}>已确认</span>}
        {state === 'READY_FOR_REVIEW' && <span className={`${styles.badge} ${styles.badgePending}`}>待确认</span>}
        {state === 'EMPTY' && <span className={`${styles.badge} ${styles.badgeEmpty}`}>等待数据</span>}
      </header>

      {mustLearn.length > 0 || recommend.length > 0 ? (
        <div className={styles.columns}>
          <div className={styles.col}>
            <h3 className={styles.colTitle + ' ' + styles.colMust}>必须掌握</h3>
            {mustLearn.map((item: MockGapItem, i: number) => (
              <div key={i} className={`${styles.item} ${styles[`prio_${item.priority}`] || ''}`}>
                <div className={styles.itemHead}>
                  <span className={styles.itemName}>{item.skill}</span>
                  <span className={styles.itemDiff}>{DIFF_LABELS[item.difficulty] || item.difficulty}</span>
                </div>
                <p className={styles.itemReason}>{item.reason}</p>
                <span className={styles.itemHours}>约 {item.estHours}h</span>
              </div>
            ))}
          </div>
          <div className={styles.col}>
            <h3 className={styles.colTitle + ' ' + styles.colRec}>建议学习</h3>
            {recommend.map((item: MockGapItem, i: number) => (
              <div key={i} className={`${styles.item} ${styles[`prio_${item.priority}`] || ''}`}>
                <div className={styles.itemHead}>
                  <span className={styles.itemName}>{item.skill}</span>
                  <span className={styles.itemDiff}>{DIFF_LABELS[item.difficulty] || item.difficulty}</span>
                </div>
                <p className={styles.itemReason}>{item.reason}</p>
                <span className={styles.itemHours}>约 {item.estHours}h</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className={styles.empty}>完成能力画像和方向匹配后，系统将分析你的技能差距</div>
      )}
    </section>
  )
}
