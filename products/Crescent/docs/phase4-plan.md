# Phase 4: 元评估 + LLM Judge 实施计划 (v1)

> **状态:** 初稿 — 待团队会议审查  
> **前置依赖:** Phase 1–3 核心完成，6 项 P1/P2 交互补全待清  
> **时间线:** Phase 4 开始前先清 Pre-Phase 4 清单，再进入构建

---

## Pre-Phase 4: 必须清空的待办清单

> 以下 6 项来自 Phase 3 对照检查发现的缺口（`docs/checkpoints/checkpoint-2026-06-10.md`），
> 必须在 Phase 4 第一行代码之前完成。Phase 4 引入 LLM Judge 后将增加系统复杂度，
> 带着这些 UI 缺口进入会让交互问题与逻辑问题叠加，排查成本倍增。

### P1 — Phase 4 启动前必须清空 (4 项来自原始缺口 + 4 项来自总工程师审查)

#### 原始 P1 (Phase 3 缺口 — 影响 30 秒信任法则)

| # | 项目 | 影响 | 涉及文件 | 预估 |
|---|------|------|----------|------|
| 1 | **趋势线 hover tooltip + annotation 标记点** | Chart.js 趋势线与建议标注完全割裂 | `eval-charts.js:trendConfig()`, `eval-main.js:assembleOverview()` | ~40 行 |
| 2 | **建议点击滑出面板 (Slide-out)** | 建议只显示前 100 字摘要，点击无响应 | `eval-ui.js:renderSuggestionItem()`, `eval.html`, `eval-main.js` | ~60 行 |

#### 总工程师审查新增 P1

| # | 项目 | 影响 | 涉及文件 | 预估 |
|---|------|------|----------|------|
| 3 | **🆕 `<template>` + cloneNode 工程债务清理** | innerHTML 字符串拼接方式无法在渲染时绑定事件，需要 post-hoc querySelector。随着组件增多（20+ 建议卡片、10+ 评分卡），性能和维护成本线性恶化 | `eval-ui.js` (重构 renderScoreCard/renderSuggestionItem/renderSpanNode), `eval.html` (新增 `<template>` 标签) | ~120 行 |
| 4 | **🆕 `_cross_validate_data_completeness()` 测试补全** | 当前函数生成 CROSSVAL_PENDING 请求但无测试验证请求结构是否符合未来 LLM Judge 消费契约。这是为了关闭 P1 行动项而做的纸面工作 | `tests/test_eval_engine.py` | ~30 行 |
| 5 | **🆕 后台任务健康检查 (daemon heartbeat)** | 后台线程每小时运行三任务，如果线程静默死亡（未捕获异常），Dashboard 数据不再更新且无人知晓——直到有人打开页面发现数据过时 | `services/eval/eval_engine.py` (新增 `_daemon_heartbeat()`), `routes/api_eval.py` (新增 `/eval/health` 端点) | ~40 行 |
| 6 | **🆕 性能基准测试 (从 P3 提升)** | 交互设计顾问明确制定了 p95 < 500ms 性能预算。无基准数据 = 不知道当前是否满足 = Phase 4 增加 LLM Judge 后性能退化无法检测 = 30 秒信任法则的物理基础不存在 | `tests/bench_eval_overhead.py` (完善) → `docs/perf-baseline-2026-06-11.md` | ~30 行 |

#### 交互设计顾问审查新增 P1

| # | 项目 | 影响 | 涉及文件 | 预估 |
|---|------|------|----------|------|
| 7 | **🆕 30 秒信任法则盲测** | 整个 Phase 3 最核心的交付标准，验证状态是"未验证"。三个信任问题的答案不是设计文档能回答的——只有真实用户的眼睛能回答：数字够大吗？告警颜色够醒目吗？非技术人员看到 0.65 能理解吗？ | 找 1 位未参与项目的人盲测 → 记录结果到 `docs/30s-trust-test-2026-06-11.md` | 30 分钟 |
| 8 | **🆕 数据新鲜度指示器 + 影子模式操作反馈** | Dashboard 展示系统健康，但自身健康不可见：数据过期无人知晓（时间戳在角落），影子模式按钮禁用但不解释原因（用户以为功能没实现） | `eval-main.js:assembleOverview()` (新鲜度指示器), `eval-ui.js:renderAlertBanner()` (影子模式 tooltip) | ~25 行 |

#### 安全审计师审查新增 P1

| # | 项目 | 影响 | 涉及文件 | 预估 |
|---|------|------|----------|------|
| 9 | **🆕 评估数据文件自动快照** | v3→v4 覆写的真正病灶：Write 工具能覆写设计文档，也能覆写 scores.json、suggestions.json、traces.jsonl。评估系统保护被评估对象，但自己不设防。所有评估记忆（评分历史、建议生命周期、Trace 数据）都存储在一份无备份的 JSON 文件中 | `services/eval/eval_store.py` (`_write_json`/`_append_jsonl` 前 snapshot)，`data/eval/snapshots/` 目录，保留最近 10 版 | ~30 行 |
| 10 | **🆕 🔴 EVAL_ADMIN_SECRET 独立迁移 (从 Phase 4 Step 0 提升为 Pre-Phase 4)** | Phase 3 最危险的安全决策。SECRET_KEY 是 Flask 会话签名基石密钥，复用于 API 鉴权混淆了两个安全域。一个凭证泄露 → 会话伪造 + CSRF 绕过 + API 鉴权同时崩溃。安全领域的等价原则是"最小权限"和"职责分离"，不是"复用现有机制" | `config.py` (新增 `EVAL_ADMIN_SECRET`，不 fallback 到 `SECRET_KEY`), `routes/api_eval.py`, `eval_store.py`, `eval.html`, 3 测试文件 | ~25 行 |
| 11 | **🆕 API 安全完成清单** | cross-validate/scores 端点裸奔不是"遗漏"，是安全没有被纳入开发的完成定义。开发者说"完成"指"能返回数据"不是"能返回数据且经过鉴权"。安全被当作功能完成后的补充工作 | 安全清单写入 CLAUDE.md → Phase 4 所有新端点必须满足清单才能标记完成 | ~10 行 |

