import { useState } from 'react'
import { DraggableSheet } from 'react-driftkit'
import type { SnapPoint } from 'react-driftkit'
import styles from './ResponseSheet.module.css'

interface Props {
  id: string
  html: string
  type: string
  onClose: (id: string) => void
}

export default function ResponseSheet({ id, html, type, onClose }: Props) {
  const [snap, setSnap] = useState<SnapPoint>('half')

  const handleSnapChange = (next: SnapPoint, _sizePx: number) => {
    if (next === 'closed') {
      onClose(id)
    } else {
      setSnap(next)
    }
  }

  return (
    <DraggableSheet
      edge="bottom"
      snapPoints={['closed', 'peek', 'half']}
      snap={snap}
      onSnapChange={handleSnapChange}
      dragHandleSelector={`.${styles.handle}`}
      closeOnOutsideClick={false}
      className={styles.sheet}
    >
      <div className={styles.handle}>
        <span className={styles.handleDot} />
        <span className={`${styles.badge} ${type === 'guide' ? styles.badgeGuide : styles.badgeSystem}`}>
          {type === 'guide' ? '分析结果' : type === 'user' ? '你' : '系统'}
        </span>
      </div>
      <div className={styles.body} dangerouslySetInnerHTML={{ __html: html }} />
      <button className={styles.closeBtn} onClick={() => onClose(id)}>
        关闭
      </button>
    </DraggableSheet>
  )
}
