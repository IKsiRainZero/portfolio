import type { PanelId, PanelState } from '../types'

export interface MockProfile {
  summary: string
  strength: string
  weakness: string
  suggestion: string
  skills: { name: string; category: 'language' | 'framework' | 'tool' | 'soft' }[]
  completeness: number
  experience: string
}

export interface MockDirection {
  name: string
  matchScore: number
  reason: string
  overlaps: string[]
  gaps: string[]
  outlook: 'growing' | 'stable' | 'declining'
}

export interface MockGapItem {
  skill: string
  priority: 'high' | 'medium' | 'low'
  difficulty: 'easy' | 'moderate' | 'hard'
  estHours: number
  reason: string
}

export interface MockPhase {
  title: string
  duration: string
  difficulty: string
  modules: string[]
  outcome: string
}

export interface MockAction {
  text: string
  estTime: string
  priority: 'high' | 'medium' | 'low'
  done: boolean
}

// -- State-derived mock selection --
export function getMockState(pid: PanelId): PanelState {
  const order = ['profile', 'direction', 'gap', 'source', 'path', 'action']
  const idx = order.indexOf(pid)
  if (idx <= 0) return 'READY_FOR_REVIEW'
  if (idx <= 2) return 'READY_FOR_REVIEW'
  return 'EMPTY'
}

export function getMockPayload(pid: PanelId): Record<string, unknown> {
  switch (pid) {
    case 'profile': return mockProfilePayload
    case 'direction': return mockDirectionPayload
    case 'gap': return mockGapPayload
    case 'path': return mockPathPayload
    case 'action': return mockActionPayload
    default: return {}
  }
}

// -- Baseline profile for radar chart --
export const baselineProfile: { language: number; framework: number; tool: number; soft: number } = {
  language: 80,
  framework: 75,
  tool: 85,
  soft: 60,
}

// Lookup: which directions reference a given skill?
export function getRelatedDirections(skillName: string, directions: MockDirection[]): number[] {
  return directions
    .map((d, i) => (d.overlaps.includes(skillName) || d.gaps.includes(skillName) ? i : -1))
    .filter(i => i >= 0)
}

// Lookup: which skills does a given direction reference?
export function getRelatedSkills(directionIndex: number, directions: MockDirection[]): string[] {
  const d = directions[directionIndex]
  return d ? [...d.overlaps, ...d.gaps] : []
}

// -- Payloads --

const mockProfilePayload = {
  summary: '3年Python后端开发经验，精通FastAPI和PostgreSQL，有Docker和AWS部署经验。对AI/ML方向有强烈兴趣，自学过基础机器学习理论。',
  strength: 'Python和FastAPI经验深厚，有全栈开发基础，技术栈覆盖面广',
  weakness: 'ML框架经验不足，缺乏特征工程和模型部署的实战经验',
  suggestion: '优先补齐PyTorch和MLOps基础，通过1-2个端到端项目积累实战经验',
  skills: [
    { name: 'Python', category: 'language' },
    { name: 'JavaScript', category: 'language' },
    { name: 'SQL', category: 'language' },
    { name: 'FastAPI', category: 'framework' },
    { name: 'React', category: 'framework' },
    { name: 'PostgreSQL', category: 'tool' },
    { name: 'Docker', category: 'tool' },
    { name: 'AWS', category: 'tool' },
    { name: 'Git', category: 'tool' },
    { name: '系统设计', category: 'soft' },
    { name: '技术写作', category: 'soft' },
  ],
  completeness: 72,
  experience: '3年 · 后端为主 · 有全栈倾向',
} as MockProfile & Record<string, unknown>

