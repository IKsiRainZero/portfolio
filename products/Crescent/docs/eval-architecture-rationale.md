# Eval 系统架构论证: 从归零原则到自指闭环

> **文档用途:** 团队会议讨论 — 理解 eval 系统"为什么必须存在"、解决了什么问题、自进化方向
> **写作日期:** 2026-06-11
> **覆盖代码:** `services/eval/` (6 modules, ~1,600 lines), `routes/api_eval.py`, `static/js/modules/eval-*.js`
> **对应 Phase:** 1-4 完整实现

---

## 1. 归零推演: 为什么评估系统必须存在

### 1.1 归零问题

把评估系统从代码库中删掉，回到没有它的状态，然后追问:

> 一个持续演进的软件系统，在没有评估机制的情况下，会发生什么？

答案分三层:

**第一层 — 不可见性:** 每次 commit、每次配置变更、每次数据迁移，系统的行为都在变化。但没有评估，这些变化是**不可见的**。你改了代码，你"觉得"它在变好，但你不知道。

**第二层 — 不可归因:** 当系统出问题时，你只能追溯到"最近改了什么"，但无法回答"这个改动让哪个指标从多少变成了多少"。没有基线，归因就是猜。

**第三层 — 不可自省:** 最致命的一层。如果连"有哪些指标"、"这些指标是否还适用"、"评估系统自身是否正常运行"都无法回答，那么这个系统就是在**凭信仰运行**，而非凭证据。

这三层问题不是"未来可能发生"的风险——它们是**正在发生的熵增**。eval 系统的存在意义不是"增加一个功能"，而是**为代码库安装了一套感官系统**。

### 1.2 归零结论

```
没有 eval 系统 → 变更不可见 → 效果不可归因 → 方向不可判断
有 eval 系统   → 变更可见   → 效果可归因
                     → [前提: 评估结果经过交叉验证且自指健康]
                     → 方向可判断 → 可自进化
```

**注意"前提"标注:** "方向可判断"的前提是评估结果本身可信。如果评估系统给出有偏误的评分（埋点盲区导致 `data_completeness` 系统性偏高、LLM Judge 未经校准导致误判），那么基于此评分做出的方向判断不是无害的——它会导致项目**朝着错误的方向自信地前进**。这个前提恰好是 Phase 4 元评估和交叉验证试图解决的问题——它不是"附加功能"，而是因果链的**逻辑必要环节**。

这一条因果链就是 eval 系统存在的全部理由。它不是 Phase 1-4 的"产物"，而是代码库从"功能堆叠"走向"系统化架构"的**先决条件**。

---

## 2. 架构总览: 四链模型 + 自指闭环

### 2.1 模块关系图

```
┌─────────────────────────────────────────────────────┐
│                   Server (server.py)                 │
│  后台循环: 每小时 daemon_cycle()                       │
│  启动: LLM Judge worker (5s 延迟)                     │
│  元评估: 每 6 周期执行 run_all()                       │
└──────────┬──────────────┬──────────────┬─────────────┘
           │              │              │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌─────▼──────────┐
    │ eval_engine │ │meta_eval   │ │  llm_judge     │
    │ (链2 引擎)  │ │(链3 自省)  │ │  (链3 验证)    │
    │             │ │            │ │                │
    │ 清理孤儿    │ │ 过程合规   │ │ 异步消费者线程  │
    │ 数据完整度  │ │ ScoreConfig│ │ 30s 超时       │
    │ 效果追踪    │ │ 评分漂移   │ │ 3次重试        │
    │ 优先级检查  │ │ 文档完整性 │ │ 6h 防风暴      │
    │ 评分聚合    │ │ 知识库防护 │ │ 安全校验层     │
    └──────┬──────┘ └─────┬──────┘ └─────┬──────────┘
           │              │              │
    ┌──────▼──────────────▼──────────────▼───────────┐
    │              eval_store (存储层)                 │
    │                                                 │
    │  traces.jsonl    scores.json   suggestions.json │
    │  configs.json    audit.jsonl   golden_dataset   │
    │  heartbeat.json  snapshots/    meta_eval.log    │
    └──────────────────────┬──────────────────────────┘
                           │
    ┌──────────────────────▼──────────────────────────┐
    │        trace_logger (链1 采集)                   │
    │  TraceContext / start_trace / end_trace          │
    │  _safe_record_llm_span / _record_tool_span       │
    └─────────────────────────────────────────────────┘
```

### 2.2 数据流: 三链闭环（物理视图）

