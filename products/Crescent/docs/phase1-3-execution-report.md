# Phase 1–3 评估系统建设执行报告

> 时间跨度: 2026-06-08 → 2026-06-10  
> 目标: 从零建造一个评估仪表盘系统，让不了解技术细节的干系人 30 秒内判断系统健康状态  
> 当前状态: 核心功能可用，6 项交互优化待完成，171 测试通过

---

## 一、时间线

### 前置阶段: Review 系统 + Phase A 规划 (6/7–6/8)

```
6/7  a193bf4  论文发现→结构化提取→知识库导入管道
6/8  b79474f  doc_indexer — 错误文档/checklist/checkpoints/论文的结构化索引
     b3d3b09  review_memory — 4 层记忆引擎 + ChromaDB 归档
     bfb963d  ReviewAgent — LLM 分析 + 文件修改 + 自指参数 + 自动触发
     93c2234  token 统计增加 task_type 维度
     32d3989  review API 端点 + review_bp 注册 + 后台自动触发线程
     9e7e653  Phase A plan v4 — 首席工程师审查修正
```

**关键决策**: Phase A 规划中确定了 eval 系统的架构方向——三条链（埋点→评分→元评估），但 v3→v4 计划覆写事件暴露了文档版本管理的系统性漏洞。

### Phase 1: 核心埋点系统 (6/10 上午)

```
90dde5c feat: Phase 1 — 强制性核心埋点系统 (链1: 行为→数据)
```

**做了什么**:
- `services/eval/trace_logger.py` — Trace/Span 记录器，基于 JSONL 文件存储
  - `start_trace()` / `end_trace()` / `_record_span()`
  - `TraceContext` 上下文管理器（with 语句自动管理生命周期）
  - 孤儿 Span 检测（trace_id=None → orphan=True）
- `services/eval/eval_store.py` — 数据存储层
  - `traces.jsonl` / `scores.json` / `suggestions.json` / `meta_results.json`
  - `list_orphan_spans()` / `find_trace_by_window()` / `attach_span_to_trace()`
  - `_read_jsonl()` / `_read_json()` / `_write_json()` 底层 I/O
  - ScoreConfig 管理（`list_score_configs()` / `save_score_config()`）
  - Suggestion 生命周期管理（`add_suggestion()` / `apply_suggestion()` / `reject_suggestion()`）
  - Git 冲突检测（`_get_current_commit_sha()` / `_git_commits_touching_file()`）
- `services/eval/eval_engine.py` — 评分引擎骨架
  - 10 个 ScoreConfig 定义（2 宪法 + 8 标准）
  - `_classify_trace_type()` — 从 trace name 推断类型
  - `_compute_data_completeness()` — 宪法 Metric（CODE 评分）
  - `_cleanup_orphan_spans()` — 孤儿 Span 清理
- `server.py` 集成 — `before_request` / `after_request` 钩子自动追踪所有 HTTP 请求
- **测试**: `tests/test_eval_core.py` — 139 tests, 89% 覆盖率

**遇到的错误**:
- `_record_span()` 的 `token_count` 参数与 `agent_service.py` 调用方签名不一致 → 统一为可选参数
- Trace 类型分类逻辑需要从实际 trace name 模式推导（`/agent/` → agent_chat 等），不能从文档假设

### Phase 1 P1/P2 遗留项修复 (6/10 中午)

```
8baad85 fix: Phase 1 P1/P2 遗留项 — 交叉验证 + 影子模式守卫 + 孤儿错误追踪 + 查询抽象
```

**做了什么**:
- Item 2 (P1): `_cross_validate_data_completeness()` — 从最近 24h traces 随机采样，生成 LLM 交叉验证请求，不自动调用 LLM（避免费用）
- Item 1 (P1): server.py 影子模式状态 banner + 集成测试
- Item 4 (P2): `_orphan_error_health_check()` — 孤儿 Span 中 error 占比追踪 + ScoreConfig `orphan_error_rate`
- Item 3 (P2): `_query_traces()` — 统一 Trace 查询入口，封装 JSONL 存储细节
- Item 6 (P2): orphan cleanup 集成测试（重关联 + 超1h确认）