**P1 通过标准:**
1. 趋势线上显示蓝色圆点 (suggestion_applied) 和灰色圆点 (commit)，hover 显示 `value_before → value_after` 拼装文案
2. 点击建议卡片 → 右侧滑出 320px 面板 → 显示完整生命周期 → 点击遮罩或 × 关闭
3. `eval.html` 含 `<template id="score-card-tmpl">` / `<template id="suggestion-item-tmpl">` / `<template id="span-node-tmpl">`；JS 通过 `cloneNode(true)` 使用；escapeHtml 仅用于单个文本节点填充
4. `_cross_validate_data_completeness()` 测试验证生成的 `crossval_items[0]` 包含 `trace_id`, `span_kinds_present`, `span_kinds_required`, `code_judgment`, `llm_prompt` 五个必填字段
5. `_daemon_heartbeat()` 每次后台循环完成时更新时间戳；`/api/eval/summary` 的 `alerts` 中增加 `type: "daemon_stale"` 告警（心跳 > 2h 未更新 → P0）
6. 100 次 `/api/eval/summary` 请求，输出 p50/p95/p99 延迟，p95 < 500ms 则通过，否则标记为性能回归
7. 找 1 位未参与项目的人盲测：打开 /eval → 计时 30 秒 → 问三个问题（系统健康吗？哪出问题？应关注什么？）。任何一个答不上来 → Phase 4 第一项工作是修复信息层级，不是实现新功能
8. 总览面板总评分旁显示"数据更新于 X 分钟前"；>60 分钟未更新 → 橙色警告。影子模式下点击禁用按钮 → tooltip "影子模式下写操作已禁用。设置 EVAL_SHADOW_MODE=false 以激活。"
9. `_write_json()` 和 `_append_jsonl()` 操作前自动将目标文件复制到 `data/eval/snapshots/`，保留最近 10 版本。`_restore_snapshot(filename, version)` 可恢复任意版本
10. `config.EVAL_ADMIN_SECRET` 独立于 `config.SECRET_KEY`，不 fallback。启动时若未设置 → 打印警告 `⚠️ EVAL_ADMIN_SECRET is not set — eval admin endpoints will reject all requests`。`_check_admin()` 和 `admin_token` 参数全面迁移。代码注释标注独立凭证的安全原因
11. CLAUDE.md 新增"API 安全完成清单"：路由层 `_check_admin()` + 数据层 `_verify_admin_token()` + 403 测试 + 影子模式 403 测试。Phase 4 所有新端点必须在实现功能的同时满足清单

### P2 — 模块联动

| # | 项目 | 影响 | 涉及文件 | 预估 |
|---|------|------|----------|------|
| 12 | **Agent 三指标卡片** | Agent 面板只有 trace 列表，缺聚合指标 | `eval-main.js:assembleAgentPanel()` | ~30 行 |
| 13 | **告警卡片点击滚动** | 告警和详情面板无联动 | `eval-ui.js:renderAlertBanner()`, `eval-main.js:switchTab()` | ~15 行 |
| 14 | **雷达图点击跳转** | 三层信息各自孤立 | `eval-charts.js:radarConfig()` (onClick) | ~15 行 |

**P2 通过标准:**
- Agent 面板顶部 3 张卡片：成功率、工具准确度、Token 效率，每张有当前值 + 迷你趋势 + 变化箭头
- 告警卡片点击 → `switchTab('details')` + 平滑滚动到对应 config 的 score card
- 雷达图点击维度标签 → `switchTab('details')` + 滚动到对应 `#card-{config_id}`

---

## 0. Phase 4 战略定位

Phase 4 完成评估系统的**自指闭环**——评估系统开始评估自身。

```
Phase 1 (链1): 行为 → 数据     ✅ 完成
Phase 2 (链2): 数据 → 行动     ✅ 完成
Phase 3 (仪表盘): 行动 → 可见   ✅ 核心完成
Phase 4 (元评估): 可见 → 自省   ← 当前
```

**核心问题:** Phase 1–3 建的评估系统，它自己可信吗？

- CODE 评分逻辑有 bug 怎么办？（`data_completeness` 的 `TRACE_TYPE_SPAN_REQUIREMENTS` 写错了？）
- 评分阈值设置合理吗？（0.9 的 completeness 阈值是拍脑袋的？）
- 建议的归因判定准确吗？（attributed / unattributable / likely_failed 三种状态，LLM 同意吗？）

Phase 4 回答这些问题：**引入独立的 LLM Judge 交叉验证 CODE 评分，建设元评估器定期审查评估体系自身的健康度。**

### 三条新的信任问题 (Phase 4 目标)

1. 评估系统自己可信吗？（CODE 评分有被独立验证吗？）
2. 评估标准在退化吗？（ScoreConfig 阈值还合理吗？指标过时了吗？）
3. 犯过的错误不会再犯吗？（文档变更、配置修改、代码重构有被追踪吗？）