**关键工程特性: 链3 的各个组件与链2 异步解耦，不是紧密耦合的同步调用。** 如果误将下图理解为同步调用链，会严重低估系统的容错能力。

```
同步 (每小时 daemon_cycle):
  链1 (采集) ──────────→ 链2 (评估) ──→ scores.json
  Trace/Span              Score/Sugg

异步 (各自独立调度):
  ┌─ 链3a: meta_evaluator.run_all()      每 6 周期 (≈6h)  ─→ META_EVAL scores
  ├─ 链3b: llm_judge._crossval_consumer() 独立 daemon 线程  ─→ LLM_JUDGE scores
  └─ 链3c: golden_dataset.evaluate_against() 手动触发       ─→ GOLDEN 评分
       ↑                                              │
       └──────── 反馈/修复 (人工/半自动) ──────────────┘
```

- **链1 (trace_logger):** 埋点采集。同步于每次 HTTP 请求。文件: `trace_logger.py` (~280 lines)
- **链2 (eval_engine):** 因果引擎。server.py 后台线程每小时 `daemon_cycle()` 调用。文件: `eval_engine.py` (~900 lines)
- **链3a (meta_evaluator):** 元评估。server.py 后台循环每 6 周期调用一次。6 小时间隔保证故障隔离——meta_evaluator 崩溃不影响链2 评分生产。
- **链3b (llm_judge):** LLM Judge。独立 daemon 线程 + `collections.deque` 异步队列，与后台循环完全解耦。30s 超时 + 3 次重试 + 6h 防风暴。
- **链3c (golden_dataset):** Golden Dataset。仅在手动触发时运行（`POST /api/eval/cross-validate/execute`），不与任何自动循环耦合。

**异步解耦是链3 最重要的工程特性。** 它保证了评估系统在"自省"时不会阻塞"生产"——即使 LLM Judge 调用超时或 meta_evaluator 遇到异常，链2 的评分生产不受影响。

### 2.3 存储设计: 文件系统优先，为迁移预留接口

当前全部使用 JSON/JSONL 文件存储，但通过 `_query_traces()` (`eval_store.py:244`) 封装了查询层:

```python
# eval_store.py:244
def _query_traces(*, min_duration_ms=None,
                  has_error=None, window_hours=None, limit=100):
    """统一 Trace 查询入口。封装 JSONL 存储细节，为 SQLite 迁移预留。"""
```

所有上层模块通过此函数查询 Trace，而非直接 `_read_jsonl("traces.jsonl")`。切换到 SQLite 时只需修改这一个函数。

数据快照 (`_snapshot_before_write`, `eval_store.py:60`) 保证每次写入前自动备份，保留最近 10 个版本。

---

## 3. 解决的核心问题 (按优先级)

### 3.1 P0: 数据完整度 — 可观测性盲区检测

**问题:** 系统的埋点是否完整？是否有关键路径没有被记录？

**解决:** `_compute_data_completeness()` (`eval_engine.py:162`) 定义了每种 Trace 类型必需的 Span 种类，自动检查覆盖率:

```python
# eval_engine.py:40
TRACE_TYPE_SPAN_REQUIREMENTS = {
    "agent_chat": ["LLM", "TOOL"],
    "rag_query":  ["LLM", "TOOL"],
}
```

低于阈值(0.9)自动生成建议。冷启动保护: `<5` 个适用 Trace 时跳过。

**为什么这是 P0:** 如果埋点本身有盲区，后续所有基于埋点的分析都在沙子上建城堡。

### 3.2 P0: 效果归因 — 每个变更的因果关系

**问题:** 采纳了一个建议，改了代码，评分变了——但这个变化是因为我们的改动，还是因为别的原因？不可知。

**解决:** `_effect_tracking_loop()` (`eval_engine.py:330`) 实现了完整的因果归因链:

1. **基线快照:** `apply_suggestion()` (`eval_store.py:479`) 在采纳建议时强制记录当前子指标值
2. **24h 后验证:** 自动对比基线 vs 当前值，计算 delta
3. **Git 冲突检测:** `_git_commits_touching_file()` (`eval_store.py:631`) 检查同一文件是否被其他提交修改
4. **优先级检查:** `_check_priority_violation()` (`eval_engine.py:298`) — P1/P2 指标下降自动标记违规
5. **归因判定:** 5 种状态 — `attributed`(确认有效) / `attributed_mixed`(部分下降) / `likely_failed`(违规) / `conflict`(并发修改) / `pending`(待验证)