### Phase 2: 因果循环引擎 (6/10 下午)

```
c5ba05a feat: Phase 2 — 因果循环引擎 (链2: 数据→行动)
```

**做了什么**:
- `_effect_tracking_loop()` — 已应用 >24h 未验证效果的建议自动追踪
  - 对比基线 vs 当前评分
  - Git 冲突检测（`_git_commits_touching_file()`）
  - 归因判定（attributed / unattributable / likely_failed）
  - 红线违规触发审查（`_trigger_review_on_violation()`）
- `_check_priority_violation()` — 优先级 1-2 的指标负 delta → 违规标记
- `_aggregation_query()` — 评分聚合查询（默认排除空 Trace + 孤儿 Span）
- `_seed_score_configs()` — 首次运行时注册所有 ScoreConfig（幂等）
- server.py 后台线程: 每 1h 运行三任务（cleanup + tracking + completeness）

### Phase 3: 前端 Dashboard (6/10 下午–晚上)

#### 3.1 计划阶段

**v3 计划** (完整版，~850 行):
- 战略定位: "信任仪表盘" 而非 "数据展览厅"
- 三大红线: 30秒信任法则、零信任安全、20英里行军
- JS 模块拆分（4 个文件，职责矩阵）
- UI 组件模式（`<template>` + cloneNode）
- 数据加载与降级策略
- 鉴权架构（双重校验）
- JSON 数据契约（3 个端点完整字段描述）
- Step 0-6 详细执行规格
- 13 项验证标准

**v3→v4 覆写事件** 🔴:
- v4 使用 Write 工具直接覆写 `docs/phase3-plan.md`
- 500+ 行详细规格丢失（JS 模块矩阵、UI 模式、数据加载策略、鉴权架构图、数据契约字段描述、Step 0-6 详细规格、13→8 验证标准压缩）
- 丢失内容事后从 git diff 手动拼凑恢复 → v5
- **教训**: 文档没有 git 回滚保护意识；Write 工具覆写语义理解偏差；缺少"改版先存旧版"纪律
- **详细记录**: `知识库/错误与修正与优化/2026-06-10.md`

**v5 计划** (恢复版):
- 恢复 v3 全部详细规格
- 保留 v4 的 3 项兼容性修正（SECRET_KEY 复用、`_build_alerts()` 实现、JS 命名空间模式）
- 新增 §10 实现现状标注（13 项验证标准逐项追踪）

#### 3.2 构建阶段

**Step 0: 基础设施**
- `routes/pages.py`: `/eval` 路由 → `eval.html` + `admin_token`
- `templates/base.html`: Chart.js CDN + "评估系统" 侧边栏导航
- 4 个 JS 模块文件骨架（命名空间模式: `window.EvalAPI` / `window.EvalCharts` / `window.EvalUI` / `window.EvalMain`）

**Step 1: API 端点**（`routes/api_eval.py`）
- `_check_admin()` — 统一鉴权（X-Admin-Token 匹配 config.SECRET_KEY）
- 9 个端点: summary / configs / trend / traces / trace_detail / suggestions / meta_results / apply / reject
- 影子模式写保护: `_check_shadow_mode()` → 403
- `_build_summary()` (在 `eval_engine.py`): 4 个 try/except 块 + errors[] 数组 + sparklines 数据

**Step 2-5: 前端构建**
- `eval.html` — 4 个 Tab 面板 + CSS 设计系统 + 影子模式横幅 + 响应式布局
- `eval-api.js` — 唯一 fetch 封装，自动携带 X-Admin-Token，3s 超时警告
- `eval-charts.js` — Chart.js 唯一入口，5 种图表配置工厂函数
- `eval-ui.js` — 6 个单组件渲染函数，escapeHtml 防护，5 种 Span 状态视觉映射
- `eval-main.js` — 面板组装 + Tab 切换 + 60s 轮询 + 错误降级

