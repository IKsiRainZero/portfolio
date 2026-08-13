import type { MockPhase } from '../../data/mockContent'
import styles from './PathBlock.module.css'

interface Props {
  data: Record<string, unknown>
  state: string
}

export default function PathBlock({ data, state }: Props) {
  const d = data as { phases?: MockPhase[] } & Record<string, unknown>
  const phases = d.phases || []
  const confirmed = state === 'CONFIRMED'

  return (
    <section className={`${styles.block} ${confirmed ? styles.confirmed : ''}`}>
      <header className={styles.header}>
        <h2 className={styles.title}>学习路径</h2>
        {confirmed && <span className={styles.badge}>已确认</span>}
        {state === 'READY_FOR_REVIEW' && <span className={`${styles.badge} ${styles.badgePending}`}>待确认</span>}
        {state === 'EMPTY' && <span className={`${styles.badge} ${styles.badgeEmpty}`}>等待数据</span>}
      </header>

      {phases.length > 0 ? (
        <div className={styles.timeline}>
          {phases.map((phase: MockPhase, i: number) => (
            <div key={i} className={styles.phase}>
              <div className={styles.phaseMarker}>
                <span className={styles.phaseNum}>{i + 1}</span>
                {i < phases.length - 1 && <div className={styles.phaseLine} />}
              </div>
              <div className={styles.phaseBody}>
                <div className={styles.phaseHead}>
                  <h3 className={styles.phaseTitle}>{phase.title}</h3>
                  <span className={styles.phaseMeta}>{phase.duration} · {phase.difficulty}</span>
                </div>
                <div className={styles.modules}>
                  {phase.modules.map((m: string, j: number) => (
                    <span key={j} className={styles.module}>{m}</span>
                  ))}
                </div>
                <p className={styles.phaseOutcome}>
                  <span className={styles.outcomeLabel}>目标：</span>{phase.outcome}
                </p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className={styles.empty}>确认方向匹配后，系统将生成个性化学习路径</div>
      )}
    </section>
  )
}