---

## 1. Phase 4 范围

### 1.1 纳入

| 模块 | 说明 | 依赖 |
|------|------|------|
| **LLM Judge** | `/cross-validate/execute` 从 501 → 实现。调用 LLM 对 CODE 评分进行独立交叉验证 | DeepSeek API (已有 client) |
| **meta_evaluator.py** | 评估评估系统自身：ScoreConfig 新鲜度、CODE/LLM 一致性、评分漂移检测、Phase 1-3 过程合规审计 | eval_store (已有) |
| **动态 Golden Dataset** | 少量手工标注的 Trace 作为评估基准，可演进 | traces.jsonl (已有) |
| **`/api/eval/meta/results` 实现** | 从 stub 空数组 → 返回真实元评估结果 | meta_evaluator.py |
| **旧 review_* 端点弃用** | `review_agent.py` / `review_store.py` 功能合并到 eval 系统 | Phase 1–3 eval 基础设施 |
| **知识库评估** | 对 `知识库/错误与修正与优化/` 中记录的错误进行结构化评估 | meta_evaluator.py |
| **文档变更可追溯性** | git log → eval trace，关键文档修改产生 event，可被评估系统追踪 | trace_logger.py (已有) |
| **🆕 EVAL_ADMIN_SECRET 迁移** | 评估系统鉴权从复用 `SECRET_KEY` 迁移到独立 `EVAL_ADMIN_SECRET`，消除安全域混淆 | config.py, routes/api_eval.py, eval_store.py |
| **🆕 文档完整性审计** | meta_evaluator 新增 `evaluate_document_integrity()` — 检测关键文档是否被非版本化覆写 | meta_evaluator.py |

### 1.2 不纳入

- ❌ 实时告警通知（Slack/Email）
- ❌ 自动回滚/自动修复（Phase 5）
- ❌ 外部系统集成
- ❌ 新的付费 API 依赖（复用现有 DeepSeek client）

---

## 2. 架构设计

### 2.1 新增模块

```
services/eval/
├── meta_evaluator.py      ← 新增: 元评估器
│   ├── evaluate_score_configs()      ScoreConfig 新鲜度审查
│   ├── evaluate_code_llm_consensus() CODE vs LLM Judge 一致性
│   ├── evaluate_score_drift()        评分漂移检测
│   └── evaluate_knowledge_base()     知识库错误记录评估
│
├── llm_judge.py            ← 新增: LLM Judge
│   ├── judge_data_completeness()     交叉验证数据完整度
│   ├── judge_attribution()           验证归因判定
│   └── judge_threshold()             审查阈值合理性
│
├── golden_dataset.py       ← 新增: 动态 Golden Dataset
│   ├── load_dataset()                加载手工标注
│   ├── add_sample()                  添加新样本
│   └── evaluate_against()            Judge vs Golden 对比
```

### 2.2 修改模块

| 文件 | 变更 |
|------|------|
| `config.py` | 新增 `EVAL_ADMIN_SECRET` 配置项；SECRET_KEY 不再用于 eval 鉴权 |
| `routes/api_eval.py` | `_check_admin()` 迁移到 `EVAL_ADMIN_SECRET`；`/cross-validate/execute` 从 501 → 调用 `llm_judge`；`/meta/results` 从 stub → 返回真实数据 |
| `services/eval/eval_store.py` | `apply_suggestion`/`reject_suggestion` 的 `admin_token` 校验迁移到 `EVAL_ADMIN_SECRET`；`meta_results.json` 读写完善 |
| `services/eval/eval_engine.py` | 新增 `_run_llm_judge()` + `_daemon_heartbeat()` + `crossval_worker`；后台任务增加元评估周期 + 心跳写 |
| `templates/pages/eval.html` | `<meta name="admin-token">` 迁移到 `EVAL_ADMIN_SECRET`；元评估面板从占位 → 真实数据渲染 |
| `static/js/modules/eval-api.js` | `ADMIN_TOKEN` 读取迁移到 `EVAL_ADMIN_SECRET` |
| `static/js/modules/eval-main.js` | `assembleMetaPanel()` 对接真实数据 |
| `tests/test_eval_api.py` | `_auth_headers()` 迁移到 `EVAL_ADMIN_SECRET` |
| `tests/test_eval_core.py` | `admin_token` 参数迁移到 `EVAL_ADMIN_SECRET` |
| `tests/test_eval_engine.py` | `admin_token` 参数迁移到 `EVAL_ADMIN_SECRET` |

### 2.3 交互设计约束 (IDC 审查 — Phase 4 全局约束)

> **核心原则:** 信息维度可以增加，视觉词汇不能增加。用户不需要学习新的交互模式来理解评估系统。

**约束 1: 视觉词汇冻结** — LLM Judge 的任何新增判定结果，必须使用现有颜色映射（§4.5 评分卡颜色）和现有图标系统（§4.4 Span 状态图标）呈现。禁止新增颜色、新增图标类型、新增图表类型。

**约束 2: 元评估内联** — 元评估结果不创建独立页面或独立面板。`eval_system_freshness` 的分数出现在雷达图上（作为一个额外维度），其生成的建议出现在建议列表中（标记为 `source: "meta_eval"`）。

**约束 3: 评估系统自指状态全局指示器** — Dashboard 顶部横幅（影子模式横幅同位置）增加一行小字：
```
评估系统自身健康度: 0.85 · 3 条待审核建议 · 数据更新于 12 分钟前
```
健康度下降时，该行文字变为橙色；>60 分钟未更新时，变为红色并显示"⚠️ 后台任务可能已停止"。