**Step 6: 导航入口 + 影子模式指示**

#### 3.3 测试

**`tests/test_eval_api.py`** (32 tests):
- TestAuth (3): 无 token → 403 / 错误 token → 403 / 正确 token → 200/404
- TestShadowModeWriteProtection (2): apply/reject → 403
- TestSummaryEndpoint (3): 字段完整性 / errors 始终数组 / 部分失败容错
- TestConfigsEndpoint (2): 列表返回 / 必填字段
- TestTrendEndpoint (2): points+annotations / days 参数
- TestTracesEndpoint (2): 列表返回 / 不存在返回 404
- TestSuggestionsEndpoint (3): 列表/status 筛选/severity 筛选
- TestMetaResultsEndpoint (1): 列表返回 + updated_at 字段
- TestWriteEndpoints (4): apply/reject 不存在→404 / apply 完整流程 / reject 完整流程
- TestCrossValidateEndpoint (3): 无 traces→skipped / 有 traces→pending / execute→501
- TestScoresEndpoint (2): 列表/config_id 筛选
- TestStoreLayerAuth (4): apply/reject 无 token / 错 token → PermissionError

#### 3.4 对照检查与修复 (今晚)

计划 v5 逐项交叉对照实际代码，发现 8 项偏离，修复 4 个 commit:

| Commit | 内容 | 严重度 |
|--------|------|--------|
| `f270cc7` | cross-validate / cross-validate-execute / scores 3 个端点缺鉴权 | 🔴 安全 |
| `9028a1a` | meta results 端点缺 `updated_at` 字段 | 🟡 契约 |
| `57eae5e` | error Span 加粗 + sparkline 渲染 + 评分卡 delta + 3s 超时 | 🟡 UI |
| `39e0412` | 空状态消息改进 + annotations 空时占位 | 🟡 UX |

---

## 二、架构总览

```
┌─────────────────────────────────────────────────────┐
│                      链1: 埋点                       │
│  server.py before/after_request → trace_logger.py   │
│  → traces.jsonl (所有 HTTP 请求自动追踪)              │
├─────────────────────────────────────────────────────┤
│                      链2: 评分                       │
│  eval_engine.py (每小时后台任务)                      │
│  ├─ _cleanup_orphan_spans()    孤儿清理               │
│  ├─ _compute_data_completeness() 数据完整度(宪法)      │
│  ├─ _effect_tracking_loop()    效果追踪               │
│  ├─ _orphan_error_health_check() 孤儿错误率            │
│  └─ _build_summary()           Dashboard聚合          │
│  → scores.json + suggestions.json                    │
├─────────────────────────────────────────────────────┤
│                      链3: 仪表盘                     │
│  eval.html + 4 JS模块                                │
│  ┌────────────┬─────────────┬──────────┬────────┐    │
│  │ eval-api   │ eval-charts │ eval-ui  │eval-main│   │
│  │ fetch唯一入口│ Chart唯一入口 │ 单组件渲染 │面板组装  │   │
│  └────────────┴─────────────┴──────────┴────────┘    │
│  → 9 个 API 端点 (全部 X-Admin-Token 鉴权)            │
├─────────────────────────────────────────────────────┤
│                   Phase 4: 元评估                     │
│  meta_evaluator.py + LLM Judge (计划中)               │
└─────────────────────────────────────────────────────┘
```

### 数据文件

| 文件 | 用途 | 格式 |
|------|------|------|
| `data/eval/traces.jsonl` | Trace + Span 数据 | JSONL 追加写 |
| `data/eval/scores.json` | 评分记录 | JSON 读写 |
| `data/eval/suggestions.json` | 建议生命周期 | JSON 读写 |
| `data/eval/configs.json` | ScoreConfig 注册表 | JSON 读写 |
| `data/eval/meta_results.json` | 元评估结果 (Phase 4) | JSON 读写 |