```python
# eval_engine.py:391-408 — 归因判定逻辑
if has_conflict:
    attribution = "conflict"
elif violation["violated"]:
    attribution = "likely_failed"
    _trigger_review_on_violation(sug, violation)
else:
    avg_delta = sum(delta_details.values()) / len(delta_details)
    attribution = "attributed" if avg_delta >= 0 else "attributed_mixed"
```

**这是 eval 系统最具工程价值的功能:** 它把一个模糊的"改完看看效果"变成了一个可追溯的因果判断。

### 3.3 P1: 孤儿 Span 管理 — 故障信号不丢失

**问题:** Trace 断裂导致 Span 变成孤儿（有 Span 没有 Trace），其中的错误信息可能丢失。

**解决:** 
- `_cleanup_orphan_spans()` (`eval_engine.py:77`): 时间窗口重关联 + >1h 确认不可修复
- `_orphan_error_health_check()` (`eval_engine.py:121`): 统计孤儿 Span 中的错误占比

```python
# eval_engine.py:136-137
error_count = sum(1 for s in orphans if s.get("status") == "error")
ratio = error_count / total
```

### 3.4 P1: 交叉验证 — CODE 评分不是自说自话

**问题:** `data_completeness` 的评分完全由 CODE 逻辑生成。如果 CODE 逻辑有 bug 或 TRACE_TYPE_SPAN_REQUIREMENTS 与实际需求不符，评分会系统性偏误且永远不会被发现。

**解决:** `_cross_validate_data_completeness()` (`eval_engine.py:225`) + `llm_judge.py`:

1. 从最近 24h Traces 随机采样 5 条
2. 生成结构化评估 prompt（包含实际 Span 种类 vs 必需 Span 种类 + CODE 判定）
3. LLM Judge 独立判定 → 保存为 `source: "LLM_JUDGE"`
4. `evaluate_code_llm_consensus()` (`meta_evaluator.py:293`) 对比 CODE vs LLM 一致性

```python
# meta_evaluator.py:328
rate = disagreements / compared if compared > 0 else None
score_value = 1.0 - (rate if rate is not None else 0)
```

### 3.5 安全纵深防御

eval 系统的安全不是事后补充的——它与功能代码同步实现:

| 层级 | 机制 | 位置 |
|------|------|------|
| 路由层 | `_check_admin()` 所有写端点 | `routes/api_eval.py` |
| 数据层 | `_verify_admin_token()` | `eval_store.py:479,524` |
| 审计 | `audit.jsonl` — SHA256(admin_token) + 操作记录 (注: 哈希函数不可降级为 SHA1/MD5/明文，SHA256 是审计日志不可否认性的最低要求) | `eval_store.py:462` |
| 快照恢复审计 | `_audit_log("snapshot_restore")` — 记录恢复的文件名和快照ID (注: 当前快照恢复为内部函数，需在调用点增加审计日志) | `eval_store.py:snapshot` |
| 防风暴 | 6h LLM Judge 间隔 + 1h 审查触发间隔 | `llm_judge.py:312`, `eval_engine.py:493` |
| 影子模式 | API 写操作禁用 + 数据采集不写入生产文件 + 调试隔离 — 完整的"不污染数据"保护机制，不仅限于 API 层 | `config.py:EVAL_SHADOW_MODE` |
| 备份数据访问 | `snapshots/` 文件系统权限依赖运维配置 — **残余风险:** 直接文件系统访问可绕过审计，当前未纳入安全模型 | 运维层 |

**LLM 输出校验层 (`_validate_llm_output`) — 外部输入与系统数据的唯一桥梁:** 这是评估系统自指闭环中唯一的"外部输入校验层"。LLM Judge 调用 DeepSeek API 获得的响应，在写入 `scores.json` 之前必须通过三层校验——**值域范围** (value ∈ [0.0, 1.0])、**文本字段长度限制** (≤ 1000 字符，防 prompt 注入膨胀)、**XSS 注入检测** (`<script>`/`<iframe>`/`javascript:` 拒绝写入)。如果这一层被绕过或实现有缺陷，LLM 的输出可以直接污染评估数据存储，进而影响 Dashboard 展示和后续的自动建议。此校验层与路由鉴权、数据鉴权不同——它防御的不是"未授权的用户"，而是"不可信的 AI 输出"。位置: `llm_judge.py:58`。

---

## 4. 自指闭环 (Phase 4): 评估系统评估自身

### 4.1 为什么需要自指

这是归零推演的自然延伸:

