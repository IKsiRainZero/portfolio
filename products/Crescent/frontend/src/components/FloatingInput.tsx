import { useState, useRef, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MovableLauncher } from 'react-driftkit'
import StatusDot from './StatusDot'
import styles from './FloatingInput.module.css'

interface Props {
  processing: boolean
  processingMsg: string
  hasSession: boolean
  autoOpen: boolean
  onAutoOpenDone: () => void
  dismissedCount: number
  onRestoreDismissed: () => void
  onSend: (text: string) => void
}

export default function FloatingInput({
  processing, processingMsg, hasSession,
  autoOpen, onAutoOpenDone,
  dismissedCount, onRestoreDismissed,
  onSend,
}: Props) {
  const [open, setOpen] = useState(false)
  const [entering, setEntering] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-open with center→bottom entrance when session starts
  useEffect(() => {
    if (autoOpen) {
      setEntering(true)
      setOpen(true)
      const timer = setTimeout(() => {
        setEntering(false)
        onAutoOpenDone()
      }, 1800)
      return () => clearTimeout(timer)
    }
  }, [autoOpen, onAutoOpenDone])

  const toggle = useCallback(() => {
    setOpen((o) => {
      if (!o) requestAnimationFrame(() => inputRef.current?.focus())
      return !o
    })
  }, [])

  const close = useCallback(() => setOpen(false), [])

  const handleSend = useCallback(() => {
    const text = inputRef.current?.value.trim()
    if (!text || processing) return
    onSend(text)
    inputRef.current!.value = ''
    setOpen(false)
  }, [processing, onSend])

  // Global shortcut: Cmd+J / Ctrl+J
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'j') {
        e.preventDefault()
        toggle()
      }
      if (e.key === 'Escape' && open) {
        close()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toggle, close, open])

  return (
    <>
      <MovableLauncher defaultPosition="bottom-right">
        <button
          className={`${styles.fab} ${open ? styles.fabOpen : ''} ${processing ? styles.fabProcessing : ''}`}
          onClick={toggle}
          aria-label={open ? '关闭输入' : '打开输入'}
        >
          <span className={styles.fabIcon}>{open ? '×' : '⌨'}</span>
        </button>
      </MovableLauncher>

      {dismissedCount > 0 && (
        <button
          type="button"
          className={styles.dismissedBadge}
          onClick={onRestoreDismissed}
          title="恢复最近关闭的消息"
        >
          消息 {dismissedCount}
        </button>
      )}

      <AnimatePresence>
        {open && (
          <motion.div
            className={styles.overlay}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={close}
          >
            <motion.div
              className={styles.inputBar}
              initial={
                entering
                  ? { y: '-50vh', scale: 0.92, opacity: 0 }
                  : { y: 12, opacity: 0 }
              }
              animate={
                entering
                  ? { y: 0, scale: 1, opacity: 1 }
                  : { y: 0, opacity: 1 }
              }
              transition={
                entering
                  ? { duration: 0.7, delay: 0.2, ease: [0.16, 1, 0.3, 1] }
                  : { duration: 0.2, ease: 'easeOut' }
              }
              onClick={(e) => e.stopPropagation()}
            >
              <div className={styles.inputBarTop}>
                <StatusDot processing={processing} active={hasSession && !processing} />
                <span className={styles.statusText}>
                  {processing ? processingMsg : (hasSession ? '就绪 — 描述你的想法' : '描述你的技能和经历')}
                </span>
                <span className={styles.hint}>Ctrl+J 切换 · Esc 关闭</span>
              </div>
              <div className={styles.inputRow}>
                <input
                  ref={inputRef}
                  className={styles.input}
                  placeholder="描述你的技能和经历…"
                  disabled={processing}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSend()
                    }
                  }}
                />
                <button
                  className={styles.sendBtn}
                  onClick={handleSend}
                  disabled={processing}
                >
                  发送
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
