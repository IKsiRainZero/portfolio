# Phase 4 执行报告 — 2026-06-11

> **提交对象:** 团队会议审查
> **执行时间:** 2026-06-11 (单日)
> **Commits:** 2 个 (Pre-Phase 4 + Phase 4 主体)，在前序 10 个总裁命令 commit 之上

---

## 1. 执行概况

### 1.1 完整 Commit 链 (12 commits, 可独立回滚)

```
2a64a36 Phase 4 主体 — meta_evaluator + LLM Judge + Golden Dataset
3128377 Pre-Phase 4 收尾 — 8 项 UI/后端补全
5becff1 Command 1 ✅ 30s 信任盲测结果
f7f77a3 fix: 趋势线时间排序修正
a3a5319 fix: 总览加载销毁DOM + sparkline无限拉伸
0035a7a Command 1 盲测模板
224c914 Command 5 ✅ p95=21.7ms 性能基准
cb111f8 Command 4 ✅ <template> + cloneNode 架构恢复
a3eb479 Command 3 ✅ 数据自动快照
a60b4be Command 2 ✅ EVAL_ADMIN_SECRET 独立
270fa87 总裁最终批复记录
a60f1ce Phase 4 计划 v5 + checkpoint + 安全清单
```

**回滚策略:** 每条 commit 独立。`git revert 2a64a36` 可只回滚 Phase 4 主体，不影响前序 10 个 commit。

### 1.2 量化统计

| 维度 | 数据 |
|------|------|
| 新增文件 | 3 (`meta_evaluator.py`, `llm_judge.py`, `golden_dataset.py`) |
| 修改文件 | 8 (eval_engine, eval_store, server, api_eval, api_review, 3 JS modules, eval.html) |
| 新增代码行 | ~1,300 行 |
| 新增 ScoreConfig | 5 (eval_process_adherence, code_llm_consensus, score_drift, document_integrity, kb_protection_coverage) |
| 新增 API 端点行为变更 | 2 (`/cross-validate/execute` 501→200, `/meta/results` stub→真实数据) |
| 测试 | 140 pass, 0 fail |
| Flask 加载 | 正常 |

---

## 2. 执行思路

### 2.1 方法论: 计划驱动 + 最小可行

Phase 4 计划文档 (`docs/phase4-plan.md` v5) 是本次执行的核心参照。执行严格遵循计划中的 §9 执行顺序，不做计划外的扩展。

**核心原则:**
1. **Pre-Phase 4 先清空** — 带着缺口进入 Phase 4 会让排查成本倍增 (计划原文)
2. **每步可验证** — 每个 Step 完成后运行全量测试 (140 tests)
3. **不调用付费 API** — LLM Judge 的 DeepSeek 调用只在手动触发时执行，后台 6h 防风暴保护
4. **安全左移** — 安全约束 (§2.4 SA 约束 1-6) 与功能代码同步实现，不是事后补充

### 2.2 实际执行顺序 (与计划 §9 对照)

```
Pre-Phase 4 剩余 8 项 (P1-1/2/4/5/8, P2-12/13/14)
  ├─ P1-5: 守护心跳 (后端, 先做)
  ├─ P1-4: 交叉验证测试补全 (后端, 与 P1-5 并行)
  ├─ P1-8: 数据新鲜度指示器 (前端)
  ├─ P1-1: 趋势标注标记点 (前端)
  ├─ P2-13/14: 告警/雷达点击联动 (前端)
  ├─ P2-12: Agent 三指标卡片 (前端)
  └─ P1-2: 建议滑出面板 (前端, 最复杂)
    ↓ 提交 3128377
Step 1: evaluate_phase3_adherence() — 过程合规审计
Step 2: Golden Dataset — 基准数据集
Step 3: llm_judge.py — LLM Judge + 异步队列
Step 4: meta_evaluator 核心函数 (3 个)
Step 5: 文档完整性 + 知识库评估 (2 个)
Step 6: 审计日志 + 自指指示器 + 前端面板更新
Step 7: 旧系统弃用 + API Key 审计
    ↓ 提交 2a64a36
```

---

## 3. 已完成项 vs 计划对照

### 3.1 Pre-Phase 4 (14/14 全部完成)

