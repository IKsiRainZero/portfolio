import type { MockAction } from '../../data/mockContent'
import styles from './ActionBlock.module.css'

interface Props {
  data: Record<string, unknown>
  state: string
}

export default function ActionBlock({ data, state }: Props) {
  const d = data as { actions?: MockAction[] } & Record<string, unknown>
  const actions = d.actions || []
  const confirmed = state === 'CONFIRMED'

  return (
    <section className={`${styles.block} ${confirmed ? styles.confirmed : ''}`}>
      <header className={styles.header}>
        <h2 className={styles.title}>下一步行动</h2>
        {confirmed && <span className={styles.badge}>已确认</span>}
        {state === 'READY_FOR_REVIEW' && <span className={`${styles.badge} ${styles.badgePending}`}>待确认</span>}
        {state === 'EMPTY' && <span className={`${styles.badge} ${styles.badgeEmpty}`}>等待数据</span>}
      </header>

      {actions.length > 0 ? (
        <div className={styles.list}>
          {actions.map((a: MockAction, i: number) => (
            <div key={i} className={`${styles.item} ${styles[`prio_${a.priority}`] || ''}`}>
              <span className={styles.checkbox + (a.done ? ' ' + styles.checked : '')} />
              <span className={styles.text}>{a.text}</span>
              <span className={styles.time}>{a.estTime}</span>
              <span className={`${styles.prio} ${styles[`prioTag_${a.priority}`] || ''}`}>
                {a.priority === 'high' ? '优先' : a.priority === 'medium' ? '推荐' : '可选'}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className={styles.empty}>确认学习路径后，系统将生成具体的行动清单</div>
      )}
    </section>
  )
}
