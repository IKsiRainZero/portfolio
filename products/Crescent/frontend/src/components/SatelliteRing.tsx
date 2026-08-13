import { motion } from 'framer-motion'
import styles from './SatelliteRing.module.css'

interface Satellite {
  title: string
  desc: string
  status: string
  color: string
}

const SATELLITES: Satellite[] = [
  {
    title: '产业-能力匹配引擎',
    desc: '技能→趋势搜索→差距分析→2-3个可行方向',
    status: 'Phase 1',
    color: 'var(--cr-accent)',
  },
  {
    title: '智能教师',
    desc: '路径分解→心理模型→引导式教学（问而不答）',
    status: '规划中',
    color: 'var(--cr-green)',
  },
  {
    title: '行动树+状态机',
    desc: '任务依赖图→事件驱动→"现在该做什么"',
    status: '规划中',
    color: 'var(--cr-yellow)',
  },
  {
    title: '自我编辑循环',
    desc: '运行日志→效果评估→自动修复→部署测试环',
    status: '规划中',
    color: '#8B7EC8',
  },
]

export default function SatelliteRing() {
  return (
    <div className={styles.scene} aria-hidden="true">
      <div className={styles.ring}>
        {SATELLITES.map((sat, i) => {
          const angle = i * 90 // 0, 90, 180, 270 degrees
          return (
            <div
              key={i}
              className={styles.cardWrapper}
              style={{
                transform: `rotateY(${angle}deg) translateZ(340px)`,
              }}
            >
              <div
                className={styles.card}
                style={{ '--sat-color': sat.color } as React.CSSProperties}
              >
                <span className={styles.cardStatus}>{sat.status}</span>
                <h3 className={styles.cardTitle}>{sat.title}</h3>
                <p className={styles.cardDesc}>{sat.desc}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
