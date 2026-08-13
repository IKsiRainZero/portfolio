import { useMemo } from 'react'
import { motion } from 'framer-motion'
import GapBlock from '../blocks/GapBlock'
import PathBlock from '../blocks/PathBlock'
import { getMockPayload } from '../../data/mockContent'
import styles from './PlanPage.module.css'

interface Props {
  panelStates: Record<string, string>
  panelPayloads: Record<string, Record<string, unknown>>
  hasSession: boolean
  onConfirm: (pid: string) => void
}

const sectionVariants = {
  initial: { y: 24, opacity: 0 },
  animate: { y: 0, opacity: 1, transition: { duration: 0.5, ease: 'easeOut' as const } },
}

export default function PlanPage({
  panelStates, panelPayloads, hasSession, onConfirm,
}: Props) {
  const gapState = panelStates.gap || 'EMPTY'
  const pathState = panelStates.path || 'EMPTY'

  const gapData = hasSession ? panelPayloads.gap : getMockPayload('gap')
  const pathData = hasSession ? panelPayloads.path : getMockPayload('path')

  const gapCount = useMemo(() => {
    const d = gapData as { mustLearn?: unknown[]; recommend?: unknown[] }
    return (d.mustLearn?.length || 0) + (d.recommend?.length || 0)
  }, [gapData])

  const narratorText = gapCount > 0
    ? `分析完成，共发现 ${gapCount} 项技能差距。基于这些差距，系统生成了分阶段的学习路径，帮助你逐步补齐所需能力。`
    : '确认职业方向后，系统将分析你的技能差距并生成学习路径。'

  return (
    <div className={styles.page}>
      {/* Gap section */}
      <motion.div variants={sectionVariants} initial="initial" animate="animate">
        <GapBlock data={gapData} state={gapState} />
      </motion.div>

      {/* Legend */}
      <div className={styles.legend}>
        <span className={styles.legendItem}><span className={`${styles.legendSwatch} ${styles.swatchMust}`} />必须</span>
        <span className={styles.legendItem}><span className={`${styles.legendSwatch} ${styles.swatchRec}`} />建议</span>
        <span className={styles.legendItem}><span className={`${styles.legendSwatch} ${styles.swatchOpt}`} />可选</span>
      </div>

      {/* Narrator */}
      <motion.div
        className={styles.narrator}
        variants={sectionVariants}
        initial="initial"
        animate="animate"
        transition={{ delay: 0.2 }}
      >
        <span className={styles.narratorIcon}>&#9670;</span>
        <p className={styles.narratorText}>{narratorText}</p>
      </motion.div>

      {/* Path section */}
      <motion.div variants={sectionVariants} initial="initial" animate="animate" transition={{ delay: 0.4 }}>
        <header style={{ display: 'flex', alignItems: 'center', gap: 'var(--cr-space-sm)', marginBottom: 'var(--cr-space-lg)' }}>
          <h2 style={{ fontSize: 22, fontWeight: 600, color: 'var(--cr-text1)', letterSpacing: '-0.02em' }}>学习路径</h2>
          {pathState === 'CONFIRMED' && (
            <span className={styles.stateBadge} style={{ background: 'var(--cr-green-soft)', color: 'var(--cr-green)' }}>已确认</span>
          )}
          {pathState === 'READY_FOR_REVIEW' && (
            <span className={styles.stateBadge} style={{ background: 'var(--cr-accent-soft)', color: 'var(--cr-accent)' }}>待确认</span>
          )}
        </header>
        <PathBlock data={pathData} state={pathState} />
      </motion.div>

      {/* Confirm bar */}
      <div className={styles.confirmBar}>
        <button
          type="button"
          className={styles.confirmBtn}
          disabled={pathState === 'CONFIRMED'}
          onClick={() => onConfirm('path')}
        >
          {pathState === 'CONFIRMED' ? '已确认' : '确认学习路径'}
        </button>
      </div>
    </div>
  )
}
