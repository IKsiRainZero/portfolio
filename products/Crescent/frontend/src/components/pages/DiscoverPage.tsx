import { useState, useMemo, useCallback } from 'react'
import { motion } from 'framer-motion'
import type { MockProfile, MockDirection } from '../../data/mockContent'
import { getMockPayload, getRelatedDirections, getRelatedSkills } from '../../data/mockContent'
import ProfileEditor from './ProfileEditor'
import SkillTree from '../charts/SkillTree'
import MatchPipeline from '../charts/MatchPipeline'
import FilterTree from '../charts/FilterTree'
import KnowledgeGraph from '../charts/KnowledgeGraph'
import styles from './DiscoverPage.module.css'

interface Props {
  panelStates: Record<string, string>
  panelPayloads: Record<string, Record<string, unknown>>
  hasSession: boolean
  onConfirm: (pid: string) => void
}

const leftVariants = {
  hidden: { y: 20, opacity: 0 },
  show: { y: 0, opacity: 1, transition: { duration: 0.5, ease: 'easeOut' as const } },
}

const rightVariants = {
  hidden: { y: 20, opacity: 0 },
  show: { y: 0, opacity: 1, transition: { duration: 0.5, ease: 'easeOut' as const, delay: 0.4 } },
}

export default function DiscoverPage({
  panelStates, panelPayloads, hasSession, onConfirm,
}: Props) {
  // Profile data
  const profilePayload = hasSession ? panelPayloads.profile : getMockPayload('profile')
  const profileHasData = !!(profilePayload && 'skills' in profilePayload)
  const profile = profileHasData ? (profilePayload as unknown as MockProfile) : null
  const [editedProfile, setEditedProfile] = useState<MockProfile | null>(null)
  const effectiveProfile = editedProfile || profile
  const profileDirty = editedProfile !== null

  // Direction data
  const directionPayload = hasSession ? panelPayloads.direction : getMockPayload('direction')
  const directions = (directionPayload?.directions as MockDirection[]) || []

  // Selection state
  const [selectedDirection, setSelectedDirection] = useState<number | null>(null)
  const [expandedDirection, setExpandedDirection] = useState<number | null>(null)

  // Cross-linking state
  const [highlightedSkill, setHighlightedSkill] = useState<string | null>(null)
  const highlightedDirections = useMemo(
    () => (highlightedSkill ? getRelatedDirections(highlightedSkill, directions) : []),
    [highlightedSkill, directions],
  )
  const highlightedSkills = useMemo(
    () => (selectedDirection !== null ? getRelatedSkills(selectedDirection, directions) : []),
    [selectedDirection, directions],
  )

  // Pipeline state
  const [pipelineOpen, setPipelineOpen] = useState(true)
  const [pipelineDetail, setPipelineDetail] = useState<number | null>(null)

  // Filter tree state
  const [filterDetail, setFilterDetail] = useState<number | null>(null)

  // SkillTree state
  const [skillTreeExpanded, setSkillTreeExpanded] = useState<Set<string>>(new Set())
  const handleToggleSkillNode = useCallback((nodeId: string) => {
    setSkillTreeExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(nodeId)) next.delete(nodeId)
      else next.add(nodeId)
      return next
    })
  }, [])

  const allSkills = effectiveProfile?.skills?.map((s) => s.name) ?? []

  const handleSkillClick = useCallback((skillName: string) => {
    setHighlightedSkill((prev) => (prev === skillName ? null : skillName))
  }, [])

  const profileState = panelStates.profile || 'EMPTY'
  const directionState = panelStates.direction || 'EMPTY'

  return (
    <div className={styles.page}>
      {/* LEFT: Profile */}
      <motion.div
        className={styles.left}
        variants={leftVariants}
        initial="hidden"
        animate="show"
      >
        <ProfileEditor
          profile={effectiveProfile}
          onProfileChange={setEditedProfile}
          onConfirm={() => onConfirm('profile')}
          confirmed={profileState === 'CONFIRMED'}
        />

        {/* SkillTree */}
        {effectiveProfile?.skills?.length ? (
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>技能关系</h3>
            <div className={styles.skillTreeWrap}>
              <SkillTree
                skills={effectiveProfile.skills}
                directions={directions}
                onSkillClick={handleSkillClick}
                expandedNodes={skillTreeExpanded}
                onToggleNode={handleToggleSkillNode}
              />
            </div>
          </div>
        ) : null}
      </motion.div>

      {/* RIGHT: Direction */}
      <motion.div
        className={styles.right}
        variants={rightVariants}
        initial="hidden"
        animate="show"
      >
        {/* Pipeline */}
        <MatchPipeline
          expanded={pipelineOpen}
          onToggle={() => setPipelineOpen((o) => !o)}
          detailNode={pipelineDetail}
          onDetailClick={setPipelineDetail}
        />

        {/* FilterTree */}
        <FilterTree
          totalCount={12}
          survivedCount={directions.length}
          detailNode={filterDetail}
          onDetailClick={setFilterDetail}
        />

        {/* KnowledgeGraph */}
        <KnowledgeGraph
          skills={allSkills}
          directions={directions}
          highlightedSkill={highlightedSkill}
          highlightedDirection={selectedDirection}
          onNodeClick={(nodeId, nodeType) => {
            if (nodeType === 'skill') handleSkillClick(nodeId)
            else setSelectedDirection(parseInt(nodeId.replace('dir_', ''), 10))
          }}
          onNodeHover={() => {}}
        />

        {/* Direction cards */}
        <div className={styles.section}>
          <header className={styles.dirHeader}>
            <h3 className={styles.sectionTitle}>匹配方向</h3>
            {directionState === 'CONFIRMED' && (
              <span className={styles.badge}>已确认</span>
            )}
          </header>

          {/* Profile dirty warning */}
          {profileDirty && (
            <div className={styles.dirtyWarning}>
              画像已修改，请通过对话框发送消息重新匹配
            </div>
          )}

          {directions.map((dir, i) => {
            const isSelected = selectedDirection === i
            const isExpanded = expandedDirection === i
            const isHighlighted = highlightedDirections.includes(i)
            return (
              <motion.div
                key={i}
                className={`${styles.dirCard} ${
                  isSelected ? styles.dirCardSelected : ''
                } ${
                  isHighlighted ? styles.dirCardHighlighted : ''
                }`}
                initial={{ y: 16, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: i * 0.08, duration: 0.4 }}
                onClick={() => setSelectedDirection(i)}
              >
                <div className={styles.cardTop}>
                  <h4 className={styles.dirName}>{dir.name}</h4>
                  <span
                    className={`${styles.score} ${
                      dir.matchScore >= 80
                        ? styles.scoreHigh
                        : dir.matchScore >= 65
                          ? styles.scoreMid
                          : styles.scoreLow
                    }`}
                  >
                    {dir.matchScore}% 匹配
                  </span>
                </div>
                <p className={styles.reason}>{dir.reason}</p>

                <button
                  type="button"
                  className={styles.expandBtn}
                  onClick={(e) => {
                    e.stopPropagation()
                    setExpandedDirection(isExpanded ? null : i)
                  }}
                >
                  匹配详情 <span>{isExpanded ? '▼' : '▶'}</span>
                </button>

                {isExpanded && (
                  <motion.div
                    className={styles.detail}
                    initial={{ height: 0 }}
                    animate={{ height: 'auto' }}
                    transition={{ duration: 0.3 }}
                  >
                    <div className={styles.detailInner}>
                      <div className={styles.detailCol}>
                        <span className={styles.detailLabel}>重叠技能</span>
                        {dir.overlaps.map((s) => (
                          <span
                            key={s}
                            className={`${styles.skillTag} ${styles.overlap} ${
                              highlightedSkills.includes(s)
                                ? styles.skillHighlighted
                                : ''
                            }`}
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                      <div className={styles.detailCol}>
                        <span className={styles.detailLabel}>需要学习</span>
                        {dir.gaps.map((s) => (
                          <span
                            key={s}
                            className={`${styles.skillTag} ${styles.gap} ${
                              highlightedSkills.includes(s)
                                ? styles.skillHighlighted
                                : ''
                            }`}
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                    {/* Score breakdown table */}
                    <ScoreBreakdown score={dir.matchScore} />
                  </motion.div>
                )}
              </motion.div>
            )
          })}

          {directions.length === 0 && (
            <div className={styles.empty}>
              {profileDirty
                ? '请重新匹配以获取方向推荐'
                : '完成能力画像后，系统将匹配适合你的产业方向'}
            </div>
          )}

          {/* Direction confirm */}
          {directions.length > 0 && (
            <div className={styles.confirmBar}>
              <motion.button
                type="button"
                className={styles.confirmBtn}
                disabled={
                  selectedDirection === null ||
                  directionState === 'CONFIRMED' ||
                  profileDirty
                }
                whileTap={selectedDirection !== null && directionState !== 'CONFIRMED' && !profileDirty ? { scale: 0.96 } : undefined}
                onClick={() => onConfirm('direction')}
              >
                {directionState === 'CONFIRMED'
                  ? '✓ 已确认'
                  : selectedDirection === null
                    ? '请先选择一个方向'
                    : '确认方向'}
              </motion.button>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  )
}

/* ── Score breakdown table ────────────────────────────────── */

const BREAKDOWN_ITEMS = [
  { label: '技能重叠', weight: 0.5, maxScore: 50 },
  { label: '经验匹配', weight: 0.2, maxScore: 20 },
  { label: '行业前景', weight: 0.15, maxScore: 15 },
  { label: '学习成本', weight: 0.15, maxScore: 15 },
]

function ScoreBreakdown({ score }: { score: number }) {
  return (
    <div className={styles.breakdown}>
      <span className={styles.detailLabel}>得分构成</span>
      <table className={styles.breakdownTable}>
        <thead>
          <tr>
            <th>维度</th>
            <th>得分</th>
            <th>权重</th>
          </tr>
        </thead>
        <tbody>
          {BREAKDOWN_ITEMS.map((b) => {
            const val = Math.round(score * b.weight)
            return (
              <tr key={b.label}>
                <td>{b.label}</td>
                <td>
                  {val}/{b.maxScore}
                </td>
                <td>{Math.round(b.weight * 100)}%</td>
              </tr>
            )
          })}
          <tr className={styles.breakdownTotal}>
            <td>综合</td>
            <td>{score}/100</td>
            <td>100%</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
