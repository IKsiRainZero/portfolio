# may-i-help-u 架构

## 整体架构
```
mayihelpu/                          ← pip install may-i-help-u
├── __init__.py
│
├── context.py                      ← ProblemContext 共享上下文
│   └── ProblemContext              │   问题描述、子问题树、方案列表、资源清单、解决结果
│                                  │   贯穿所有器官的单一可信状态
│
├── decomposer.py                   ← 问题拆解器
│   └── Decomposer.decompose(ctx)  │   输入问题 → 输出结构化子问题树
│                                  │   每个子问题有：id, 依赖关系, 优先级, 可继续拆分标记
│                                  │   递归调用自己直到原子问题（不可再拆分）
│
├── analyzer.py                     ← 问题分析器
│   └── Analyzer.analyze(ctx)      │   输入问题 → 输出解决方案路径列表
│                                  │   每条路径有：方法, 可行性, 风险, 依赖项
│                                  │   可递归调用 Decomposer 把路径拆成子任务
│
├── coordinator.py                  ← 情报统筹器
│   └── Coordinator.gather(ctx)    │   输入问题+方案 → 检索外部资源
│   ├── web_search(query)          │   网络搜索 (Scrapling + LLM 结果提取)
│   ├── local_search(query)        │   本地向量检索 (ChromaDB sentence-transformers)
│   └── match(need, resources)     │   余弦相似度匹配 → 产出"可用的资源/技术"
│
├── solver.py                       ← 问题解决器
│   └── Solver.solve(ctx)          │   输入问题+方案+资源 → 执行解决
│   ├── tool_registry              │   可注册的工具集 (function calling, shell, browser)
│   ├── plan_execute(plan)         │   按计划逐步执行，记录每步结果
│   └── delegate(organ, ctx)       │   随时可调用拆解/分析/统筹器
│
└── orchestrator.py                 ← C 层：自治编排器（可选包装）
    └── Orchestrator.solve(goal)   │   内部自主决定 organ 调用顺序
                                   │   让 LLM 调度：先拆→再分析→需要更多信息则统筹→解决→循环
```

## 数据流 (B 层：自由编排)
```
调用者
  → ctx = ProblemContext(problem="...")
  → Decomposer.decompose(ctx)       // ctx.subproblems 被填充
  → Analyzer.analyze(ctx)            // ctx.solutions 被填充（读取 subproblems）
  → Coordinator.gather(ctx)          // ctx.resources 被填充（基于 solutions 搜索）
  → Solver.solve(ctx)                // ctx.result 被填充
  → ctx.summary()                    // 完整解决链路
```

## 数据流 (C 层：自治编排)
```
调用者
  → Orchestrator.solve("做一个股票预测模型")
    → LLM 判断：先拆解
      → Decomposer.decompose(ctx)
    → LLM 判断：子问题 1 需要分析
      → Analyzer.analyze(ctx, target=subproblem_1)
    → LLM 判断：方案涉及 LSTM → 搜索 LSTM 最新实现
      → Coordinator.gather(ctx, query="LSTM pytorch 2026 best practice")
    → LLM 判断：可以开始解决
      → Solver.solve(ctx)
    → return ctx
```

## 共享上下文结构
```
ProblemContext:
  problem: str                          # 原始问题
  subproblems: list[SubProblem]         # 拆解结果（树形）
  solutions: list[Solution]             # 分析结果（多路径）
  resources: list[Resource]             # 统筹结果（外部资源映射）
  result: SolveResult                   # 解决结果
  history: list[OrganCall]              # 调用链记录（可回溯）
```

## 设计原则
- 每个器官无状态 — 只读/写 ProblemContext，器官之间不直接耦合
- 可单独使用 — `Decomposer(...).decompose(ctx)` 不依赖其他器官
- 可递归 — Analyzer 可以 new 一个 Decomposer 来拆解自己的方案
- 工具可插拔 — Solver 的 tool_registry 可以注册任意 Python callable