**约束 4: 历史智慧接入 (IDC 问题 5)** — 建议滑出面板底部增加"历史相似事件"区域：
- 数据来源: `doc_indexer` 索引的错误文档 + `review_memory` Archive 层
- 展示逻辑: 当前告警的 `config_id` + `category` 匹配历史记录的 `config_id` + `category`
- 展示文案: "这个错误模式在过去 4 周内出现过 N 次，上次的修复方案是'{suggestion.title}'，采纳后 {config_id} 提升了 {delta}。"
- 这是总裁"数据故事"理念在交互层面的落地：Dashboard 从"描述问题"升级为"提供解决方案"

### 2.4 安全架构约束 (SA 审查 — Phase 4 全局约束)

**约束 1: 数据文件自动快照** — `eval_store._write_json()` 和 `_append_jsonl()` 内部，写入前自动将目标文件复制到 `data/eval/snapshots/{filename}.{timestamp}.bak`，保留最近 10 版。`snapshot_retention` 可配置。这确保评估系统自身的记忆（评分、建议、Trace）像被评估对象一样受到保护。

**约束 2: 安全完成清单** — Phase 4 所有新增/修改的 API 端点必须满足四项条件才能标记"完成"：
1. 路由层 `_check_admin()` 守卫（写操作）或明确注释为何不鉴权（读操作）
2. 数据层 `_verify_admin_token()` 校验（写操作）
3. 测试覆盖 403 场景（无 token + 错 token）
4. 测试覆盖影子模式 403 场景（写操作）

**约束 3: LLM 输出校验层** — `eval_engine.py` 中新增 `_validate_llm_output(score)` 函数：
- 评分值必须在 [0.0, 1.0] 范围内
- 文本字段长度 ≤ 1000 字符
- 任何包含 `<script>` / `<iframe>` / `javascript:` 的输出被拒绝并记录安全事件
- 校验失败 → 标记 `status: "rejected_security"`，不写入 scores.json

**约束 4: 审计日志** — 高权限操作（apply/reject/rollback/LLM Judge 执行）写入 `data/eval/audit.jsonl`：
```json
{"timestamp": "...", "admin_token_hash": "sha256:abc...", "operation": "apply_suggestion", "target_id": "sug_xyz", "source_ip": "...", "user_agent": "..."}
```
与业务 Trace 分离，专用于事后溯源。

**约束 5: API Key 环境变量化** — DeepSeek API Key 必须通过环境变量 `DEEPSEEK_API_KEY` 注入。检查项：代码库中无硬编码 Key（`grep -r 'sk-[a-zA-Z0-9]'` 返回零结果）。

**约束 6: 依赖安全** — Phase 4 引入的任何新外部库（pip 或 CDN）必须固定版本号 + 校验完整性哈希。CDN 引用使用 `integrity` 属性（与 Chart.js 一致）。

### 2.5 数据流

```
后台任务 (每 6h，不是 1h — LLM 调用有成本)
  │
  ├─→ meta_evaluator.evaluate_score_configs()
  │     ├─ 检查每个 ScoreConfig 的 updated_at
  │     ├─ 标记 >30 天未审查的 config → meta_results
  │     └─ 评分: eval_system_freshness
  │
  ├─→ meta_evaluator.evaluate_code_llm_consensus()
  │     ├─ 读取 CROSSVAL_PENDING 评分 (Phase 2 已产生)
  │     ├─ 调用 llm_judge.judge_data_completeness() 逐条判定
  │     ├─ 对比 CODE judgment vs LLM judgment
  │     ├─ 不一致 + delta > 阈值 → suggestion (severity=P1)
  │     └─ 评分: data_completeness_crossval 从 placeholder → 真实值
  │
  ├─→ meta_evaluator.evaluate_score_drift()
  │     ├─ 检查各 config 评分趋势
  │     ├─ 连续 7 天下降 → suggestion
  │     └─ 评分: score_drift (新增 ScoreConfig)
  │
  ├─→ meta_evaluator.evaluate_document_integrity()
  │     ├─ 扫描 docs/*.md 关键文档的 git log
  │     ├─ 检测非版本化覆写 (Write without prior commit)
  │     ├─ 检测同一文件连续两次修改间隔 < 1 分钟 (覆写信号)
  │     └─ 评分: document_integrity (新增 ScoreConfig, P1)
  │
  └─→ meta_evaluator.evaluate_knowledge_base()
        ├─ 扫描 知识库/错误与修正与优化/
        ├─ 检查每个错误是否有对应的系统防护
        ├─ 未防护错误 → suggestion (severity=P2)
        └─ 评分: kb_protection_coverage (新增 ScoreConfig, P2)
```

---

## 3. LLM Judge 设计

### 3.1 调用策略 — 异步任务队列

**LLM 调用绝对不能在同步路径中执行。** Phase 2 Bug #6（真实调用 LLM 导致测试耗时 90s+）的教训：慢速 I/O 必须与主循环解耦。

**LLM 判定结果的呈现** 必须遵守 §2.3 约束 1（视觉词汇冻结）：Judge 的 `complete/incomplete` 判定使用现有 `--success`/`--danger` 颜色，不新增图标类型。

