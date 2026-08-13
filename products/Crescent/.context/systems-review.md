# Crescent 系统诊断与重构评估

**日期**: 2026-07-03 | **版本**: v2.0 | **状态**: 待执行

## 一、概述

Crescent 从"个人学习伴侣"原型起步，经 3 个版本迭代，发展为包含 Workbench 职业匹配、评估系统、论文分析、面试模拟、简历审查、知识管理、SRS 调度、代码执行等 18 个功能模块的综合平台。

当前代码库呈现出**功能蔓延**、**模块耦合**、**流水线僵化**、**测试膨胀**四重症状。本文档对每个症状进行归因分析，对照 2026 年业界先进范式给出差距分析，提出具体可执行的重构方案。

## 二、症状诊断

### 2.1 巨型文件：职责真空

| 文件 | 行数 | 症状 | 归因 |
|------|------|------|------|
| `services/agent_service.py` | 1,841 | 单文件承载全部 Agent 行为（聊天、工具调用、prompt 管理、上下文组装） | 没有接口边界，"Agent"被当作万能筐 |
| `services/eval/eval_engine.py` | 1,493 | 评估引擎包含影子模式、评分、对比、报告生成 | eval 系统被当作独立产品开发，而非诊断工具 |
| `tests/test_eval_engine.py` | 2,092 | 单测文件行数超过被测模块 | 过度工程化：测试本身成为维护负担 |
| `frontend/components/pages/DiscoverPage.tsx` | 341 | 数据加载、方向选择、卡片展开、确认提交混在一个组件 | 页面组件承担了状态管理 + 业务逻辑 + 交互 |

**模式**: 当没有明确的模块边界时，代码向"最方便的地方"聚集。每个巨型文件都是一个**隐式模块**——没有任何接口定义，但事实上有自己的状态、生命周期和依赖。

### 2.2 功能蔓延：18 个路由模块

```
routes/
├── api_workbench.py     ← 核心 (188 行)
├── api_ai.py            ← AI 代理
├── api_eval.py          ← 评估 CRUD (484 行)
├── api_agent.py         ← Agent 管理 (454 行)
├── api_knowledge.py     ← 知识库 (306 行)
├── api_papers.py        ← 论文分析
├── api_exercises.py     ← 练习系统
├── api_interview.py     ← 模拟面试
├── api_resume.py        ← 简历审查
├── api_code.py          ← 代码执行
├── api_source_trace.py  ← 溯源
├── api_sync.py          ← 同步
├── api_tokens.py        ← Token 计费
├── api_progress.py      ← 进度追踪
├── api_impressions.py   ← 印象笔记
├── api_config.py        ← 配置
├── api_import.py        ← 导入
├── api_review.py        ← 复习
└── pages.py             ← 页面路由
```

**模式**: "先加上去再说"——每个功能独立开路由，但路由之间没有统一的认证/限流/日志/错误处理层。每增加一个路由，系统复杂度线性增长，但一致性非线性下降。

### 2.3 双重流水线

```
services/pipeline/ (16 文件)    services/workbench/ (9 文件)
├── orchestrator.py              ├── engine.py
├── intent_parser.py             ├── skill_matcher.py
├── plan_generator.py            ├── gap_analyzer.py
├── fetcher.py                   ├── industry_scanner.py
├── normalizer.py                ├── learning_path.py
├── dedup.py                     ├── next_action.py
├── credibility.py               ├── narrator.py
├── search.py                    ├── profile_store.py
├── resource_scanner.py          └── types.py
├── persistence.py
├── task_store.py
├── trace_logger.py
├── e2e.py
├── protocols.py
└── types.py
```

**模式**: pipeline 是先建的，workbench 是后加的。两者功能重叠（都在做"输入→处理→输出"），但没有共享接口。pipeline 偏"知识摄入"，workbench 偏"职业匹配"——但它们本该是**同一抽象的不同实例**。