```
链2 评估了代码库 → 谁评估链2 的评估是否正确？
链3 评估了链2     → 谁评估链3 的评估是否正确？
```

Phase 4 的答案是: **链3 评估链2，同时链3 的产出被链2 消费（作为 ScoreConfig），形成可见的自指循环。** 至于"谁评估链3"——这是 Phase 4 明确不做的事（计划 §10），但通过人工抽检 + 审计日志 + 独立日志文件保留了可追溯性。

### 4.2 meta_evaluator 的 6 项检查

| # | 函数 | 检查内容 | 检测方式 |
|---|------|----------|----------|
| 1 | `evaluate_phase3_adherence()` | Phase 1-3 6项设计原则是否被遵守 | 静态代码分析 |
| 2 | `evaluate_score_configs()` | ScoreConfig 是否 >30天未审查 | 时间戳检查 |
| 3 | `evaluate_code_llm_consensus()` | CODE vs LLM Judge 判定一致率 | 交叉对比 |
| 4 | `evaluate_score_drift()` | 是否有指标连续7天单调下降 | 趋势分析 |
| 5 | `evaluate_document_integrity()` | 关键文档是否被非版本化覆写 | git log 分析 (注: 不检测 `meta_evaluator.py` 自身的篡改——"谁来保护保护者"是自指系统在安全层面的终极问题。当前通过独立日志文件 `meta_eval.log` 保留可追溯性，但恶意篡改 `meta_evaluator.py` 同时可篡改日志写入逻辑。需代码审查或外部完整性监控补充) |
| 6 | `evaluate_knowledge_base()` | 知识库记录的错误是否有代码防护 | 关键词匹配 |

每项检查的产出:
- 评分写入 `scores.json` (source: `META_EVAL`) — 内联展示在 Dashboard
- 建议写入 `suggestions.json` — 与普通建议同列显示。**元评估建议通过 `[自指]` 标签与业务建议区分，其他视觉元素（颜色、卡片结构、操作按钮）保持一致。** 区分来源的目的是提供可追溯性，而非暗示元评估建议与业务建议有优先级差异——建议的严重度和紧急性由内容决定，不由来源决定。
- 日志写入 `meta_eval.log` — 独立于业务 Trace

### 4.3 自指指示器

Dashboard 顶部横幅实时显示评估系统自身状态 (`eval-main.js`)，三个信息层级:

**常态:**
```
评估系统自身健康度: 0.85 · 3条待审核建议 · 数据更新于12分钟前
```

**告警联动（当待审核建议中含 P0 级别项时，视觉升级）:**
```
评估系统自身健康度: 0.85 · ⚠ 3条待审核建议(含1条P0) · 数据更新于12分钟前
```
这是安全审计师"不允许静默"原则在交互层的体现——就像汽车仪表盘区分"油箱快空了"和"发动机故障"的紧急程度差异。P0 告警不允许与普通建议使用相同的视觉权重。

**信任验证入口:** 自指指示器支持点击交互。点击"评估系统自身健康度: 0.85"时，页面跳转到元评估面板，展示该分数的 6 项检查分解、上次运行时间、待审核建议详情。这不是美化——是"30 秒信任法则"的延伸。用户看到 0.85 后的第一个问题是"我应该相信它吗？"，而验证这个数字可信度的入口必须在一次点击之内可达。

**性能信任基线:** 在 Dashboard 底部信息栏永久展示 "API 响应时间 < 500ms (当前: 21.7ms)"。这不是给技术用户看的——它建立了"系统响应迅速"的持续信任。性能是体验的底线，不是可选的优化。当前 p95=21.7ms 远超预算，但需要被持续监控而非一次性测量后束之高阁。

---

## 5. 已解决 vs 未解决

### 5.1 已解决 (Phase 1-4 完成)

| 问题 | 解决方式 | 验证 |
|------|----------|------|
| 埋点盲区 | `_compute_data_completeness` + 自动建议 | 140 tests pass |
| 效果不可归因 | `_effect_tracking_loop` + 基线 + Git 冲突检测 | 5 种归因状态 |
| CODE 评分自说自话 | LLM Judge 交叉验证 + 一致性对比 | **已部署，待真实调用验证** (见 §5.2-A) |
| 评估系统自身健康不可知 | meta_evaluator 6 项 + 自指指示器 | 每 6h 自动运行 |
| 文档被覆写无记录 | `evaluate_document_integrity` git log 分析 | 检测 <60s 覆写 |
| 知识库错误无防护 | `evaluate_knowledge_base` 错误-防护映射 | P1 级别告警 |
| 守护进程静默死亡 | heartbeat.json + 2h 超时 P0 告警 | 已测试 (注: heartbeat 写入者与读取者为同一后台循环，后台线程整体崩溃需 OS 级进程监控，不在当前 scope 内) |
| 影子模式未验证 | `TestShadowModeIntegration` 端到端测试 | 已测试 |
| 高权限操作无审计 | audit.jsonl + SHA256(admin_token) | 成功写操作全量记录 (注: 鉴权失败路径待 Phase 5 P0-2 修复后覆盖) |