```
_effect_tracking_loop (后台 6h 周期)
  │
  ├─→ 收集待验证的 CROSSVAL_PENDING 评分
  ├─→ 逐个入队 → crossval_task_queue (内存队列)
  │
  └─→ crossval_worker (独立消费者线程)
        ├─ 从队列取任务
        ├─ 调用 LLM Judge (30s 硬超时)
        ├─ 写入判定结果 → scores.json
        └─ 失败重试 (最多 3 次，间隔 60s)
```

触发方式:
1. **手动触发:** `POST /api/eval/cross-validate/execute` → 入队（前端按钮）
2. **定时触发:** 后台 6h 周期 → 批量入队（`EVAL_CROSSVAL_ENABLED=true` 时）
3. **事件触发:** 累积 10 条以上 CROSSVAL_PENDING → 自动入队

队列设计:
- 内存队列 (`collections.deque`)，不引入 Redis/RabbitMQ
- 消费者为独立 daemon 线程，server.py 启动时创建
- 队列深度限制 50，超出时丢弃最旧任务并告警
- 消费者死亡 → `_daemon_heartbeat()` 在 2h 内检测到并告警

### 3.2 Judge Prompt 设计

```
你是评估系统的独立审查者。你的任务是交叉验证代码评分系统
对一条 Trace 的"数据完整度"判定是否正确。

**Trace 信息:**
- 名称: {trace_name}
- 类型: {trace_type}
- 实际记录的 Span 种类: {span_kinds_present}
- 该类型 Trace 必需的 Span 种类: {span_kinds_required}

**CODE 评分系统的判定:** {code_judgment} (complete/incomplete)

**你的任务:**
根据 Span 覆盖情况，独立判断这条 Trace 是否数据完整。
回答格式: {"judgment": "complete|incomplete", "reasoning": "...", "confidence": 0.0-1.0}
```

### 3.3 输出校验 (SA 约束 3)

```python
def _validate_llm_output(output: dict) -> bool:
    """LLM Judge 输出安全校验。不通过 → 拒绝写入 scores.json + 记录安全事件。"""
    # 评分值范围检查
    if not (0.0 <= output.get("value", -1) <= 1.0):
        _log_security_event("llm_value_out_of_range", output)
        return False
    # 文本字段长度限制
    for field in ("judgment", "reasoning"):
        if len(output.get(field, "")) > 1000:
            _log_security_event("llm_text_too_long", {"field": field})
            return False
    # XSS 防护: 拒绝包含脚本标签的输出
    for field in ("judgment", "reasoning", "note"):
        text = output.get(field, "")
        if any(tag in text.lower() for tag in ("<script", "<iframe", "javascript:")):
            _log_security_event("llm_xss_attempt", {"field": field})
            return False
    return True
```

### 3.4 成本控制

- 每次 Judge 调用最多采样 5 条 Trace
- 两次调用间隔 ≥ 6h（防风暴）
- 手动触发无限制（用户知情）
- 月度 LLM Judge 成本预估: 5 traces × ~500 tokens/trace × 30 天 ≈ 75K tokens ≈ ¥3-5

---

## 4. 元评估器设计

### 工程约束

1. **硬性超时**: 所有涉及 LLM 调用的元评估函数必须设 30 秒超时。超时则标记为 `status: "timeout"`，下次循环重试（最多 3 次）。
2. **独立运行日志**: 元评估日志写入 `data/eval/meta_eval.log`（JSONL 格式），不与业务 Trace（`traces.jsonl`）混在一起。方便调试"评估系统的评估系统"。
3. **独立运行器**: `meta_evaluator.py` 有自己的 `run_all()` 入口，可被 server.py 后台线程调用，也可被独立脚本手动触发（`python -m services.eval.meta_evaluator`）。
4. **内联展示**: 遵守 §2.3 约束 2。元评估结果不创建独立页面——`eval_system_freshness` 显示在雷达图上，其建议显示在建议列表中（`source: "meta_eval"`）。

### 4.0 Phase 1-3 过程合规审计

```python
def evaluate_phase3_adherence():
    """
    元评估最应该回答的第一个问题：
    Phase 3 确定的设计原则，在 Phase 3 执行中到底是被遵循了还是被妥协了？

    检查项:
      1. 红线1 (30秒信任法则): 信息层级是否严格按 告警→趋势→评分 渲染？
      2. 红线2 (零信任): 所有 /api/eval/* 端点是否有 _check_admin()？
      3. 红线3 (20英里行军): JS 模块是否超 300 行？eval-charts.js 是否垄断 new Chart()？
      4. 3 个兼容性修正是否在计划中标注了 trade-off？
      5. SECRET_KEY 复用是否作为已知风险记录？
      6. 文档覆写事件的防护措施是否落地？

    评分逻辑:
      - 每项通过 +1，妥协则记录 deviation 并扣分
      - 总分 / 6 → eval_process_adherence 指标
      - 未通过的项 → suggestion (severity=P1)
    """
```

**为什么这是第一优先:** 审计 AI 指出，元评估不应该仅仅是一个功能，它应该是一面镜子。在评估 ScoreConfig 新鲜度、LLM 一致性之前，先评估"我们承诺的设计原则兑现了吗"。

### 4.1 文档完整性审计

```python
def evaluate_document_integrity():
    """
    检测关键文档是否被非版本化覆写。
    基于 v3→v4 覆写事件的教训:
      - 扫描 docs/*.md 的 git log
      - 检测同一文件两次修改间隔 < 60 秒且第二次是 Write (覆写信号)
      - 检测文件修改量 > 500 行删减 (大量内容删除信号)
      - 检测已 git commit 的文档是否被后续 Write 覆写
    """
```

### 4.2 ScoreConfig 新鲜度