### 2.4 评估系统膨胀

```
services/eval/ (7 文件, ~5,000+ 行)
├── eval_engine.py      1,493 行 ← 核心评估
├── eval_store.py         845 行 ← 存储层
├── meta_evaluator.py     726 行 ← 元评估
├── trace_logger.py       413 行 ← 全链路追踪
├── llm_judge.py          345 行 ← LLM 裁判
├── golden_dataset.py      ~80 行 ← 金标数据集
└── __init__.py
```

**模式**: 评估系统从"验证 Workbench 匹配质量"演变为"通用 RAG 评估框架"，成为一个**寄生产品**——它运行在 Crescent 内部，但功能完全独立，消耗大量开发资源而主产品用户无感知。

症状总结：
- **LLM Judge** — 用 LLM 评估 LLM 输出，递归且昂贵
- **Meta Evaluator** — 评估评估结果，二阶递归
- **Trace Logger** — 全链路 LLM 调用追踪，数据量线性增长
- **Golden Dataset** — 手工标注，维护成本高，覆盖场景有限

### 2.5 固定管道架构

Workbench 的 5 阶段流程被硬编码为：

```
Profile → Direction → Gap → Path → Action
```

每个阶段必须等前一个完成。没有：
- 跳步：用户说"我只要方向推荐"→ 做不到
- 回溯：Direction 结果不满意改 Profile → 做不到
- 旁路：直接指定方向跳过匹配 → 做不到
- 递归：Gap 分析发现新问题 → 不能返回到 Direction 重新匹配

这与 MayIhelpU 的自由编排模式形成对立——后者是 Crescent 问题的直接反思。

### 2.6 频繁技术切换

| 日期 | ADR | 决策 | 试过又放弃 |
|------|-----|------|-----------|
| 06-10 | C05 | 文件系统存储 | (未尝试数据库) |
| 06-15 | C03 | SSE | WebSocket 评估 |
| 06-20 | C02 | CSS Modules | CSS-in-JS 评估 |
| 06-22 | C01 | 手写 SVG | Recharts, visx, nivo 均已安装试用后删除 |
| 07-02 | C04 | framer-motion | CSS transition 方案评估 |

**模式**: 5 个 ADR 在 12 天内做出，其中 3 个涉及"先试用→再否决"的循环。这不是错——探索本来就是这样的。但它说明**项目初期缺少方向锚点**，导致每个技术决策都要自己踩一遍。

### 2.7 测试膨胀

```
tests/
├── test_eval_engine.py        2,092 行 ← 单文件最长
├── test_eval_core.py          1,209 行
├── test_eval_api.py             720 行
├── eval/                         独立目录
├── pipeline/                  14 个测试文件
├── workbench/                  8 个测试文件
└── docindex/                   4 个测试文件
```

**模式**: 测试数量与被测代码行数正相关，而非与"出问题的概率"相关。eval 系统的测试是 workload 最大的——恰恰是用户最不需要的功能。

## 三、结构性问题归因

以上症状的共同根因：

1. **没有模块接口** — 每个 `.py` 文件都是独立王国，`import` 是唯一的连接方式。没有 protocol/interface/ABC 定义模块契约。
2. **功能即路由** — "加功能 = 加路由"的默认模式，没有功能生命周期管理（添加→验证→保留/删除）。
3. **评估系统寄生** — 评估从诊断工具演变为独立产品，消耗资源与主产品功能不成比例。
4. **管道硬编码** — 步骤顺序写死在代码里，缺乏编排抽象层。
5. **缺乏功能开关** — 要么全有要么全无，无法按场景启用/禁用模块集。

## 四、业界范式对标

### 4.1 模块化设计：Crescent vs. SKILL 架构

