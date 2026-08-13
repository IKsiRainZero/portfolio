import type { MockProfile } from '../../data/mockContent'
import styles from './ProfileBlock.module.css'

interface Props {
  data: Record<string, unknown>
  state: string
}

const CAT_COLORS: Record<string, string> = {
  language: styles.catLang,
  framework: styles.catFw,
  tool: styles.catTool,
  soft: styles.catSoft,
}
const CAT_LABELS: Record<string, string> = {
  language: '语言',
  framework: '框架',
  tool: '工具',
  soft: '软技能',
}

export default function ProfileBlock({ data, state }: Props) {
  const p = data as unknown as MockProfile
  const skills = p.skills || []
  const confirmed = state === 'CONFIRMED'

  return (
    <section className={`${styles.block} ${confirmed ? styles.confirmed : ''}`}>
      <header className={styles.header}>
        <h2 className={styles.title}>能力画像</h2>
        {confirmed && <span className={styles.badge}>已确认</span>}
        {state === 'READY_FOR_REVIEW' && <span className={`${styles.badge} ${styles.badgePending}`}>待确认</span>}
        {state === 'EMPTY' && <span className={`${styles.badge} ${styles.badgeEmpty}`}>等待数据</span>}
      </header>

      {p.summary && (
        <p className={styles.summary}>{p.summary}</p>
      )}

      <div className={styles.meta}>
        <span className={styles.metaItem}>
          <span className={styles.metaLabel}>完整度</span>
          <span className={styles.metaVal}>{p.completeness || 0}%</span>
        </span>
        <span className={styles.metaItem}>
          <span className={styles.metaLabel}>经验</span>
          <span className={styles.metaVal}>{p.experience || '—'}</span>
        </span>
      </div>

      {skills.length > 0 && (
        <div className={styles.tags}>
          {skills.map((s: MockProfile['skills'][number], i: number) => (
            <span key={i} className={`${styles.tag} ${CAT_COLORS[s.category] || ''}`}>
              <span className={styles.tagCat}>{CAT_LABELS[s.category] || s.category}</span>
              {s.name}
            </span>
          ))}
        </div>
      )}

      {!p.summary && (
        <div className={styles.empty}>输入你的技能和经历，系统将生成能力画像</div>
      )}
    </section>
  )
}
