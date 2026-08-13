import { useMemo } from 'react'
import { motion } from 'framer-motion'
import styles from './RadarChart.module.css'

interface RadarChartProps {
  userValues: { language: number; framework: number; tool: number; soft: number }
  baselineValues: { language: number; framework: number; tool: number; soft: number }
  animated?: boolean
}

const DIMENSIONS = [
  { key: 'language' as const, label: '语言深度', angle: -90 },
  { key: 'framework' as const, label: '框架广度', angle: -18 },
  { key: 'tool' as const, label: '工具链', angle: 54 },
  { key: 'soft' as const, label: '软技能', angle: 126 },
]

const CX = 140; const CY = 130; const R = 100

function polarToCart(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg - 90) * (Math.PI / 180)
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

export default function RadarChart({ userValues, baselineValues, animated }: RadarChartProps) {
  const avgScore = Math.round(
    (userValues.language + userValues.framework + userValues.tool + userValues.soft) / 4,
  )

  const userPoints = useMemo(
    () =>
      DIMENSIONS.map((d) => {
        const val = userValues[d.key] / 100
        return polarToCart(CX, CY, R * val, d.angle)
      }),
    [userValues],
  )

  const baselinePoints = useMemo(
    () =>
      DIMENSIONS.map((d) => {
        const val = baselineValues[d.key] / 100
        return polarToCart(CX, CY, R * val, d.angle)
      }),
    [baselineValues],
  )

  const userPath = userPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ') + ' Z'
  const baselinePath =
    baselinePoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ') + ' Z'

  const labelPoints = DIMENSIONS.map((d) => polarToCart(CX, CY, R + 24, d.angle))

  return (
    <div className={styles.wrap}>
      <svg viewBox="0 0 280 260" className={styles.svg}>
        {/* Grid rings */}
        {[0.25, 0.5, 0.75, 1].map((s) => {
          const r = R * s
          const pts = DIMENSIONS.map((d) => polarToCart(CX, CY, r, d.angle))
          const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ') + ' Z'
          return <path key={s} d={d} className={styles.gridRing} />
        })}

        {/* Axes */}
        {DIMENSIONS.map((d) => {
          const end = polarToCart(CX, CY, R, d.angle)
          return <line key={d.key} x1={CX} y1={CY} x2={end.x} y2={end.y} className={styles.axis} />
        })}

        {/* Baseline polygon */}
        <motion.path
          d={baselinePath}
          className={styles.baselinePoly}
          initial={animated ? { scale: 0, opacity: 0 } : undefined}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          style={{ transformOrigin: '140px 130px' }}
        />

        {/* User polygon */}
        <motion.path
          d={userPath}
          className={styles.userPoly}
          initial={animated ? { scale: 0, opacity: 0 } : undefined}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          style={{ transformOrigin: '140px 130px' }}
        />

        {/* Labels */}
        {labelPoints.map((p, i) => (
          <text
            key={i}
            x={p.x}
            y={p.y}
            className={styles.label}
            textAnchor="middle"
            dominantBaseline="middle"
          >
            {DIMENSIONS[i].label}
          </text>
        ))}

        {/* Center score */}
        <text x={CX} y={CY - 6} className={styles.centerScore} textAnchor="middle">
          {avgScore}
        </text>
        <text x={CX} y={CY + 12} className={styles.centerLabel} textAnchor="middle">
          综合分
        </text>
      </svg>
    </div>
  )
}