2026 年业界在模块化 Agent 设计上形成了共识：**SKILL 架构**通过原子化拆分（单一职责）和标准化封装（统一 Schema、触发、依赖），将功能模块化为可独立开发、测试、复用、迭代的单元。每个 SKILL 单元包含五要素：输入校验、核心逻辑、输出校验、触发规则、依赖声明。

**Crescent 的差距**：
- "器官化"构想方向正确，但缺乏**标准化接口契约**——当前模块之间通过 `import` 随意连接，没有 Protocol/ABC 定义
- "通过共享 Context 对象交换数据"方向对，但未定义 Context 的 Schema——这会导致新的隐式耦合（见 5.8.1 Context 设计约束）
- SKILL 架构要求"每个技能单元必须有边界清晰、独立运行、可单独迭代"，当前 Workbench 器官尚未达到这个颗粒度

**决策**: 采纳 SKILL 架构的五要素标准，为每个器官定义明确的输入/输出 Schema、触发条件和依赖声明。

### 4.2 编排范式：固定管道 vs. Graph-based Orchestration

"固定管道架构"（Profile → Direction → Gap → Path → Action 硬编码）是整个系统最核心的结构性问题。

2026 年学术界对此有明确结论：**ReAct 不应作为 Agent 的默认架构**，应采用 **Plan-Then-Execute 范式**——在观察运行时内容之前，先承诺一个任务特定的执行计划。DAG Plan-and-Execute 在小规模下提供更高的精度和结构化并行能力。2026 年主流 Agent 设计模式已演进为五种命名形状：ReAct、Plan-Then-Execute、Supervisor、Graph 等。

**Crescent 的差距**：
- 管道是**顺序硬编码**，连 Plan-Then-Execute 都不如——后者至少分离了规划与执行
- 想要的"跳步、回溯、旁路、递归"能力，本质上是 **Graph 模式**（带类型的状态图）——节点是执行单元，边是数据流和路由逻辑
- 2026 年主流编排框架（Microsoft Agent Framework、LangGraph、AutoGen、CrewAI）都支持基于图的工作流编排。Microsoft Agent Framework 的心智模型正是**数据流**——将执行者定义为节点，以类型安全的边连接它们，提供图级别的检查点机制

**决策**: 放弃"管道"思维，采用 **Graph-based Orchestration**。将每个器官定义为图中的节点，边定义数据流向和路由条件——跳步、回溯、旁路、递归都是图遍历的自然结果。

### 4.3 评估系统：从寄生产品到诊断工具

评估系统"从验证工具演变为独立产品"的问题在 2026 年业界有明确定位：评估系统应作为**质量评测、数据观测能力**存在于开发和运维层，而非面向用户的产品功能。

前沿思路参考 **AgentDevel**——将 Agent 的迭代优化视为"发布工程"流程，通过执行追踪产生症状级质量信号，通过可执行诊断合成发布候选版本。

**Crescent 的差距**：
- 将 eval 系统暴露为 API 路由（`/api/eval/*`），这是架构层级错误——诊断工具不应有产品级 API
- LLM Judge + Meta Evaluator 的二阶递归是典型的**过度工程化**——评估的评估消耗资源但收益递减
- Golden Dataset 手工标注维护成本高，2026 年更倾向于**基于执行轨迹的自动信号采集**

**决策**: 将 eval 系统降级为 **Dev/Staging 环境的诊断插件**，移除产品路由，保留核心能力（影子模式、质量信号采集）作为开发工具链的一部分。

## 五、重构方案

### 5.0 前置步骤：功能退役决策

**在拆分前，先做功能优先级分类。** 当前方案把 18 个模块全部保留只是换了组织形式——如果某个功能用户触及率很低，继续"器官化"它只会把腐烂的代码移植到新架构里。

| 优先级 | 标准 | 动作 |
|--------|------|------|
| **Must-have** | 月活用户 > 10% 或属核心闭环 | 按 SKILL 标准完整拆分 |
| **Nice-to-have** | 月活 2%-10% 或有战略价值 | 保留代码，仅定义接口，不深度重构 |
| **Deprecate** | 月活 < 2% 且无战略意义 | 移除路由，归档代码，不进入新架构 |