```python
def evaluate_score_configs():
    """
    检查每个 ScoreConfig 的审查间隔。
    >30 天未审查 → 标记为 stale
    >90 天未审查 → severity P1 suggestion
    """
```

**为什么需要:** v3→v4 覆写事件证明，关键配置（如 `TRACE_TYPE_SPAN_REQUIREMENTS`、`DEFAULT_SCORE_CONFIGS`）可能长期不被审查而过时。元评估器自动检测这种"评估标准退化"。

### 4.3 CODE vs LLM 一致性

```python
def evaluate_code_llm_consensus():
    """
    对比 data_completeness 的 CODE judgment 与 LLM judgment。
    不一致率 > 20% → CODE 评分逻辑可能有 bug。
    """
```

**为什么需要:** `_compute_data_completeness` 是纯 CODE 评分。如果 `_classify_trace_type` 的分类逻辑或 `TRACE_TYPE_SPAN_REQUIREMENTS` 定义有误，评分会系统性偏误且永远不会被发现——除非有独立的 LLM 交叉验证。

### 4.4 评分漂移检测

```python
def evaluate_score_drift():
    """
    检查所有活跃 config 的评分趋势。
    连续 7 天单调下降 → 系统在退化。
    """
```

### 4.5 知识库错误防护审查

```python
def evaluate_knowledge_base():
    """
    扫描 知识库/错误与修正与优化/ 中记录的每个错误，
    检查代码库中是否有对应的防护措施。
    
    错误类型 → 期望的防护:
      - v3→v4 文档覆写 → 是否有文档版本纪律文件？
      - sys.modules 双重恢复 → 是否有测试隔离检查？
      - 端点缺鉴权 → 是否有 auth 覆盖扫描？
    """
```

**为什么需要:** 会议讨论的核心问题——"如何保证犯过的错误不再犯"。元评估器将知识库中的错误记录与代码库中的防护措施关联起来。未防护的错误 = 待修复的 suggestion。

---

## 5. 动态 Golden Dataset

### 5.1 设计

```python
# data/eval/golden_dataset.json
{
  "samples": [
    {
      "sample_id": "golden_001",
      "trace_id": "abc123",
      "trace_name": "/api/agent/chat",
      "trace_type": "agent_chat",
      "expected_completeness": true,
      "expected_tool_accuracy": 0.85,
      "annotated_by": "human",
      "annotated_at": "2026-06-11T10:00:00",
      "notes": "正常 Agent 对话，LLM + TOOL 都记录了"
    }
  ]
}
```

### 5.2 演进机制

- 手动添加: 从 Dashboard 的 Trace 详情页点"添加到 Golden Dataset"
- Judge vs Golden: 新 Judge 判定与 Golden 对比，评估 Judge 质量
- Golden 自身审查: Judge 对 Golden 样本重新判定，不一致 → Golden 可能过时需要更新

---

## 6. 鉴权安全域分离 — EVAL_ADMIN_SECRET 迁移

> **审计 AI 警告:** SECRET_KEY 在 Flask 中的核心用途是加密会话、CSRF 令牌等。
> 将它暴露给评估系统鉴权，违反了最小权限和职责分离原则。
> Phase 4 必须纠正这个 Phase 3 的妥协。

### 6.1 问题

Phase 3 决定"鉴权重用 `config.SECRET_KEY`"（v4 三项兼容性修正之一），理由是"复用现有机制"。但从安全审计的角度：

- `SECRET_KEY` 的服务边界是 Flask 框架安全（session signing、CSRF tokens）
- eval 鉴权的服务边界是管理操作授权（采纳/拒绝建议、查看敏感评估数据）
- 这两个安全域不应共享同一个密钥——任何一方的泄漏都会波及另一方

### 6.2 迁移方案

```python
# config.py — 新增
EVAL_ADMIN_SECRET = os.environ.get("EVAL_ADMIN_SECRET", os.urandom(24).hex())
# 注意: EVAL_ADMIN_SECRET 不再 fallback 到 SECRET_KEY，确保独立
```

**迁移范围:**

| 文件 | 变更 |
|------|------|
| `config.py` | 新增 `EVAL_ADMIN_SECRET` |
| `routes/api_eval.py` | `_check_admin()` 改用 `config.EVAL_ADMIN_SECRET` |
| `services/eval/eval_store.py` | `apply_suggestion`/`reject_suggestion` 的 `admin_token` 校验改用 `config.EVAL_ADMIN_SECRET` |
| `templates/pages/eval.html` | `<meta name="admin-token">` 改用 `EVAL_ADMIN_SECRET` |
| `tests/test_eval_api.py` | `_auth_headers()` 改用 `config.EVAL_ADMIN_SECRET` |
| `tests/test_eval_core.py` | `admin_token` 参数改用 `config.EVAL_ADMIN_SECRET` |
| `tests/test_eval_engine.py` | `admin_token` 参数改用 `config.EVAL_ADMIN_SECRET` |
| `.env.example` | 标注 `EVAL_ADMIN_SECRET` 用途 |

### 6.3 向后兼容

- 如果 `EVAL_ADMIN_SECRET` 未设置，**不 fallback 到 SECRET_KEY**
- 启动时 `server.py` banner 打印警告: `⚠️ EVAL_ADMIN_SECRET is not set — eval admin endpoints will reject all requests`
- 这强制执行配置，防止"默认不安全"

---

## 7. 旧系统弃用计划