---

## 三、遇到的问题与解决

### 问题 1: 11 测试失败 — PermissionError: X-Admin-Token required
**原因**: `apply_suggestion()` / `reject_suggestion()` 新增 `admin_token` 参数，但测试调用未传递。  
**解决**: 两个测试文件添加 `import config`，所有 11 个调用点传入 `admin_token=config.SECRET_KEY`。

### 问题 2: 同样 11 测试 + 3 更多失败 — 影子模式写操作已禁用
**原因**: `eval_store.py` 中有冗余的 `EVAL_SHADOW_MODE` 检查，API 层已经守卫。计划中"双重校验"指 API 层 + 数据层 admin_token 校验，不是 API + store 都检查影子模式。  
**解决**: 移除 `eval_store.py` 中的影子模式检查，保留 `admin_token` 参数校验。

### 问题 3: test_priority_violation_import_config_fails 破坏 sys.modules
**原因**: 测试先 `sys.modules.pop("config")` 再 monkeypatch，pytest teardown 和 finally 块双重恢复导致 config key 从 sys.modules 消失。  
**解决**: 完全交由 monkeypatch 管理生命周期，不手动 pop/restore。

### 问题 4: test_cross_validate_with_traces 返回 "skipped" 而非 "pending"
**原因**: Trace 名称 `/test/cv_0` 不匹配 `_classify_trace_type` 的模式（需要 `/agent/` 或 `/api/agent/` 在名称中）。  
**解决**: 测试 trace 名改为 `/api/agent/cv_{i}`。

### 问题 5: v3 计划被 v4 覆写，500+ 行规格丢失 🔴
**原因**: Write 工具覆写语义理解偏差 + 缺少文档版本纪律 + 审查流程缺失。  
**解决**: 从 diff 手动重建 v5 + 新增强制版本纪律 + 独立 commit。  
**详细记录**: `知识库/错误与修正与优化/2026-06-10.md`

### 问题 6: cross-validate / scores 端点缺少鉴权
**原因**: 这 3 个端点在原有代码中就存在，Phase 3 新增 `_check_admin()` 时遗漏了它们。  
**解决**: 添加 `_check_admin()` 守卫 + 更新测试覆盖。

---

## 四、当前现状

### 已完成 ✅

| 组件 | 文件 | 状态 |
|------|------|------|
| 埋点系统 | `services/eval/trace_logger.py` | ✅ 完成 |
| 数据存储 | `services/eval/eval_store.py` | ✅ 完成 |
| 评分引擎 | `services/eval/eval_engine.py` | ✅ 完成 |
| API 端点 (9个) | `routes/api_eval.py` | ✅ 完成 |
| Dashboard 模板 | `templates/pages/eval.html` | ✅ 完成 |
| JS API 层 | `static/js/modules/eval-api.js` | ✅ 完成 |
| JS 图表层 | `static/js/modules/eval-charts.js` | ✅ 完成 |
| JS UI 层 | `static/js/modules/eval-ui.js` | ✅ 完成 |
| JS 主控层 | `static/js/modules/eval-main.js` | ✅ 完成 |
| 导航 + 影子横幅 | `templates/base.html` + `eval.html` | ✅ 完成 |
| API 测试 | `tests/test_eval_api.py` (32 tests) | ✅ 完成 |
| 引擎测试 | `tests/test_eval_engine.py` | ✅ 完成 |
| 核心测试 | `tests/test_eval_core.py` | ✅ 完成 |
| 安全: 所有端点鉴权 | `routes/api_eval.py:_check_admin()` | ✅ 完成 |
| 安全: 影子模式写保护 | API 403 + 前端横幅 | ✅ 完成 |
| 降级: 部分失败容错 | `_build_summary()` errors[] | ✅ 完成 |
| 降级: 加载/超时/错误处理 | `eval-main.js` catch 分支 | ✅ 完成 |

