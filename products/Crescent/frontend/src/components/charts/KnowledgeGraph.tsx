import { useEffect, useRef, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import type { MockDirection } from '../../data/mockContent'
import styles from './KnowledgeGraph.module.css'

interface KnowledgeGraphProps {
  skills: string[]
  directions: MockDirection[]
  highlightedSkill: string | null
  highlightedDirection: number | null
  onNodeClick: (nodeId: string, nodeType: 'skill' | 'direction') => void
  onNodeHover: (nodeId: string | null) => void
}

interface SimNode {
  id: string
  type: 'skill' | 'direction'
  x: number; y: number
  vx: number; vy: number
  label: string
}

interface SimLink { source: number; target: number; strong: boolean }

const W = 400; const H = 350
const MAX_NODES = 50

export default function KnowledgeGraph({
  skills, directions, highlightedSkill, highlightedDirection, onNodeClick, onNodeHover,
}: KnowledgeGraphProps) {
  const [nodes, setNodes] = useState<SimNode[]>([])
  const [links, setLinks] = useState<SimLink[]>([])
  const [dragging, setDragging] = useState<number | null>(null)
  const animRef = useRef<number>(0)
  const svgRef = useRef<SVGSVGElement>(null)

  // Build graph data
  useEffect(() => {
    const newNodes: SimNode[] = []
    const newLinks: SimLink[] = []

    skills.forEach((s) => {
      newNodes.push({ id: s, type: 'skill', x: Math.random() * W, y: Math.random() * H, vx: 0, vy: 0, label: s })
    })

    directions.forEach((d, di) => {
      const did = `dir_${di}`
      newNodes.push({ id: did, type: 'direction', x: Math.random() * W, y: Math.random() * H, vx: 0, vy: 0, label: d.name })

      d.overlaps.forEach((s) => {
        const si = newNodes.findIndex((n) => n.id === s)
        if (si >= 0) newLinks.push({ source: si, target: newNodes.length - 1, strong: true })
      })
      d.gaps.forEach((s) => {
        const si = newNodes.findIndex((n) => n.id === s)
        if (si >= 0) newLinks.push({ source: si, target: newNodes.length - 1, strong: false })
      })
    })

    if (newNodes.length > MAX_NODES) {
      // Degrade to static grid layout
      newNodes.forEach((n, i) => { n.x = 40 + (i % 5) * 72; n.y = 40 + Math.floor(i / 5) * 60 })
    }

    setNodes(newNodes)
    setLinks(newLinks)
  }, [skills, directions])

  // Force simulation
  useEffect(() => {
    if (nodes.length === 0 || nodes.length > MAX_NODES) return

    const simNodes = nodes.map((n) => ({ ...n }))
    let running = true

    function tick() {
      if (!running) return
      // Repulsion (O(n²) — fine for ≤50 nodes)
      for (let i = 0; i < simNodes.length; i++) {
        for (let j = i + 1; j < simNodes.length; j++) {
          const dx = simNodes[j].x - simNodes[i].x
          const dy = simNodes[j].y - simNodes[i].y
          const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy))
          const force = 2000 / (dist * dist)
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          simNodes[i].vx -= fx; simNodes[i].vy -= fy
          simNodes[j].vx += fx; simNodes[j].vy += fy
        }
      }
      // Attraction (links)
      links.forEach((l) => {
        const dx = simNodes[l.target].x - simNodes[l.source].x
        const dy = simNodes[l.target].y - simNodes[l.source].y
        const dist = Math.sqrt(dx * dx + dy * dy)
        const force = (dist - 80) * 0.005
        simNodes[l.source].vx += dx * force
        simNodes[l.source].vy += dy * force
        simNodes[l.target].vx -= dx * force
        simNodes[l.target].vy -= dy * force
      })
      // Center gravity + damping
      simNodes.forEach((n) => {
        n.vx += (W / 2 - n.x) * 0.001
        n.vy += (H / 2 - n.y) * 0.001
        n.vx *= 0.85; n.vy *= 0.85
        n.x = Math.max(12, Math.min(W - 12, n.x + n.vx))
        n.y = Math.max(12, Math.min(H - 12, n.y + n.vy))
      })
      setNodes(simNodes.map((n) => ({ ...n })))
      animRef.current = requestAnimationFrame(tick)
    }
    animRef.current = requestAnimationFrame(tick)
    return () => { running = false; cancelAnimationFrame(animRef.current) }
  }, [nodes.length, links])

  // Convert pointer screen coords to viewBox coords
  const svgToViewBox = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const rect = svg.getBoundingClientRect()
    return {
      x: ((clientX - rect.left) / rect.width) * W,
      y: ((clientY - rect.top) / rect.height) * H,
    }
  }, [])

  const handlePointerDown = useCallback((i: number, e: React.PointerEvent) => {
    e.preventDefault()
    const svg = svgRef.current
    if (svg) svg.setPointerCapture(e.pointerId)
    setDragging(i)
  }, [])

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (dragging === null) return
    const vb = svgToViewBox(e.clientX, e.clientY)
    setNodes((ns) => ns.map((n, idx) =>
      idx === dragging
        ? { ...n, x: Math.max(12, Math.min(W - 12, vb.x)), y: Math.max(12, Math.min(H - 12, vb.y)) }
        : n,
    ))
  }, [dragging, svgToViewBox])

  const handlePointerUp = useCallback(() => setDragging(null), [])

  const isSkillHighlighted = (id: string) => highlightedSkill === id
  const isDirHighlighted = (i: number) => highlightedDirection === i

  // Empty state
  if (nodes.length === 0) {
    return (
      <div className={styles.wrap}>
        <h4 className={styles.title}>知识关系网络</h4>
        <svg viewBox={`0 0 ${W} ${H}`} className={styles.svg} />
      </div>
    )
  }

  return (
    <div className={styles.wrap}>
      <h4 className={styles.title}>知识关系网络</h4>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className={styles.svg}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        style={{ touchAction: dragging !== null ? 'none' : undefined }}
      >
        {links.map((l, i) => {
          const s = nodes[l.source]; const t = nodes[l.target]
          if (!s || !t) return null
          return (
            <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y}
              className={`${l.strong ? styles.linkStrong : styles.linkGap}${highlightedSkill && (s.id === highlightedSkill || t.id === highlightedSkill) ? ' ' + styles.linkHighlighted : ''}`} />
          )
        })}
        {nodes.map((n, i) => {
          const isSkill = n.type === 'skill'
          const highlighted = isSkill
            ? isSkillHighlighted(n.id)
            : isDirHighlighted(parseInt(n.id.replace('dir_', ''), 10))
          return (
            <g key={n.id}>
              <motion.circle cx={n.x} cy={n.y} r={isSkill ? 10 : 14}
                className={`${isSkill ? styles.nodeSkill : styles.nodeDir}${highlighted ? ' ' + styles.nodeHighlighted : ''}`}
                initial={{ opacity: 0, r: 0 }}
                animate={{ opacity: 1, r: isSkill ? 10 : 14 }}
                transition={{ delay: i * 0.05, duration: 0.3 }}
                onPointerDown={(e) => handlePointerDown(i, e)}
                onClick={() => onNodeClick(n.id, n.type)}
                onPointerEnter={() => onNodeHover(n.id)}
                onPointerLeave={() => onNodeHover(null)} />
              <motion.text x={n.x} y={n.y + (isSkill ? 20 : 22)}
                className={styles.nodeLabel} textAnchor="middle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.05 + 0.15, duration: 0.3 }}>
                {n.label.length > 8 ? n.label.slice(0, 8) + '…' : n.label}
              </motion.text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
