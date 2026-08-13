import { motion, AnimatePresence } from 'framer-motion'
import styles from './MatchPipeline.module.css'

interface MatchPipelineProps {
  expanded: boolean
  onToggle: () => void
  detailNode: number | null
  onDetailClick: (idx: number | null) => void
}

const STEPS = [
  { label: '你的技能', detail: '原始技能列表: Python, FastAPI, React, PostgreSQL...' },
  { label: '分词 & 向量化', detail: '使用 sentence-transformers 编码技能描述 → 768维向量' },
  { label: '产业需求库检索', detail: 'ChromaDB 向量检索 → 召回 Top-50 相关职位需求' },
  { label: 'Jaccard + 加权', detail: '技能重叠度 ×0.5 + 经验匹配 ×0.25 + 行业前景 ×0.15 + 学习成本 ×0.1' },
  { label: '方向排序', detail: '综合得分降序排列 → 返回 Top-N 推荐方向' },
]

const NODE_W = 130; const NODE_H = 40; const GAP = 60

export default function MatchPipeline({ expanded, onToggle, detailNode, onDetailClick }: MatchPipelineProps) {
  return (
    <div className={styles.wrap}>
      <button className={styles.header} onClick={onToggle}>
        <span>匹配算法流程</span>
        <span className={styles.chevron}>{expanded ? '▼' : '▶'}</span>
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className={styles.body}
          >
            <svg viewBox={`0 0 ${STEPS.length * (NODE_W + GAP) + 20} 100`} className={styles.svg}>
              {STEPS.map((step, i) => {
                const x = 10 + i * (NODE_W + GAP)
                const y = 20
                return (
                  <g key={i}>
                    {/* Arrow */}
                    {i > 0 && (
                      <line x1={x - GAP + NODE_W} y1={y + NODE_H / 2} x2={x} y2={y + NODE_H / 2}
                        className={styles.arrow} />
                    )}
                    <rect x={x} y={y} width={NODE_W} height={NODE_H} rx={8}
                      className={`${styles.node} ${detailNode === i ? styles.nodeActive : ''}`}
                      onClick={() => onDetailClick(detailNode === i ? null : i)} />
                    <text x={x + NODE_W / 2} y={y + NODE_H / 2 + 1}
                      className={styles.nodeText} textAnchor="middle" dominantBaseline="middle">
                      {step.label}
                    </text>
                    {/* Arrow head */}
                    {i > 0 && (
                      <polygon
                        points={`${x - 6},${y + NODE_H / 2 - 5} ${x},${y + NODE_H / 2} ${x - 6},${y + NODE_H / 2 + 5}`}
                        className={styles.arrowHead} />
                    )}
                  </g>
                )
              })}
            </svg>
            <AnimatePresence>
              {detailNode !== null && (
                <motion.div
                  className={styles.detailPanel}
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.25 }}
                >
                  <p className={styles.detailText}>{STEPS[detailNode].detail}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
