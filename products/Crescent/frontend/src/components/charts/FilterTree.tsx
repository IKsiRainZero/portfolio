import { motion, AnimatePresence } from 'framer-motion'
import styles from './FilterTree.module.css'

interface FilterTreeProps {
  totalCount: number
  survivedCount: number
  detailNode: number | null
  onDetailClick: (idx: number | null) => void
}

const FILTERS = [
  { label: '行业增长率 > 5%', eliminated: 4, details: ['传统运维', '桌面开发', '嵌入式C', 'Windows Forms'] },
  { label: '技术栈重叠 > 2项', eliminated: 3, details: ['前端专家', '数据科学', 'DevOps'] },
  { label: '学习成本 < 200h', eliminated: 2, details: ['NLP研究员', 'CV工程师'] },
]

const NODE_W = 160; const NODE_H = 32; const LAYER_GAP = 72

export default function FilterTree({ totalCount, survivedCount, detailNode, onDetailClick }: FilterTreeProps) {
  const svgW = 360; const svgH = FILTERS.length * LAYER_GAP + 120

  return (
    <div className={styles.wrap}>
      <h4 className={styles.title}>方向筛选过程</h4>
      <svg viewBox={`0 0 ${svgW} ${svgH}`} className={styles.svg}>
        {/* Root */}
        <rect x={svgW / 2 - NODE_W / 2} y={10} width={NODE_W} height={NODE_H} rx={16} className={styles.rootNode} />
        <text x={svgW / 2} y={10 + NODE_H / 2 + 1} className={styles.rootText} textAnchor="middle" dominantBaseline="middle">
          所有可能方向 ({totalCount})
        </text>

        {FILTERS.map((f, i) => {
          const y = 60 + i * LAYER_GAP
          const passX = svgW / 2 - NODE_W - 20
          const elimX = svgW / 2 + 20
          const parentX = i === 0 ? svgW / 2 : svgW / 2 - NODE_W - 20
          const parentY = i === 0 ? 10 + NODE_H : 60 + (i - 1) * LAYER_GAP + NODE_H

          return (
            <g key={i}>
              {/* Lines from parent */}
              <line x1={parentX} y1={parentY} x2={passX + NODE_W / 2} y2={y + NODE_H / 2} className={styles.line} />
              <line x1={parentX} y1={parentY} x2={elimX + NODE_W / 2} y2={y + NODE_H / 2} className={styles.lineElim} />

              {/* Pass node */}
              <rect x={passX} y={y} width={NODE_W} height={NODE_H} rx={6}
                className={`${styles.passNode} ${detailNode === i ? styles.nodeActive : ''}`}
                onClick={() => onDetailClick(detailNode === i ? null : i)} />
              <text x={passX + NODE_W / 2} y={y - 6} className={styles.condLabel} textAnchor="middle">{f.label}</text>
              <text x={passX + NODE_W / 2} y={y + NODE_H / 2 + 1} className={styles.passText} textAnchor="middle" dominantBaseline="middle">✓ 通过</text>

              {/* Eliminated node */}
              <rect x={elimX} y={y} width={NODE_W} height={NODE_H} rx={6} className={styles.elimNode} />
              <text x={elimX + NODE_W / 2} y={y + NODE_H / 2 + 1} className={styles.elimText} textAnchor="middle" dominantBaseline="middle">
                ✗ 淘汰 {f.eliminated} 个
              </text>
            </g>
          )
        })}

        {/* Result */}
        <rect x={svgW / 2 - NODE_W / 2} y={60 + FILTERS.length * LAYER_GAP} width={NODE_W} height={NODE_H} rx={8} className={styles.resultNode} />
        <text x={svgW / 2} y={60 + FILTERS.length * LAYER_GAP + NODE_H / 2 + 1} className={styles.resultText} textAnchor="middle" dominantBaseline="middle">
          → {survivedCount} 个推荐方向
        </text>
      </svg>

      <AnimatePresence>
        {detailNode !== null && (
          <motion.div
            className={styles.detailPanel}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
          >
            <span className={styles.detailLabel}>淘汰的方向：</span>
            {FILTERS[detailNode].details.join('、')}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
