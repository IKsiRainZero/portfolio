import { useState } from 'react'
import { motion } from 'framer-motion'
import type { MockProfile } from '../../data/mockContent'
import { baselineProfile, defaultConclusionValues } from '../../data/mockContent'
import RadarChart from '../charts/RadarChart'
import styles from './ProfileEditor.module.css'

interface ProfileEditorProps {
  profile: MockProfile | null
  onProfileChange: (p: MockProfile) => void
  onConfirm: () => void
  confirmed: boolean
}

const RADAR_DIM_LABELS: Record<string, string> = {
  language: '语言覆盖 4/5 后端关键场景',
  framework: '框架广度 覆盖 2/3 主流框架',
  tool: '工具链完整 部署+数据库+版本控制',
  soft: '软技能 系统设计 + 技术写作',
}

export default function ProfileEditor({ profile, onProfileChange, onConfirm, confirmed }: ProfileEditorProps) {
  const [editingConclusion, setEditingConclusion] = useState<string | null>(null)

  if (!profile) {
    return <div className={styles.empty}>等待能力画像数据…</div>
  }

  // Radar values (mock computation from profile data)
  const skills = profile.skills || []
  const userValues = {
    language: Math.min(100, skills.filter((s) => s.category === 'language').length * 25),
    framework: Math.min(100, skills.filter((s) => s.category === 'framework').length * 30),
    tool: Math.min(100, skills.filter((s) => s.category === 'tool').length * 20),
    soft: Math.min(100, skills.filter((s) => s.category === 'soft').length * 40),
  }

  const handleDeleteSkill = (name: string) => {
    onProfileChange({ ...profile, skills: skills.filter((s) => s.name !== name) })
  }

  const handleAddSkill = (name: string, category: MockProfile['skills'][number]['category']) => {
    if (skills.some((s) => s.name === name)) return
    onProfileChange({ ...profile, skills: [...skills, { name, category }] })
  }

  return (
    <div className={styles.panel}>
      {/* Radar + Completeness */}
      <div className={styles.topRow}>
        <RadarChart userValues={userValues} baselineValues={baselineProfile} animated />
        <div className={styles.completenessBars}>
          {Object.entries(userValues).map(([key, val]) => (
            <div key={key} className={styles.barRow}>
              <span className={styles.barLabel}>{key === 'language' ? '语言' : key === 'framework' ? '框架' : key === 'tool' ? '工具' : '软技能'}</span>
              <div className={styles.barTrack}>
                <div
                  className={styles.barFill}
                  style={{
                    width: `${val}%`,
                    backgroundColor: val < 40 ? 'var(--cr-red)' : val < 70 ? 'var(--cr-accent)' : 'var(--cr-green)',
                  }}
                />
              </div>
              <span className={styles.barVal}>{val}%</span>
              <span className={styles.barHint}>{RADAR_DIM_LABELS[key]}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Skill tags */}
      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>技能标签</h3>
        <div className={styles.tags}>
          {skills.map((s) => (
            <span key={s.name} className={`${styles.tag} ${styles[`cat_${s.category}`]}`}>
              {s.name}
              <button className={styles.tagDel} onClick={() => handleDeleteSkill(s.name)}>×</button>
            </span>
          ))}
        </div>
        {/* Add skill form */}
        <AddSkillForm onAdd={handleAddSkill} />
      </div>

      {/* Analysis conclusions */}
      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>分析结论</h3>
        {(['strength', 'weakness', 'suggestion'] as const).map((field) => (
          <div key={field} className={styles.conclusionRow}>
            <span className={styles.conclusionLabel}>
              {field === 'strength' ? '强项' : field === 'weakness' ? '弱项' : '建议'}
            </span>
            {editingConclusion === field ? (
              <textarea
                className={styles.conclusionInput}
                defaultValue={profile[field] || ''}
                onBlur={(e) => {
                  onProfileChange({ ...profile, [field]: e.target.value })
                  setEditingConclusion(null)
                }}
                autoFocus
              />
            ) : (
              <p
                className={styles.conclusionText}
                onClick={() => setEditingConclusion(field)}
              >
                {profile[field] || '点击编辑…'}
              </p>
            )}
          </div>
        ))}
        <button
          className={styles.resetBtn}
          onClick={() => onProfileChange({ ...profile, ...defaultConclusionValues })}
        >
          重置为系统原文
        </button>
      </div>

      {/* Confirm */}
      <div className={styles.confirmBar}>
        <motion.button className={styles.confirmBtn} onClick={onConfirm} disabled={confirmed}
          whileTap={!confirmed ? { scale: 0.96 } : undefined}>
          {confirmed ? '✓ 已确认' : '确认画像'}
        </motion.button>
      </div>
    </div>
  )
}

function AddSkillForm({ onAdd }: { onAdd: (name: string, cat: MockProfile['skills'][number]['category']) => void }) {
  const [name, setName] = useState('')
  const [cat, setCat] = useState<MockProfile['skills'][number]['category']>('language')

  return (
    <div className={styles.addForm}>
      <input placeholder="技能名…" value={name} onChange={(e) => setName(e.target.value)}
        className={styles.addInput} />
      <select value={cat} onChange={(e) => setCat(e.target.value as MockProfile['skills'][number]['category'])}
        className={styles.addSelect}>
        <option value="language">语言</option>
        <option value="framework">框架</option>
        <option value="tool">工具</option>
        <option value="soft">软技能</option>
      </select>
      <button onClick={() => { if (name.trim()) { onAdd(name.trim(), cat); setName('') } }}
        className={styles.addBtn}>
        添加
      </button>
    </div>
  )
}
