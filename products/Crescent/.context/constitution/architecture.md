# Crescent 架构

## 整体架构
```
main.py (FastAPI app)
├── routes/pages.py           ← 页面路由 (Jinja2 模板 + SPA fallback)
├── routes/api_workbench.py   ← Workbench SSE pipeline
├── routes/api_ai.py          ← AI proxy (DeepSeek)
├── routes/api_eval.py        ← 评估系统 (CRUD + 影子模式)
├── routes/api_*.py           ← 18 个 API 模块
├── services/                 ← 业务逻辑层
│   ├── docindex/             ← DocIndex 文档检索 (Resolver + L1/L2 index)
│   └── ...
├── frontend/                 ← React SPA (Vite)
│   └── src/
│       ├── components/       ← 组件
│       │   ├── blocks/       ← 内容块 (Profile, Direction, Gap, Path, Action)
│       │   ├── charts/       ← SVG 图表 (Radar, SkillTree, FilterTree, etc.)
│       │   └── pages/        ← 页面 (Welcome, Discover, Plan, Act)
│       ├── hooks/            ← useWorkbench, useSSE, usePageNavigation
│       ├── styles/           ← variables.css (设计 token)
│       └── utils/            ← api.ts, types.ts, mockContent.ts
└── static/                   ← 生产构建产物 (dist/)
```

## Workbench 数据流
```
FloatingInput (Cmd+J) 
  → useWorkbench.startSession(message) 
    → fetch POST /api/workbench/start 
      → SSE stream: profile→direction→gap→path→action
        → applyEvent() 更新 panelStates + panelPayloads
          → PageRouter 渲染对应页面
            → ResponseSheet 弹出结果
```

## 页面过渡
- `PageRouter.tsx` 使用 `<AnimatePresence mode="wait">` 编排页面切换
- 每页面 `motion.div` 带 spring physics (stiffness:80, damping:18)
- WelcomePage → DiscoverPage → PlanPage → ActPage

## 背景层
- `AmbientLight` — 跟随鼠标的径向渐变光源
- `FlowField` — Canvas 粒子流场 (requestAnimationFrame)
- `Spotlight` — SVG 聚光灯效果