此分类需在 Phase 1 基础设施搭建完成后、器官拆分启动前完成。功能生命周期管理（入口条件、出口条件、退役条件、使用计数）应前置到此刻。

### 5.1 架构目标

从"单体 Agent"到**基于图编排的模块化 Agent 系统**，符合 2026 年业界对生产级 Agent 系统的定义——有能力、有工具、可托管、可互联、可观测。

### 5.2 新架构蓝图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Orchestration Layer                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Workflow Graph (DAG)                       │   │
│  │  [Profile] → [Direction] → [Gap] → [Path] → [Action]  │   │
│  │       ↕           ↕          ↕         ↕               │   │
│  │    [跳步]      [回溯]     [旁路]    [递归]             │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                       SKILL Layer                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Profile  │ │  Skill   │ │   Gap    │ │   Path   │        │
│  │  Store   │ │ Matcher  │ │ Analyzer │ │ Planner  │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │  Action  │ │  Chat    │ │Knowledge │ │  Paper   │        │
│  │  Engine  │ │Orchestr. │ │  Index   │ │ Pipeline │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────────────────────┤
│                   横切关注点 (Cross-Cutting)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │  可观测性 │ │ 功能开关 │ │ 评估诊断 │ │ 模块版本 │        │
│  │ (Tracing) │ │ (Flags)  │ │ (Eval)   │ │ (Version)│        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 SKILL 接口协议

每个 SKILL 单元遵循五要素标准：

```python
from typing import Protocol, Any, Dict, List
from dataclasses import dataclass

@dataclass
class SkillInput:
    """输入校验：定义和验证输入参数的类型、格式、必填项"""
    schema: Dict[str, Any]

@dataclass
class SkillOutput:
    """输出校验：验证并格式化输出结果"""
    schema: Dict[str, Any]

class Skill(Protocol):
    """每个 SKILL 单元 = 输入校验 + 核心逻辑 + 输出校验 + 触发规则 + 依赖声明"""

    @property
    def input_schema(self) -> SkillInput: ...

    @property
    def output_schema(self) -> SkillOutput: ...

    @property
    def trigger_rules(self) -> List[str]: ...

    @property
    def dependencies(self) -> List[str]: ...

    async def execute(self, input: Dict[str, Any]) -> Dict[str, Any]: ...
```

### 5.4 图编排引擎

将硬编码的 5 阶段管道替换为基于图的自由编排（参考 Microsoft Agent Framework 的数据流模型）：

```python
workflow = Graph()
workflow.add_node("profile", ProfileStoreSkill())
workflow.add_node("direction", SkillMatcherSkill())
workflow.add_node("gap", GapAnalyzerSkill())
workflow.add_node("path", PathPlannerSkill())
workflow.add_node("action", ActionEngineSkill())

# 正向边
workflow.add_edge("profile", "direction")
workflow.add_edge("direction", "gap")
workflow.add_edge("gap", "path")
workflow.add_edge("path", "action")
# 回溯边
workflow.add_edge("gap", "direction", condition=lambda ctx: ctx.needs_reprofile)
# 跳步边
workflow.add_edge("profile", "action", condition=lambda ctx: ctx.skip_all)
```

| 能力 | 当前（硬编码管道） | 重构后（图编排） |
|------|-------------------|------------------|
| 跳步 | 不支持 | 条件边跳过中间节点 |
| 回溯 | 不支持 | 条件边回到上游节点 |
| 旁路 | 不支持 | 并行分支 + 汇合 |
| 递归 | 不支持 | 循环边（有终止条件） |
| 并行 | 串行执行 | 扇出/扇入边 |

### 5.5 器官化拆分

