# Workbench 模块

## 数据流
```
useWorkbench (hooks/useWorkbench.ts)
├── startSession(message) → POST /api/workbench/start
├── sendResponse(message) → POST /api/workbench/respond
├── panelStates: Record<PanelId, PanelStatus>  ← 'idle' | 'loading' | 'streaming' | 'done' | 'error'
├── panelPayloads: Record<PanelId, any>         ← SSE payload 累积
├── sessionId: string | null
└── messages: Message[]                          ← 对话历史
```

## SSE 事件协议
```
event: panel_update
data: {"panel": "profile", "status": "streaming", "payload": {...}}

event: panel_complete
data: {"panel": "profile", "payload": {...}}

event: error
data: {"panel": "profile", "error": "..."}

event: done
data: {"session_id": "..."}
```

## Panel 管道顺序
1. `profile` — 技能画像 (SkillTree, RadarChart)
2. `direction` — 职业方向匹配 (DirectionBlock, FilterTree, MatchPipeline)
3. `gap` — 技能差距分析 (GapBlock, KnowledgeGraph)
4. `path` — 学习路径 (PathBlock, 时间线)
5. `action` — 行动计划 (ActionBlock, 勾选 + 进度)

## 页面路由 (usePageNavigation)
```
page = derive(sessionId, panelStates):
  null       → 'welcome'
  profile    → 'discover'
  gap/path   → 'plan'
  action     → 'act'
```

## 关键文件
- `hooks/useWorkbench.ts` — 核心状态管理
- `hooks/useSSE.ts` — SSE 连接 + 重连
- `hooks/usePageNavigation.ts` — 页面派生
- `components/pages/PageRouter.tsx` — AnimatePresence 页面过渡
- `components/FloatingInput.tsx` — Cmd+J 打开对话输入
- `components/ResponseSheet.tsx` — 阶段性结果弹出
- `utils/mockContent.ts` — Mock 数据（开发/调试用）