### 未完成 ❌ (6 项已知缺口)

| 优先级 | 项目 | 影响 | 文件 |
|--------|------|------|------|
| P1 | 趋势线 annotation 标记点 | 趋势图和变更标注割裂 | `eval-charts.js` |
| P1 | 建议滑出面板 (Slide-out) | 建议无完整生命周期展示 | `eval-ui.js` + `eval.html` |
| P2 | Agent 三指标卡片 | Agent 面板缺聚合指标 | `eval-main.js` |
| P2 | 告警点击滚动到详情 | 告警和详情无联动 | `eval-ui.js` + `eval-main.js` |
| P2 | 雷达图点击跳转 | 无跨模块导航 | `eval-charts.js` |
| P3 | p95 < 500ms 基准测试 | 无性能测量数据 | `tests/bench_eval_overhead.py` |

### 未验证 ⚠️

- **30秒信任法则盲测**: 信息层级已按计划实现，但无真人验证
- **浏览器交互验证**: 171 测试覆盖数据流和 API，但未在浏览器中手动验证

---

## 五、接下来的打算

### 明天 (6/11)

1. **P1 交互优化** — 趋势线 annotation 标记点 + 建议滑出面板
2. **P2 交互补充** — Agent 三指标卡片、告警滚动、雷达图跳转
3. **战略讨论**:
   - 知识库评估: Phase 1/2 建好后，是否对知识库中过往经验/错误/知识做过评估？
   - 错误预防机制: 如何保证 v3→v4 覆写这类错误不再发生？
   - 评估系统自指: 评估系统建设中的问题证明了它的必要性——如何继续推进？

### Phase 4 (后续)

- LLM Judge: `/cross-validate/execute` 从 501 → 实现
- `meta_evaluator.py`: 元评估器，评估评估系统自身
- 动态 Golden Dataset: 可演进的评估基准
- 旧 `review_*` 端点弃用，合并到 eval 系统

---

## 六、关键决策记录

1. **鉴权重用 SECRET_KEY 而非新增 ADMIN_SECRET** — 项目原则"复用现有机制"（2026-06-10）
2. **JS 使用命名空间模式而非 ES modules** — 与现有 15 个 JS 文件一致（2026-06-10）
3. **eval.html 使用 escapeHtml + innerHTML 而非 `<template>` + cloneNode** — 两种模式计划均批准，当前方式安全且实现更简单（2026-06-10）
4. **后端 JSON 文件而非 SQLite** — Phase 3 数据量 < 1000 行，SQLite 迁移预留 `_query_traces()` 抽象层（2026-06-10）
5. **LLM Judge 留到 Phase 4** — 避免付费 API 在未充分验证基础设施前消耗 token（2026-06-10）
6. **影子模式作为默认** — Phase 3 开发全期 `EVAL_SHADOW_MODE=true`，不写生产数据（2026-06-10）

---

## 七、数字总结

| 指标 | 数值 |
|------|------|
| 新建文件 | 7 个 (4 JS + 1 HTML + 1 test + 1 plan) |
| 修改文件 | 7 个 (routes/api_eval, pages, server, base.html, eval_engine, eval_store, config) |
| API 端点 | 9 个 (7 GET + 2 POST + 1 stub 501) |
| 测试数 | 171 (32 API + 其余 engine/core) |
| 合并覆盖率 | 89% |
| ScoreConfig | 10 个 (2 宪法 + 8 标准) |
| JS 模块 | 4 个 (~420 行总计，无文件超 300 行警戒线) |
| Commit 数 (Phase 3) | 7 个 (Phase 1 + P1/P2 + Phase 2 + API tests + 4 control fixes) |
| 遇到的问题 | 6 个 (3 测试 + 1 sys.modules + 1 文档覆写 + 1 鉴权遗漏) |
| 已知缺口 | 6 个 (2 P1 + 3 P2 + 1 P3) |
