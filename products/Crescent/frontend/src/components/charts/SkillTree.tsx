import { motion, AnimatePresence } from 'framer-motion'
import type { MockProfile, MockDirection } from '../../data/mockContent'
import styles from './SkillTree.module.css'

interface SkillTreeProps {
  skills: MockProfile['skills']
  directions: MockDirection[]
  onSkillClick: (skillName: string) => void
  expandedNodes: Set<string>
  onToggleNode: (nodeId: string) => void
}

interface TreeNode {
  id: string
  label: string
  depth: number
  color?: string
  children?: TreeNode[]
  dirMatches?: string[] // direction names this skill contributes to
}

const CAT_COLORS: Record<string, string> = {
  language: 'var(--cr-accent)',
  framework: 'var(--cr-green)',
  tool: '#8B7EC8',
  soft: 'var(--cr-yellow)',
}

const CAT_LABELS: Record<string, string> = {
  language: '语言',
  framework: '框架',
  tool: '工具',
  soft: '软技能',
}

function buildTree(
  skills: MockProfile['skills'],
  directions: MockDirection[],
): TreeNode {
  const cats = new Map<string, TreeNode>()
  skills.forEach((s) => {
    if (!cats.has(s.category)) {
      cats.set(s.category, {
        id: s.category,
        label: CAT_LABELS[s.category] || s.category,
        depth: 1,
        color: CAT_COLORS[s.category],
        children: [],
      })
    }
    const dirMatches = directions
      .filter((d) => d.overlaps.includes(s.name))
      .map((d) => d.name)
    cats.get(s.category)!.children!.push({
      id: s.name,
      label: s.name,
      depth: 2,
      dirMatches,
    })
  })
  return {
    id: 'root',
    label: '技能池',
    depth: 0,
    children: Array.from(cats.values()),
  }
}

const NODE_W = 100
const NODE_H = 28
const LEVEL_GAP = 160
const NODE_GAP = 10

export default function SkillTree({
  skills,
  directions,
  onSkillClick,
  expandedNodes,
  onToggleNode,
}: SkillTreeProps) {
  const tree = buildTree(skills, directions)
  if (!tree.children) return null

  const nodes: {
    node: TreeNode
    x: number
    y: number
    parentX?: number
    parentY?: number
  }[] = []

  /**
   * Recursive tree layout.
   *
   * Pushes `node` into the `nodes` array at the computed position, then
   * lays out children (if expanded) below it. Returns the next free y offset.
   *
   * Fixes over the brief's original algorithm:
   *  - No double-push of child nodes (brief line 89 re-pushed what layout()
   *    had already pushed).
   *  - Return value is the *next* free y, not the child's own y.
   *  - parentX/parentY are threaded through so connector lines always
   *    connect a node's right edge to its child's centre-left.
   */
  function layout(
    node: TreeNode,
    level: number,
    yOffset: number,
    parentX?: number,
    parentY?: number,
  ): number {
    const x = 20 + level * LEVEL_GAP
    const y = yOffset
    nodes.push({ node, x, y, parentX, parentY })

    // Leaf or collapsed — just this node
    if (
      !node.children ||
      node.children.length === 0 ||
      !expandedNodes.has(node.id)
    ) {
      return y + NODE_H + NODE_GAP
    }

    // Expanded branch — lay out children, accumulating y
    let nextY = y + NODE_H + NODE_GAP
    const nodeW = node.depth === 2 ? NODE_W : NODE_W - 10
    const midY = y + NODE_H / 2

    node.children.forEach((child) => {
      nextY = layout(child, level + 1, nextY, x + nodeW, midY)
    })
    return nextY
  }

  const rootCx = 20 + NODE_W
  const rootCy = 10 + NODE_H / 2
  let y = 20
  tree.children.forEach((cat) => {
    y = layout(cat, 1, y, rootCx, rootCy)
  })
  const svgHeight = y + 20

  return (
    <div className={styles.wrap}>
      <svg
        viewBox={`0 0 ${20 + 3 * LEVEL_GAP + NODE_W} ${svgHeight}`}
        className={styles.svg}
      >
        {/* Root node (hardcoded — not in animated list) */}
        <rect
          x={20}
          y={10}
          width={NODE_W}
          height={NODE_H}
          rx={14}
          className={styles.rootNode}
        />
        <text
          x={20 + NODE_W / 2}
          y={10 + NODE_H / 2 + 1}
          className={styles.nodeText}
          textAnchor="middle"
        >
          技能池
        </text>

        <AnimatePresence>
          {nodes.map(({ node, x, y, parentX, parentY }) => {
            const isSkill = node.depth === 2
            const nodeW = isSkill ? NODE_W : NODE_W - 10
            return (
              <motion.g
                key={node.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                {/* Connector line from parent's right edge to child's left-centre */}
                {parentX !== undefined && parentY !== undefined && (
                  <line
                    x1={parentX}
                    y1={parentY}
                    x2={x}
                    y2={y + NODE_H / 2}
                    className={styles.line}
                    style={{
                      stroke: node.color || 'var(--cr-border-hv)',
                    }}
                  />
                )}

                {/* Node rectangle */}
                <rect
                  x={x}
                  y={y}
                  width={nodeW}
                  height={NODE_H}
                  rx={isSkill ? 4 : 14}
                  className={isSkill ? styles.skillNode : styles.catNode}
                  style={
                    node.color && !isSkill
                      ? { stroke: node.color }
                      : undefined
                  }
                  onClick={() => {
                    if (isSkill) onSkillClick(node.label)
                    else onToggleNode(node.id)
                  }}
                  cursor="pointer"
                />

                {/* Node label */}
                <text
                  x={x + nodeW / 2}
                  y={y + NODE_H / 2 + 1}
                  className={isSkill ? styles.skillText : styles.catText}
                  textAnchor="middle"
                >
                  {node.label}
                </text>

                {/* Direction match hint badge */}
                {node.dirMatches && node.dirMatches.length > 0 && (
                  <text
                    x={x + NODE_W + 6}
                    y={y + NODE_H / 2 + 1}
                    className={styles.matchHint}
                  >
                    +{node.dirMatches.length}
                  </text>
                )}
              </motion.g>
            )
          })}
        </AnimatePresence>
      </svg>
    </div>
  )
}
