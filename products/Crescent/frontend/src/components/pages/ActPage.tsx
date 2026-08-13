import { useState, useMemo, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { MockAction } from '../../data/mockContent'
import { getMockPayload } from '../../data/mockContent'
import styles from './ActPage.module.css'

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

const checkboxVariants = {
  unchecked: { scale: 1 },
  checked: { scale: [1, 1.25, 1], transition: { duration: 0.25, ease: 'easeOut' as const } },
}

export default function ActPage({
  panelStates, panelPayloads, hasSession, onConfirm,
}: Props) {
  const actionState = panelStates.action || 'EMPTY'
  const rawData = hasSession ? panelPayloads.action : getMockPayload('action')
  const sourceActions = (rawData as { actions?: MockAction[] }).actions || []

  // Local checkbox state initialized from data
  const [doneMap, setDoneMap] = useState<Record<number, boolean>>(() => {
    const init: Record<number, boolean> = {}
    sourceActions.forEach((a, i) => { init[i] = a.done || false })
    return init
  })

  const toggle = useCallback((i: number) => {
    setDoneMap((prev) => ({ ...prev, [i]: !prev[i] }))
  }, [])

  const doneCount = useMemo(() => Object.values(doneMap).filter(Boolean).length, [doneMap])
  const total = sourceActions.length
  const allDone = total > 0 && doneCount === total
  const progressPct = total > 0 ? Math.round((doneCount / total) * 100) : 0

  // Merge local state into the data ActionBlock receives
  const mergedData = useMemo(() => ({
    ...rawData,
    actions: sourceActions.map((a, i) => ({ ...a, done: doneMap[i] })),
  }), [rawData, sourceActions, doneMap])

  return (
    <div className={styles.page}>
      {/* Progress bar */}
      <motion.div variants={sectionVariants} initial="initial" animate="animate">
        <div className={styles.progressHeader}>
          <span className={styles.progressLabel}>完成进度</span>
          <span className={styles.progressPct}>{progressPct}%</span>
        </div>
        <div className={styles.progressTrack}>
          <motion.div
            className={styles.progressFill}
            initial={{ width: 0 }}
            animate={{ width: `${progressPct}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' as const }}
          />
        </div>
      </motion.div>

      {/* Action list with animated checkboxes */}
      <motion.div variants={sectionVariants} initial="initial" animate="animate" transition={{ delay: 0.15 }}>
        <header style={{ display: 'flex', alignItems: 'center', gap: 'var(--cr-space-sm)', marginBottom: 'var(--cr-space-lg)' }}>
          <h2 style={{ fontSize: 22, fontWeight: 600, color: 'var(--cr-text1)', letterSpacing: '-0.02em' }}>下一步行动</h2>
          {actionState === 'CONFIRMED' && (
            <span className={styles.stateBadge} style={{ background: 'var(--cr-green-soft)', color: 'var(--cr-green)' }}>已确认</span>
          )}
          {actionState === 'READY_FOR_REVIEW' && (
            <span className={styles.stateBadge} style={{ background: 'var(--cr-accent-soft)', color: 'var(--cr-accent)' }}>待确认</span>
          )}
        </header>

        <div className={styles.actionList}>
          {sourceActions.map((a, i) => {
            const done = doneMap[i]
            return (
              <motion.div
                key={i}
                className={`${styles.actionItem} ${done ? styles.actionItemDone : ''}`}
                whileHover={{ scale: 1.01 }}
                onClick={() => toggle(i)}
              >
                <motion.span
                  className={`${styles.checkbox} ${done ? styles.checkboxDone : ''}`}
                  variants={checkboxVariants}
                  animate={done ? 'checked' : 'unchecked'}
                >
                  {done ? '✓' : ''}
                </motion.span>
                <span className={`${styles.actionText} ${done ? styles.actionTextDone : ''}`}>{a.text}</span>
                <span className={styles.actionTime}>{a.estTime}</span>
                <span className={`${styles.actionPrio} ${styles[`prio_${a.priority}`] || ''}`}>
                  {a.priority === 'high' ? '优先' : a.priority === 'medium' ? '推荐' : '可选'}
                </span>
              </motion.div>
            )
          })}
        </div>
      </motion.div>

      {/* Confetti celebration */}
      <AnimatePresence>
        {allDone && (
          <motion.div
            className={styles.confettiOverlay}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            {Array.from({ length: 24 }).map((_, i) => (
              <motion.span
                key={i}
                className={styles.confettiParticle}
                initial={{
                  x: 0, y: 0, opacity: 1, scale: 1,
                }}
                animate={{
                  x: (Math.random() - 0.5) * 400,
                  y: (Math.random() - 0.5) * 400 - 200,
                  opacity: 0,
                  scale: 0,
                }}
                transition={{ duration: 1.5 + Math.random(), ease: 'easeOut' as const }}
                style={{
                  left: `${40 + Math.random() * 20}%`,
                  top: `${30 + Math.random() * 20}%`,
                  background: ['var(--cr-accent)', 'var(--cr-green)', 'var(--cr-yellow)', 'var(--cr-red)'][i % 4],
                }}
              />
            ))}
            <p className={styles.confettiText}>全部完成！</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Confirm bar */}
      <div className={styles.confirmBar}>
        <button
          type="button"
          className={styles.confirmBtn}
          disabled={actionState === 'CONFIRMED'}
          onClick={() => onConfirm('action')}
        >
          {actionState === 'CONFIRMED' ? '已确认' : '确认行动计划'}
        </button>
      </div>
    </div>
  )
}