| # | 项目 | 状态 | 验收 |
|---|------|------|------|
| P1-1 | 趋势线 annotation 标记点 + hover tooltip | ✅ | 蓝色圆点=suggestion_applied, 灰色=commit, hover 显示 value_before→value_after |
| P1-2 | 建议滑出面板 | ✅ | 320px 侧边栏, 完整生命周期, 历史相似事件区域, 点击遮罩/×关闭 |
| P1-3 | `<template>` + cloneNode | ✅ | 总裁 Command 4 已完成 |
| P1-4 | cross-validate 测试补全 | ✅ | 验证 trace_id 等 5 必填字段 |
| P1-5 | 守护心跳 | ✅ | heartbeat.json + 2h 超时 P0 告警 |
| P1-6 | 性能基准 | ✅ | 总裁 Command 5 已完成, p95=21.7ms |
| P1-7 | 30s 信任盲测 | ✅ | 总裁 Command 1 已完成, Round 2 通过 |
| P1-8 | 数据新鲜度 + 影子模式反馈 | ✅ | "X分钟前" + >60min 橙色 + disabled 按钮 tooltip |
| P1-9 | 数据自动快照 | ✅ | 总裁 Command 3 已完成 |
| P1-10 | EVAL_ADMIN_SECRET | ✅ | 总裁 Command 2 已完成 |
| P1-11 | 安全清单写入 CLAUDE.md | ✅ | 已完成 |
| P2-12 | Agent 三指标卡片 | ✅ | 成功率 + Trace数 + 平均耗时 |
| P2-13 | 告警点击滚动 | ✅ | 点击告警 → switchTab('details') + 平滑滚动 + 高亮闪烁 |
| P2-14 | 雷达图点击跳转 | ✅ | onClick → scrollToCard(configId) |

### 3.2 Phase 4 主体 (7/7 步骤全部完成)

| Step | 模块 | 状态 | 关键产出 |
|------|------|------|----------|
| 1 | `evaluate_phase3_adherence()` | ✅ | 审计 6 项设计原则, 得分 4/6 |
| 2 | `golden_dataset.py` | ✅ | load/add/evaluate_against, 首次 import 自动初始化 |
| 3 | `llm_judge.py` | ✅ | 异步队列 + 消费者线程 + `_validate_llm_output()` |
| 4 | 元评估核心函数 ×3 | ✅ | score_configs/consensus/drift |
| 5 | 文档完整性 + KB 评估 | ✅ | git log 覆写检测 + 知识库防护覆盖 |
| 6 | 审计日志 + 指示器 + 前端 | ✅ | audit.jsonl + 自指横幅 + meta 面板真实数据 |
| 7 | 旧系统弃用 + 安全审计 | ✅ | review API 弃用头 + API Key 零硬编码验证 |

---

## 4. 困难和错误

### 4.1 遇到的问题

**问题 1: git subprocess 编码错误 (Windows GBK vs UTF-8)**
- 现象: `evaluate_document_integrity()` 中 `subprocess.run(text=True)` 在中文 Windows 上默认用 GBK 解码，git log 输出的 UTF-8 字符导致 `UnicodeDecodeError`
- 修复: 显式设置 `encoding="utf-8", errors="replace"`，同时防御 `r.stdout` 为 None 的情况
- 教训: Windows 平台上的 subprocess 文本模式不可信赖默认编码，必须显式指定

**问题 2: eval-main.js 超出 300 行红线**
- 现象: `evaluate_phase3_adherence()` 检测到 eval-main.js 483 行 (红线3 限制 300 行)
- 根因: 滑出面板 + Agent 卡片 + 新鲜度指示器 + 自指指示器全部内联在 assemble 函数中
- 状态: **未修复** — 这是一个被检测到的偏差。滑出面板逻辑可以提取到独立模块 (`eval-slideout.js`)，但当前阶段优先完成功能而非架构整洁
- 是否需会议决策: 是

**问题 3: 多个前端任务修改同一文件导致编辑冲突**
- 现象: Edit 工具在处理 tab 缩进文件时频繁因空白字符不匹配而失败
- 修复: 对于需要多处修改的文件 (eval-main.js, eval-charts.js)，改用 Write 全量覆写
- 教训: 这是文档版本铁律中提到的风险——Write 覆写会丢失增量历史。对于 JS 模块，后续应优先考虑拆分以降低单文件修改频率

### 4.2 实际犯的错误

**错误 1: replace_all 误伤测试断言**
- 操作: 将 `11` replace_all 为 `15` 以更新 ScoreConfig 数量断言
- 风险: 如果测试文件中有其他 `11` (如 delta 值 0.11)，会被误改
- 实际影响: 未发生——测试文件中 `11` 只出现在 config 数量断言中
- 教训: `replace_all` 是危险操作。更安全的做法是逐个 Edit 替换，或仅在有充分把握时使用

**错误 2: `_audit_log` 定位偏差**
- 初始思路: 在 `apply_suggestion` 函数开头添加审计日志
- 实际问题: 函数有提前返回路径 (suggestion not found → None)，审计日志应只在成功路径写入
- 修复: 将 `_audit_log()` 调用移到 `_save_suggestion()` 之后、`return` 之前
- 教训: 审计日志的调用位置必须覆盖所有成功路径且仅覆盖成功路径

---

## 5. 测试覆盖

### 5.1 后端测试 (140 pass)

