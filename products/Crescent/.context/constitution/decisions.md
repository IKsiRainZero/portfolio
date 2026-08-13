# Crescent 架构决策

## ADR-C01: 手写 SVG 图表 vs 图表库
- **日期**: 2026-06-22
- **决策**: 全部 Workbench 图表手写 SVG
- **理由**: 试用 Recharts/visx/nivo 后发现定制需求（双层雷达、递归技能树、匹配管道图）远超库能力。手写 SVG + framer-motion 更可控
- **代价**: 新图表类型从零实现

## ADR-C02: CSS Modules vs CSS-in-JS
- **日期**: 2026-06-20
- **决策**: CSS Modules + CSS 变量设计 token
- **理由**: 零运行时开销，Vite 原生集成，变量支持动态主题

## ADR-C03: SSE vs WebSocket
- **日期**: 2026-06-15
- **决策**: Workbench pipeline 用 SSE
- **理由**: 单向数据流（server→client），无需双向通信。SSE 更简单，HTTP 原生支持，不需要额外库
- **代价**: 断线重连需手动处理

## ADR-C04: framer-motion vs CSS transition
- **日期**: 2026-07-02
- **决策**: 页面过渡 + 组件动画用 framer-motion
- **理由**: AnimatePresence 自动管理 exit 动画（CSS 做不到），variants + staggerChildren 替代手写 nth-child delay，spring physics 替代手动 cubic-bezier

## ADR-C05: 文件系统存储 vs 数据库
- **日期**: 2026-06-10
- **决策**: 全部数据用文件系统（JSONL/JSON/Markdown），不引入数据库
- **理由**: 单用户、数据量小、Git 友好、零部署依赖
- **代价**: 并发写入无保护（单用户场景可接受）

## ADR-C06: SKILL 模块协议 vs 裸 import
- **日期**: 2026-07-04
- **决策**: 所有可拆分功能模块采用 SKILL 架构（五要素标准：输入校验、核心逻辑、输出校验、触发规则、依赖声明），通过 Protocol/ABC 定义契约
- **理由**: 系统诊断发现 18 个路由模块通过 `import` 随意连接，没有模块边界。SKILL 架构是 2026 年业界共识——每个技能单元边界清晰、独立可测、可单独迭代。器官之间不互相 import，只通过图编排层调度
- **代价**: 每个模块需额外定义接口协议（~20行/模块），但在巨型文件拆分中这笔开销可忽略

## ADR-C07: Graph-based Orchestration vs 固定管道
- **日期**: 2026-07-04
- **决策**: Workbench 的硬编码 5 阶段管道（Profile→Direction→Gap→Path→Action）改为基于 DAG 的图编排引擎
- **理由**: 2026 年学术界明确结论——ReAct 不应作为 Agent 默认架构，应采用 Plan-Then-Execute/Graph 范式。硬编码管道无跳步/回溯/旁路/递归能力，图编排将这些变为图遍历的自然结果。直接对齐 MayIhelpU 的 B 层自由编排设计
- **代价**: 图执行路径复杂度高于线性管道，需 BFS 遍历、回边限流、条件边等额外逻辑

## ADR-C08: 评估系统降级 vs 保留产品级 API
- **日期**: 2026-07-04
- **决策**: 将 eval 系统从产品功能降级为 Dev/Staging 环境的诊断插件，移除 `/api/eval/*` 路由，保留影子模式和 CI 健康检查
- **理由**: eval 系统演变为寄生产品（7 文件 ~5,000 行），LLM Judge + Meta Evaluator 的二阶递归是过度工程化。2026 年业界定位：评估应作为开发工具链，非面向用户产品。用户无感知，开发资源消耗不成比例
- **代价**: 丢失生产环境的 LLM 输出质量监控，需 CI 中的契约测试补偿

## ADR-C09: 功能开关基础设施 vs 全量发布
- **日期**: 2026-07-04
- **决策**: 在重构启动前建立 FeatureFlags 基础设施，支持全局 + per-SKILL 粒度的开关，与图节点注册机制结合
- **理由**: 系统诊断发现 18 个模块功能无生命周期管理。"先加上去再说"的模式导致功能蔓延。开关系统在 Phase 1 建立后，后续器官拆分和新旧流程灰度切换都有基础。同一图节点位置可通过开关选择不同 SKILL 实现
- **代价**: 每个受控路径需额外判断 `is_enabled()`，增加微量复杂度

## ADR-C10: 可观测性作为横切关注点 vs 子系统
- **日期**: 2026-07-04
- **决策**: 可观测性（请求ID、耗时、Token、错误率）作为独立于业务模块的横切层，不依附于 eval 系统
- **理由**: 旧架构中 Trace Logger 是 eval 子系统的一部分，导致可观测性随着 eval 降级一同消失。生产级 Agent 系统需要独立的可观测性基础设施。图编排引擎的 execute() 自动为每个节点创建 Span 并聚合到 Metrics
- **代价**: 内存指标在进程重启后丢失（当前 MVP 范围可接受，持久化后续再加）

## ADR-C11: 绞杀者模式合并 pipeline/ + workbench/ → 5 个 SKILL + eval 降级
- **日期**: 2026-07-04
- **决策**: pipeline/ 和 workbench/ 的 26 个模块不逐一重建为独立 SKILL，而是按业务边界合并为 5 个 SKILL 包装器（research_pipeline / profile_engine / gap_analyzer / path_engine / workbench_engine），均通过绞杀者模式委托给现有代码。eval/ (7 files, ~5,000 行) 降级为 tools/diagnostics/，只保留 CI 可用的 SkillHealthCheck schema 校验
- **理由**: 逐一拆分 26 个模块会创造大量低价值包装代码。pipeline 和 workbench 内部已有 orchestrator 级入口点，适合作为一个 SKILL 单元。eval 的产品级 API 路由已在 Phase 0 移除，过度工程化的 LLM Judge + Meta Evaluator 作为参考代码保留但不导入。SkillHealthCheck 提供 CI 门禁用 schema 验证，不依赖 LLM
- **代价**: 5 个 SKILL 的 execute() 方法内仍做 lazy construction（ProfileStore 需密码/路径），生产环境应由依赖注入容器管理。eval 旧代码（test_eval_engine.py 等）仍占用磁盘空间但在 pytest.ini 中被排除