### 5.2 未解决 (已知限制，会议需讨论)

**A. LLM Judge 从未真实调用** (对应 §5.1 第 3 项)

`llm_judge.py` 的消费者线程已启动，但队列为空。防风暴保护(6h)阻止了所有自动触发。需要手动 `POST /api/eval/cross-validate/execute` 且 `force=true` 才能入队。`evaluate_code_llm_consensus()` 在空数据集上无法产生有意义的对比——此项在 §5.1 中的状态为"已部署，待真实调用验证"而非"已解决"。参见执行报告 §6.2。

**交互层影响:** 元评估面板的"CODE-LLM 一致率"区域在 LLM Judge 空数据时**不得**展示 0% 或 100%——两者都会产生严重误导（0% 暗示已验证且全部不一致，100% 暗示已验证且全部一致）。正确展示方式: **"待验证"状态 + 说明"需要手动触发 LLM 交叉验证"**。这是一个占位符模式，已在前端空状态设计中确定，Phase 4 实现需确认遵循此模式。

**B. meta_evaluator 准确性未校准**

`evaluate_phase3_adherence()` 的 6 项检查中，"兼容性修正 trade-off 标注" 通过关键词匹配实现——可能漏检也可能误检。Phase 5 需引入人工抽检校准。

**C. 前端模块超标**

`eval-main.js` 483 行，超过红线3 的 300 行限制。已被 `evaluate_phase3_adherence()` 自动检测到——此问题在 Phase 4 执行报告、本架构论证、以及会议中被三次提及，不允许退化为"仪式性承认"。**总裁裁定 P0-2: Phase 5 第一个 commit 必须包含 `eval-slideout.js` 拆分，未完成前不启动任何其他工作。**

**D. 知识库路径硬编码**

`evaluate_knowledge_base()` 假设知识库在 `ROOT_DIR.parent / "知识库" / "错误与修正与优化"`。如果目录结构变化，静默返回空结果。**已纳入 Phase 5 P1-2 修复计划**，提取为 `config.py` 常量 + 静默失效 → 显式错误信号。在修复完成前，此风险部分被 `evaluate_phase3_adherence()` 的文档完整性检查间接覆盖（目录结构变化会触发 git 变更检测）。

**E. Golden Dataset 首次 import 自动初始化存在隐式副作用**

`golden_dataset.py` 在 import 时检查 `golden_dataset.json` 是否存在，不存在则创建空数据集。当前单进程 Flask 应用中安全，但如果未来切换到多 worker 模式（gunicorn），多个进程同时 import 会导致竞争条件。**建议:** 在初始化逻辑中增加文件锁或 `exist_ok`，并在代码注释中标注"当前单进程安全，多 worker 需增加进程锁"。此问题不影响当前功能正确性，但不应隐藏为 import 副作用。

**F. 心跳机制的后台线程单点故障 — 安全攻击面**

总工程师已指出 heartbeat 写入者与读取者为同一后台循环（工程盲区）。从安全角度补充: 如果攻击者发现能让后台线程崩溃的漏洞（如构造特殊格式 Trace 数据导致未捕获异常），可利用此漏洞让整个评估系统的安全监控静默失效——heartbeat 不再更新、孤儿 Span 不再清理、效果追踪不再运行、优先级违规不再被检测。当前通过 `try/except` 包裹每个后台任务降低了风险，但这是单层防御而非纵深防御。**后台线程整体崩溃的检测需 OS 级进程监控，当前未实现独立于后台线程的心跳消费者。**

---

## 6. 自进化方向

> **注意:** Phase 4 计划仅在 §1.2 将"自动回滚/自动修复"标记为推迟项，未定义后续 Phase 的范围。以下基于当前已知限制和归零推演的逻辑延伸，不是已批准的计划。

### 6.1 立即: 校准 + 验证 + 修复已知限制