| 测试类 | 覆盖内容 |
|--------|----------|
| TestBugFixRegression | orphan confirmed 持久化 + query_scores 过滤 |
| TestCleanupOrphanSpans | 空集/跳过/防崩盖 |
| TestDataCompleteness | 冷启动/完整/缺失/rag/save/system_task/异常 |
| TestPriorityViolation | P1下降/P3不违规/全正/未知/降级 |
| TestEffectTracking | 无建议/无基线/git冲突/违规/正向delta/防崩盖 |
| TestAggregationQuery | 列表/过滤 |
| TestSeedScoreConfigs | 创建15/幂等/user_value_statement/宪法weight=0 |
| TestReviewTriggerOnViolation | 成功/异常/防风暴/影子模式 |
| TestCrossValidation | 不足/生成/5字段验证/incomplete/异常 |
| TestShadowModeIntegration | 三任务不崩/traces不写 |
| TestOrphanErrorHealthCheck | 空集/混合/error_count |
| TestQueryTraces | 窗口过滤/空数据/接口兼容 |
| TestOrphanReattachment | 时间窗口重关联/超1h确认 |
| TestDaemonSmoke | 三任务/有数据/单任务容错/心跳 |

### 5.2 前端测试

前端无自动化测试。信任依赖:
1. 30s 盲测 (Round 2 通过, 20s)
2. Flask 加载验证 (无 JS 语法错误导致 500)
3. Chart.js 渲染验证 (手动检查)

**风险评估:** 前端回归依赖人工。新增的滑出面板、自指指示器、meta 面板均未经第二人盲测。

---

## 6. 待会议决策的问题

### 6.1 红线3 违规: eval-main.js 483 行

`evaluate_phase3_adherence()` 自动检测到此偏差。**建议:**
- 方案 A: 接受现状，将红线3 从 300 行放宽到 500 行 (风险: JS 模块持续膨胀)
- 方案 B: 提取 `_showSlideOut()` 到 `eval-slideout.js` (~80 行，立即降到 400 行以下)
- 推荐: 方案 B，作为 Phase 5 第一项工作

### 6.2 LLM Judge 从未被真实调用

`llm_judge.py` 的异步消费者线程已启动，但 `run_crossval_batch()` 需要手动 POST `/api/eval/cross-validate/execute` 且设置 `force=true` 才会入队。防风暴保护 (6h) 阻止了所有自动触发。

**当前状态:** `_crossval_queue` 为空，`_worker_thread` 运行中但 idle。

**建议:** 会议决定是否进行一次手动触发来验证 LLM Judge 端到端流程。成本估算: 5 traces × ~500 tokens = ~2,500 tokens ≈ ¥0.1-0.2。

### 6.3 元评估的元评估缺失

Phase 4 计划 §10 明确写了"Phase 4 不做元评估的元评估"。但 `evaluate_phase3_adherence()` 自身是否准确？它的 6 项检查中，"兼容性修正 trade-off 标注" 是通过关键词匹配实现的——可能漏检也可能误检。

**建议:** 先接受这个限制。Phase 5 可以引入人工抽检来校准 meta_evaluator 的准确性。

### 6.4 知识库评估的文件编码假设

`evaluate_knowledge_base()` 假设知识库文件在 `ROOT_DIR.parent / "知识库" / "错误与修正与优化"` 下。如果知识库目录结构变化，此函数会静默返回空结果。

**建议:** 将知识库路径提取为配置常量。

---

## 7. 下一步

Phase 4 计划仅在 §1.2 将"自动回滚/自动修复"标记为 `(Phase 5)` 推迟项，并未定义 Phase 5 的范围或计划。当前没有 Phase 5 计划文档。

基于本次执行暴露的问题，建议后续优先:

1. **前端模块拆分** (eval-main.js → eval-slideout.js) — 修复红线3 违规
2. **LLM Judge 端到端验证** — 至少一次真实调用
3. **第二人盲测 Round 3** — 验证新增的 meta 面板和自指指示器
4. **meta_evaluator 准确性校准** — 人工审查评估结果的合理性
5. 以上完成后，重新评估是否需要编写 Phase 5 计划

---

## 附录 A: 文件变更清单

### 新增文件
| 文件 | 行数 | 职责 |
|------|------|------|
| `services/eval/meta_evaluator.py` | ~320 | 6 个元评估函数 + run_all() 入口 |
| `services/eval/llm_judge.py` | ~260 | 异步队列 + LLM Judge + 安全校验 |
| `services/eval/golden_dataset.py` | ~120 | Golden Dataset CRUD + 对比评估 |

### 修改文件
| 文件 | 变更概要 |
|------|----------|
| `services/eval/eval_engine.py` | +守护心跳 +5 个新 ScoreConfig + daemon_stale 告警 |
| `services/eval/eval_store.py` | +_audit_log() + apply/reject 审计 |
| `server.py` | +LLM Judge worker 启动 + 元评估 6h 周期 + 心跳写入 |
| `routes/api_eval.py` | cross-validate/execute 501→200, meta/results stub→真实 |
| `routes/api_review.py` | 弃用头 + 迁移指引 |
| `static/js/modules/eval-main.js` | +新鲜度 +滑出面板 +自指横幅 +Agent卡片 +alert点击 +scrollToCard |
| `static/js/modules/eval-charts.js` | +趋势标注 +hover tooltip +雷达onClick |
| `static/js/modules/eval-ui.js` | +alert data-config-id |
| `templates/pages/eval.html` | +新鲜度元素 +滑出面板容器 +自指指示器 |
| `tests/test_eval_engine.py` | +心跳测试 +crossval 5字段验证 +config数量更新 |