const mockDirectionPayload = {
  directions: [
    {
      name: 'ML 基础设施工程师',
      matchScore: 78,
      reason: '你的Python和后端经验是ML工程化的核心能力。FastAPI可用于模型serving API，Docker/AWS是MLOps的基础设施基础。主要差距在ML框架和特征工程经验。',
      overlaps: ['Python', 'FastAPI', 'Docker', 'AWS', 'PostgreSQL'],
      gaps: ['PyTorch', '特征工程', 'A/B实验设计', '模型监控'],
      outlook: 'growing',
    },
    {
      name: '数据平台后端工程师',
      matchScore: 85,
      reason: '你的技术栈与数据平台需求高度吻合。FastAPI+PostgreSQL是数据API的经典组合，Docker和AWS经验可直接用于数据管道部署。',
      overlaps: ['Python', 'FastAPI', 'PostgreSQL', 'Docker', 'AWS', 'SQL'],
      gaps: ['Spark', '数据建模', 'Kafka'],
      outlook: 'growing',
    },
    {
      name: '全栈产品工程师',
      matchScore: 65,
      reason: '你有React基础和后端深度，适合产品型团队。但全栈路线竞争激烈，差异化不如前两个方向明显。',
      overlaps: ['Python', 'JavaScript', 'React', 'FastAPI', 'PostgreSQL'],
      gaps: ['TypeScript深度', 'CSS工程化', '移动端开发', '用户体验设计'],
      outlook: 'stable',
    },
  ],
} as Record<string, unknown>

const mockGapPayload = {
  mustLearn: [
    { skill: 'PyTorch基础', priority: 'high', difficulty: 'moderate', estHours: 80, reason: 'ML方向的核心框架，几乎所有模型开发都基于此' },
    { skill: 'MLOps基础', priority: 'high', difficulty: 'moderate', estHours: 60, reason: '模型部署和监控是ML工程师和普通后端的分水岭' },
    { skill: '特征工程', priority: 'high', difficulty: 'hard', estHours: 100, reason: '直接影响模型效果，需要实际项目积累' },
  ],
  recommend: [
    { skill: 'Kubernetes基础', priority: 'medium', difficulty: 'hard', estHours: 60, reason: '模型服务编排的工业标准' },
    { skill: 'A/B实验设计', priority: 'medium', difficulty: 'easy', estHours: 20, reason: '数据驱动的决策方法论' },
    { skill: 'Go语言', priority: 'low', difficulty: 'moderate', estHours: 60, reason: '高性能服务场景的备选方案' },
  ],
} as Record<string, unknown>

const mockPathPayload = {
  phases: [
    {
      title: '第一阶段：ML基础加固',
      duration: '4周',
      difficulty: '中等',
      modules: ['Python数据科学生态', 'PyTorch基础与实战', '经典ML算法回顾', '特征工程实践'],
      outcome: '能独立训练和评估常见模型',
    },
    {
      title: '第二阶段：工程化能力',
      duration: '6周',
      difficulty: '中高',
      modules: ['FastAPI模型服务化', 'Docker容器化部署', 'CI/CD流水线', '模型监控与日志'],
      outcome: '能搭建完整的ML服务 pipeline',
    },
    {
      title: '第三阶段：项目实战',
      duration: '8周',
      difficulty: '高',
      modules: ['端到端ML项目', '性能优化', 'A/B实验', '开源贡献或实习'],
      outcome: '有可展示的完整项目作品',
    },
  ],
} as Record<string, unknown>

export const defaultConclusionValues = {
  strength: 'Python和FastAPI经验深厚，有全栈开发基础，技术栈覆盖面广',
  weakness: 'ML框架经验不足，缺乏特征工程和模型部署的实战经验',
  suggestion: '优先补齐PyTorch和MLOps基础，通过1-2个端到端项目积累实战经验',
}

const mockActionPayload = {
  actions: [
    { text: '完成PyTorch官方60分钟入门教程', estTime: '1小时', priority: 'high', done: false },
    { text: '在Kaggle上完成一个Titanic入门比赛', estTime: '3小时', priority: 'high', done: false },
    { text: '搭建个人ML项目仓库(GitHub)', estTime: '30分钟', priority: 'high', done: false },
    { text: '阅读"ML系统设计"相关文章5篇', estTime: '2小时', priority: 'medium', done: false },
    { text: '注册并了解AWS SageMaker', estTime: '1小时', priority: 'medium', done: false },
    { text: '浏览目标公司JD，确认技能要求', estTime: '30分钟', priority: 'low', done: false },
  ],
} as Record<string, unknown>