1. **LLM Judge 端到端验证** — 至少一次真实调用，确认 `judge_data_completeness → _validate_llm_output → save_score` 全链路
2. **meta_evaluator 准确性校准** — 人工审查 1-2 次 `run_all()` 结果，标记误检/漏检
3. **前端模块拆分** — `eval-main.js` → `eval-slideout.js` (~80 lines)，**强制项**（总裁 P0-2 裁定，Phase 5 第一个 commit）
4. **知识库路径配置化** — 提取为 `config.py` 常量
5. **快照恢复自动化测试** — 模拟数据文件损坏，执行恢复流程，验证恢复后数据与快照时刻一致。当前快照机制像灭火器——希望永不用上，但必须定期检查它还能用

### 6.2 中期可能性

- 红线违规 → 自动回滚/自动修复（Phase 4 plan §1.2 推迟项）
- 实时告警通知（Phase 4 plan §1.2 "不纳入"项）
- 告警推送机制选型待定（Slack/Email/Webhook 均可，尚未评估）

### 6.3 长期: 真正的自进化

> **关键前提:** 评估系统自身的可靠性必须达到一定阈值后，才能开始自动化链条的延伸。如果 `evaluate_code_llm_consensus()` 的一致率只有 70%，"建议自动实施"就是危险功能——它有 30% 概率基于错误评估自动修改代码。如果 `evaluate_score_drift()` 检测到的"连续下降"是因为埋点盲区导致的数据缺失，"阈值自调整"会让系统基于噪音调整阈值。**用评估系统评估自己是否足够可靠，是自动化开始的前提。**

#### 自动演化门槛

| 能力 | 启动前提 | 当前状态 |
|------|----------|----------|
| 性能回归自动检测 | Phase 5 建立 CI 性能基线（`/api/eval/summary` p95），每 Phase 完成后自动对比 | Phase 3 基线已建立 (p95=21.7ms)，Phase 5 纳入 CI |
| 建议自动实施 | CODE-LLM 一致率 > 95% + `eval_system_freshness` > 0.85 | LLM Judge 未真实调用，不可启动 |
| 阈值自调整 | 连续 30 天 `data_completeness` > 0.95 + 无 P0 告警 | 数据量不足，不可启动 |
| Golden Dataset 自增长 | `evaluate_code_llm_consensus()` 一致率 > 90% | Phase 5 后可评估 |
| 指标自动发现 | Phase 6+ 人工设计，不自动生成 | 不在当前规划内 |

#### 自进化能力

当前 eval 系统的 ScoreConfig 是人工定义的。真正的自进化意味着:

1. **指标发现:** 系统自动从异常模式中发现新指标（如:"过去 24h 中 token_per_task 的方差突然增大 3 倍"）
2. **阈值自调整:** 不是人工设 threshold=0.9，而是基于历史分布自动计算异常边界
3. **建议自动实施:** 低风险建议（如文档更新）自动 apply，高风险建议（如安全相关）保留人工审批
4. **Golden Dataset 自增长:** 每一条人工标注自动加入 Golden Dataset，LLM Judge 持续校准

当前阶段的正确目标不是"自进化"，而是**让自进化成为可能**——即: 有一个可信的评估基础设施，能回答"改完后变好了还是变差了"。

---

## 附录: 代码清单

| 模块 | 文件 | 行数 | 职责 |
|------|------|------|------|
| 链1 采集 | `services/eval/trace_logger.py` | ~280 | Trace/Span 生成 + TraceContext |
| 链2 引擎 | `services/eval/eval_engine.py` | ~900 | 5个评估函数 + 15个ScoreConfig + 聚合 |
| 链2 存储 | `services/eval/eval_store.py` | ~650 | 4种文件读写 + 查询 + 审计 + Git工具 |
| 链3 自省 | `services/eval/meta_evaluator.py` | ~566 | 6个元评估函数 + run_all() 入口 |
| 链3 验证 | `services/eval/llm_judge.py` | ~346 | LLM交叉验证 + 异步队列 + 安全校验 |
| 链3 基准 | `services/eval/golden_dataset.py` | ~133 | Golden Dataset CRUD + 对比评估 |
| API | `routes/api_eval.py` | ~350 | 20+ 端点 (读/写/元评估) |
| 前端 | `static/js/modules/eval-*.js` | ~1,200 | Dashboard + 交互 + 图表 |
| 测试 | `tests/test_eval_engine.py` | ~600 | 140 tests, 14 test classes |

**总计: ~5,000 lines, 6 后端模块, 3 前端模块, 15 ScoreConfigs, 20+ API 端点**