| 原文件 | 拆分后 | 说明 |
|--------|--------|------|
| `services/agent_service.py` (1,841行) | `skills/chat_orchestrator/` + `skills/tool_registry/` + `skills/prompt_manager/` | 每个 SKILL 独立，通过图编排层调度 |
| `services/pipeline/` (16文件) | `skills/knowledge_index/` + `skills/paper_pipeline/` | 合并重叠功能，统一为 SKILL 接口 |
| `services/workbench/` (9文件) | `skills/profile_store/` + `skills/skill_matcher/` + `skills/gap_analyzer/` + `skills/path_planner/` + `skills/action_engine/` | 每个器官一个 SKILL，通过图编排连接 |
| `services/eval/` (7文件, ~5,000行) | `tools/diagnostics/eval_engine/` | **移除产品路由**，降级为开发诊断工具 |
| `routes/*.py` (18个路由) | 统一为 `api/v1/` + 功能开关控制 | 路由层只做协议转换，业务逻辑下沉到 SKILL |

**拆分原则**：
- 每个 SKILL 遵循单一职责，边界清晰
- SKILL 之间不互相 import，只通过图编排层调度
- 每个 SKILL 可独立测试（mock 依赖）

### 5.6 前端收敛

| 当前 | 重构后 | 说明 |
|------|--------|------|
| `pages/` (5个页面) | `pages/Input/` + `pages/Result/` + `pages/Trace/` | 精简为 3 个核心视图 |
| `blocks/` (5个) | 保留，作为 Result 页面的子组件 | 数据展示层 |
| `charts/` (5个手写SVG) | **提取为独立 NPM 包** `@crescent/charts` | 核心资产，跨项目复用 |
| 其他 15 个装饰组件 | 保留，不重构 | 低优先级 |

### 5.7 数据迁移与 API 兼容

- `/api/eval/*` 移除前，确认无前端/外部调用方依赖
- 旧 pipeline 和 workbench 产生的持久化数据（任务、评估报告、技能分析），新 SKILL 架构需提供无损迁移路径
- **新旧 API 并行运行至少一个版本**（如 `/api/v0/` 保留过渡期），功能开关控制路由灰度

### 5.8 横切关注点设计

#### 5.8.1 Context 设计约束

SKILL 通过共享 Context 交换数据，但必须防止从 import 耦合变成数据结构耦合：
- Context 应为**不可变快照 + 明确输出字段**
- 每个节点只读取自己声明的依赖字段，输出新字段，而非就地修改
- Context Schema 需在 Phase 1 定义，与 SKILL 协议同步确定

#### 5.8.2 功能开关粒度

功能开关不仅是路由层开关，需要在 SKILL 调度时生效。例如"PathPlanner 新算法"可通过开关选择旧 SKILL 或新 SKILL 实现。**开关需与图节点注册机制结合**——同一个图节点位置可替换不同 SKILL 实现。

#### 5.8.3 SKILL 健康检查

评估系统降级为诊断工具后，仍需要验证 SKILL 的输出质量。用一个极简的"器官健康检查"钩子，在 CI 中运行（输入/输出 schema 校验 + 关键分支断言），而非复杂的 LLM Judge。

### 5.9 测试策略重构

拆分巨型文件后，如果沿用旧的"全量集成测试 + 巨型 mock"方式，测试文件数会从 30+ 暴涨到 60+。需同步建立测试金字塔：

| 层级 | 范围 | 说明 |
|------|------|------|
| **单元测试** | 每个 SKILL | 纯逻辑 mock 依赖，覆盖核心分支 |
| **契约测试** | SKILL 边界 | 验证输入/输出 schema 符合接口协议 |
| **集成测试** | 图编排关键路径 | 只测正向 5 步等关键路径，不测所有排列组合 |

废弃 `test_eval_engine.py` 风格的大文件测试。

## 六、实施路线图