| 组件 | 操作 | 理由 |
|------|------|------|
| `services/review_agent.py` | 弃用，功能合并到 `meta_evaluator.py` | eval 系统已覆盖审查功能 |
| `services/review_store.py` | 弃用，合并到 `eval_store.py` | 统一数据存储 |
| `routes/api_review.py` | 端点重定向到 `/api/eval/*` | 统一 API 入口 |
| `services/review_memory.py` | 保留 (4 层记忆引擎) | eval 系统不覆盖记忆功能 |

---

## 8. 验证标准

1. ✅ `EVAL_ADMIN_SECRET` 独立于 `SECRET_KEY`，无 fallback
2. ✅ `evaluate_phase3_adherence()` 审计 Phase 1-3 设计原则兑现情况
3. ✅ `/cross-validate/execute` 从 501 → 200，返回 LLM Judge 结果
4. ✅ `/api/eval/meta/results` 返回真实元评估数据（非空数组）
5. ✅ `meta_evaluator.py` 五个评估函数均返回有效评分
6. ✅ LLM Judge 与 CODE 判定一致性可量化（`meta_results.json` 中记录）
7. ✅ 知识库中所有 P0/P1 错误都有对应的防护措施或已知缺口标注
8. ✅ `evaluate_document_integrity()` 检测非版本化文档覆写
9. ✅ 旧 `review_*` 端点返回 301 重定向或明确的弃用通知
10. ✅ LLM Judge 调用有 6h 防风暴保护
11. ✅ 元评估面板 UI 从占位 → 展示真实数据
12. ✅ 所有新增代码有测试覆盖 (≥ 85%)
13. ✅ 所有涉及 LLM 的测试必须 Mock 实际调用（禁止真实 API 请求在测试中执行）
14. ✅ 不引入新的付费 API 依赖（复用 DeepSeek client）
15. ✅ 30 秒信任法则盲测通过（真实用户，三个问题全部答对）
16. ✅ Dashboard 顶部横幅显示"评估系统自身健康度"指示器
17. ✅ 新增 UI 元素不引入新颜色、新图标类型、新图表类型（视觉词汇冻结）
18. ✅ 建议滑出面板包含"历史相似事件"区域（数据来源: doc_indexer + review_memory）
19. ✅ `_write_json`/`_append_jsonl` 自动快照，`data/eval/snapshots/` 保留最近 10 版
20. ✅ `config.EVAL_ADMIN_SECRET` 独立于 `config.SECRET_KEY`，无 fallback
21. ✅ 所有 LLM 输出经 `_validate_llm_output()` 校验后写入
22. ✅ `data/eval/audit.jsonl` 记录所有高权限操作
23. ✅ `grep -r 'sk-[a-zA-Z0-9]'` 返回零结果（无硬编码 API Key）
24. ✅ Phase 4 新增 CDN/pip 依赖固定版本 + integrity hash

---

## 9. 执行顺序

