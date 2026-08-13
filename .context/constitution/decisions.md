# 架构决策记录 (ADR)

## ADR-001: 单仓库多项目
- **日期**: 2026-07-02
- **决策**: 所有项目（Crescent, cv-lab, 旧项目）放在同一个 Git 仓库下，按 products/experiments/archive/ 三级分类
- **理由**: 共享知识库、统一规范、简化上下文管理。各项目独立部署但共同演进
- **替代方案**: 每项目独立 repo（被否 — 共享知识碎片化、跨项目经验难复用）

## ADR-002: .context/ 三层知识架构
- **日期**: 2026-07-02
- **决策**: 采用工作空间级 .context/（共享）+ 项目级 .context/（专属）两层分离，每层内部按 constitution/reference/sessions 三层组织
- **理由**: AI 会话天然无状态，项目开发需要有状态积累。文件系统优先，版本化、模块化、可复用
- **来源**: 上下文工程（Context Engineering）方法论

## ADR-003: 手写 SVG 图表 vs 图表库
- **日期**: 2026-06-22
- **决策**: Crescent Workbench 图表组件手写 SVG（RadarChart, SkillTree, FilterTree, KnowledgeGraph, MatchPipeline）
- **理由**: 经过 3 个图表库试用后（Recharts, visx, nivo），发现定制需求（双层雷达图、递归树、管道图）远超库能力范围。手写 SVG + framer-motion 动画更可控
- **代价**: 新图表类型需从零实现，但复用模式已建立

## ADR-004: CSS Modules vs CSS-in-JS
- **日期**: 2026-06-20
- **决策**: 使用 CSS Modules + CSS 变量（variables.css 设计 token 系统）
- **理由**: 零运行时开销，与 Vite 原生集成，CSS 变量支持动态主题

## ADR-005: 知识库/ + docs/ + memory/ → .context/ 合并
- **日期**: 2026-07-02
- **决策**: 将三个分散的知识存放处合并为统一的 .context/ 体系
- **理由**: 消除碎片化，建立单一真相源。按"加载频率"而非"来源"分层