```
Phase 0 (前置):  功能退役决策
                 ├── 统计各功能使用频率
                 ├── Must-have / Nice-to-have / Deprecate 分类
                 └── 退役模块：移除路由，归档代码

Phase 1 (Week 1-2):  基础设施
                      ├── 定义 SKILL 接口协议
                      ├── 建立图编排引擎（MVP）
                      ├── 建立可观测性基础设施（请求ID、耗时、Token、错误率）
                      ├── 建立功能开关系统
                      └── 写入 ADR（架构决策记录）

Phase 2 (Week 3-6):  器官化拆分（并行，每个 SKILL 独立）
                      ├── 拆分 agent_service.py → 3 个 SKILL
                      ├── 合并 pipeline/ + workbench/ → 5 个 SKILL
                      └── eval/ → 降级为诊断工具（移除路由）

Phase 3 (Week 7-9):  编排层重构
                      ├── 将 5 阶段管道迁移到图编排
                      ├── 实现跳步/回溯/旁路/递归
                      ├── 流量复制：新旧流程并行运行，对比输出
                      └── 灰度验证（功能开关控制新旧流程）

Phase 4 (Week 10-11): 前端收敛
                       ├── 精简页面为 3 个核心视图
                       └── 提取 charts 为独立 NPM 包

Phase 5 (Week 12):    全量切换 + 文档化
                       ├── 功能开关全量放开
                       ├── 回滚演习确认
                       ├── 更新 AGENTS.md / .context/
                       └── 归档旧代码（保留 2 周回滚窗口）
```

### 风险治理

| 风险 | 严重程度 | 缓解措施 |
|------|----------|----------|
| **无功能开关** — 新功能全量发布，无法灰度/A/B/回滚 | 🔴 高 | Phase 1 建立 Flag 基础设施，与图节点注册结合 |
| **架构漂移** — 新引入的图编排引擎、SKILL 协议本身可能又被替换 | 🟡 中 | 在 `.context/constitution/decisions.md` 写入 ADR；CI 中禁止 SKILL 之间直接 import |
| **无可观测性基线** — Trace Logger 是 eval 子系统而非横切关注点 | 🟡 中 | Phase 1 建立独立于 eval 的全链路可观测性 |
| **无模块版本管理** — 模块变化时无法判断下游影响 | 🟡 中 | SKILL 注册时声明版本号，图编排层校验依赖兼容性 |
| **本地开发体验恶化** — 十几个独立 SKILL 包后难以一键启动 | 🟡 中 | 统一 `dev` 编排脚本或 docker-compose |

## 七、与上下文工程架构的衔接

| 上下文工程层 | 对应重构产出 |
|-------------|-------------|
| `constitution/tech-stack.md` | 记录新架构的技术选型（图编排引擎、SKILL 接口协议） |
| `constitution/decisions.md` | 记录 ADR：为何从管道迁移到图编排、为何降级 eval |
| `modules/[器官名]/` | 每个 SKILL 的 README（功能描述、接口 Schema、依赖关系） |
| `sessions/` | 每个器官拆分的会话记录和复盘 |

## 八、总结

Crescent 当前的架构问题，本质上是**从"原型"到"生产级系统"的成长痛**。核心策略：

1. **先退役再拆分** — 按用户触及率分类，不把腐烂代码移植到新架构
2. **用 SKILL 架构解决模块耦合** — 每个器官有标准化的输入/输出/触发/依赖
3. **用 Graph-based Orchestration 解决管道僵化** — 跳步、回溯、旁路、递归都是图遍历的自然结果
4. **用评估降级 + 测试金字塔解决测试膨胀** — 诊断工具不应有产品级 API，拆分后测试分三层
5. **用功能开关 + 可观测性 + 架构守护解决部署风险** — 灰度发布、全链路追踪、CI 契约校验

---

本文件应伴随每次重构迭代更新。每个 Phase 完成后在此记录：
- 完成日期、产出清单、未达预期的项目、是否引入新依赖