```
Pre-Phase 4: 清空 14 项待办 (11 P1 + 3 P2)
  ├─ P1-10: 🔴 EVAL_ADMIN_SECRET 独立迁移 (SA+审计: 安全域分离)
  ├─ P1-9: 评估数据文件自动快照 (SA 问题1: 数据完整性)
  ├─ P1-11: API 安全完成清单写入 CLAUDE.md (SA 问题2: 安全左移)
  ├─ P1-3: <template> + cloneNode 工程债务清理 (CE+IDC+SA 问题4)
  ├─ P1-4: _cross_validate_data_completeness() 测试补全 (CE 问题2)
  ├─ P1-5: _daemon_heartbeat() 后台任务健康检查 (CE 问题3)
  ├─ P1-6: p95 < 500ms 性能基准 (CE 问题4)
  ├─ P1-7: 30 秒信任法则盲测 (IDC 问题2)
  ├─ P1-8: 数据新鲜度指示器 + 影子模式操作反馈 (IDC 问题4)
  ├─ P1-1: 趋势线 annotation 标记点
  ├─ P1-2: 建议滑出面板 (含历史相似事件 + 审计日志)
  ├─ P2-12: Agent 三指标卡片
  ├─ P2-13: 告警卡片点击滚动
  └─ P2-14: 雷达图点击跳转
    ↓
Step 1: evaluate_phase3_adherence() — 先审计 Phase 1-3 过程合规
    ↓
Step 2: Golden Dataset (建基准)
    ↓
Step 3: llm_judge.py (异步任务队列 + LLM Judge + 输出校验层 + 视觉词汇冻结)
    ↓
Step 4: meta_evaluator.py (元评估函数 + 30s 超时 + 独立日志 + 内联展示)
    ↓
Step 5: evaluate_document_integrity() + 知识库评估集成
    ↓
Step 6: audit.jsonl + 自指全局指示器 + API 端点 + 前端面板
    ↓
Step 7: 旧系统弃用 + API Key 环境变量化 + 依赖安全审计
```

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| LLM Judge 自身不准确 | Golden Dataset 作为第三方参照；Judge 输出含 confidence 字段 |
| LLM 调用费用 | 6h 防风暴 + 每次最多 5 条 + 手动触发需显式确认 |
| 元评估器过于复杂 | 5 个独立函数，每个 < 60 行；Phase 4 不做元评估的元评估 |
| EVAL_ADMIN_SECRET 迁移打破现有鉴权 | 全量测试覆盖 + 启动时自检：若 EVAL_ADMIN_SECRET 未设则打印警告 |
| 旧系统弃用破坏现有功能 | 先重定向，确认无调用后删除 |
| 文档完整性审计误报 | 只检测 docs/*.md，排除 README；告警阈值 ≥ 500 行删减 |
| 异步消费者线程死亡 | `_daemon_heartbeat()` 检测消费者心跳，>2h 无心跳 → P0 告警 |
| LLM 调用 30s 超时导致数据丢失 | 失败标记 `status: timeout`，下次循环重试 (最多 3 次) |
| `<template>` 迁移引入回归 | 逐组件迁移（先 Span 树 → 再建议卡片 → 再评分卡），每步全量测试通过再继续 |
| 快照目录膨胀 | 保留最近 10 版，超出自动清理；快照总大小监控告警 |
| LLM Prompt Injection 污染评分 | `_validate_llm_output()` 校验层拒绝 `<script>`/`<iframe>`/值域外数据 |
| API Key 硬编码残留 | `grep -r 'sk-[a-zA-Z0-9]'` 零结果检查，纳入 CI |
| `innerHTML` 绕过 escapeHtml 直接拼接 | 代码审查阻塞项：`innerHTML` + 动态数据若无注释说明安全理由 → 拒绝合并 |

---

## 11. 与审计和会议议题的关联

Phase 4 直接回应 6/10 会议三个战略议题 + 审计 AI 四个深层问题 + 总工程师四个工程偏差。

### 会议议题

1. **知识库评估** → `meta_evaluator.evaluate_knowledge_base()` 提供自动化机制
2. **错误不再犯** → 每个知识库错误记录对应代码库防护检查，未防护的自动生成 suggestion
3. **评估系统自指** → Phase 4 的核心就是"评估系统评估自身"

### 审计 AI (流程与逻辑)

1. **文档覆写是流程黑洞** → `evaluate_document_integrity()` + 文档版本铁律写入 CLAUDE.md
2. **测试破坏全局状态** → 已修复 sys.modules 操作，Phase 4 评估依赖注入重构
3. **SECRET_KEY 复用是安全捷径** → Phase 4 Step 0: EVAL_ADMIN_SECRET 独立迁移
4. **元评估应是镜子** → `evaluate_phase3_adherence()` 作为 meta_evaluator 第一优先函数

### 总工程师 (工程与架构)

1. **innerHTML 是技术债务** → Pre-Phase 4: `<template>` + cloneNode 迁移 (P1-3)
2. **cross-validate 是纸面功能** → Pre-Phase 4: 测试补全，验证请求结构符合 LLM Judge 契约 (P1-4)
3. **后台任务无健康检查** → Pre-Phase 4: `_daemon_heartbeat()` + 2h 超时 P0 告警 (P1-5)
4. **性能基准不可推迟** → Pre-Phase 4: p95 基准从 P3 提升到 P1，100 次请求测量 (P1-6)

### 交互设计顾问 (用户体验与信息架构)

1. **innerHTML 锁死交互扩展** → Pre-Phase 4: `<template>` + cloneNode 用 `dataset` 属性携带数据（同 CE 问题1，UX 视角补充）
2. **30 秒信任法则从未验证** → Pre-Phase 4 P1-7: 真人盲测，任何一个问题答不上来 → Phase 4 第一项工作是修复信息层级
3. **6 项交互缺口是承重墙而非装饰** → P1 两项作为 Phase 4 前置条件；P2 三项在 Phase 4 中期交付；annotation 标记点不是"好看"而是"回答为什么"
4. **评估系统自身交互反馈缺失** → Pre-Phase 4 P1-8: 数据新鲜度指示器 + 影子模式操作反馈 tooltip
5. **知识库评估是信息架构断层** → Phase 4: 建议滑出面板"历史相似事件"区域 — Dashboard 从"描述问题"升级为"提供解决方案"

### 安全审计师 (数据完整性与安全左移)

1. **文档覆写的真正病灶是数据完整性缺失** → Pre-Phase 4 P1-9: `_write_json`/`_append_jsonl` 自动快照，保留最近 10 版。覆写事件升级为安全事件
2. **鉴权遗漏是安全左移流程缺陷** → Pre-Phase 4 P1-11: API 安全完成清单写入 CLAUDE.md。安全不是功能完成后的补充，是功能完成的前提
3. **SECRET_KEY 复用是单点凭证风险** → Pre-Phase 4 P1-10: EVAL_ADMIN_SECRET 独立迁移。不同安全域使用不同凭证，"复用现有机制"适用于代码结构，不适用于凭证管理
4. **escapeHtml 是 XSS 防护的单点故障** → 同 CE/IDC: `<template>` + cloneNode + textContent 是默认安全的方案。迁移后 `innerHTML` + 动态数据 → 代码审查阻塞项

### Phase 4 全部约束汇总

| 视角 | 约束 |
|------|------|
| 审计 AI | 文档版本铁律 / 测试隔离 / 安全域分离 / 元评估自指 |
| 总工程师 | `<template>` 迁移 / 异步任务队列 / 超时重试 / 慢路径 Mock |
| 交互设计 | 视觉词汇冻结 / 元评估内联 / 自指全局指示器 / 历史智慧接入 |
| 安全审计 | 数据自动快照 / 安全完成清单 / LLM 输出校验 / 审计日志 / API Key 环境变量 / 依赖安全 |

Phase 3 建设中暴露的问题恰恰证明了：
**如果没有元评估，评估系统自身的缺陷会静默累积。** Phase 4 就是那个"不再让缺陷静默累积"的机制。而四位审查者从流程、工程、交互、安全四个视角照出的全部已知问题，已在 Pre-Phase 4 和 Phase 4 执行步骤中逐项映射。
