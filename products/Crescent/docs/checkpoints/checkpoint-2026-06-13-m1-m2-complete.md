# Checkpoint — 2026-06-13 M1+M2 执行完成

> compact 前存档。下次恢复后**不要自动执行**，等待用户指令。

## 本次做了什么

按照 v5 执行计划，完成 **M1 (事件管道泛化)** 和 **M2 (追溯链连通)** 两个里程碑的全部任务。

## 执行摘要

| M | 任务数 | Commits | 测试增量 | 核心交付 |
|---|--------|---------|----------|----------|
| M1 | 6 | 6 | 175→180 (+5) | emit_event, beacon+频率限制, L2 Timer stub, perf_check.sh |
| M2 | 4 | 4 | 180→192 (+7) | chain_hash, L2响应率三态, 决策面加载器, trace-chain API |

**当前测试: 192 passed, 0 failed**

## Git 提交历史 (本次 session)

```
abc4d07 feat(M2): trace-chain API — GET /api/eval/trace-chain/<suggestion_id>
625cc6f feat(M2): _load_decision_surfaces() — centralized YAML loader with failure isolation
8980a50 feat(M2): L2 self-check — heartbeat, alert response rate, L1 degradation
e092313 feat(M2): chain_hash integrity — _compute_chain_hash + _verify_chain_hash
ba3e8a3 chore(M1): integration verification — all 180 tests pass, core paths untouched, alert_id contract fixed
7224263 feat(M1): performance benchmark script for CI acceptance gates
67397c5 feat(M1): L2 independent timer with stub — graceful degrade until M2
667299c feat(M1): /api/eval/beacon endpoint + frontend sendBeacon
3d69f07 feat(M1): emit_event() generic event emitter + event_types whitelist
463c524 feat(M1): add scan resource limit configs for M5 prospective water sources
```

## M1 详细交付

| Task | 文件 | 内容 |
|------|------|------|
| 1.1 | `config.py` | SCAN_MAX_FILE_BYTES, SCAN_MAX_FILES, SCAN_TIMEOUT_SECONDS |
| 1.2 | `trace_logger.py` | emit_event() + register_event_type() + 8种预注册事件 + 白名单安全机制 |
| 1.3 | `routes/api_eval.py`, `eval-api.js`, `eval.html` | /api/eval/beacon + 滑动窗口频率限制(10次/60s/IP) + sendBeacon + 隐私披露 |
| 1.4 | `server.py` | L2 threading.Timer(2h) + ImportError stub → M2 自动激活 |
| 1.5 | `scripts/perf_check.sh` | 性能基准脚本 |
| 1.6 | `eval_engine.py` | alert_id 契约修复 — _build_alerts() 为每条告警生成 alert_id |

## M2 详细交付

| Task | 文件 | 内容 |
|------|------|------|
| 2.1 | `eval_store.py` | _compute_chain_hash() + _verify_chain_hash() + add_suggestion 携带 chain_hash |
| 2.2 | `meta_evaluator.py` | run_l2_self_check(): L1心跳检查 + 告警响应率三态(responded/auto_recovered/unresponded) + L1指标退化 |
| 2.2b | `eval_store.py` | _load_decision_surfaces(): 集中化YAML加载器, 单文件失败不影响其他, 内存缓存 |
| 2.3 | `routes/api_eval.py` | GET /api/eval/trace-chain/<id>: chain(full/partial/broken) + evidence_brief + chain_hash_verified |

## 安全基线状态

- [x] beacon 频率限制 (10次/60s/IP, 429)
- [x] beacon 字段白名单 (event_type/panel_id/timestamp)
- [x] emit_event 白名单 (未注册类型拒绝+安全告警)
- [x] chain_hash SHA256 完整性校验
- [x] L2 独立线程 (2h间隔, 连续两次失败stderr告警)
- [x] alert_id 契约 (M2追溯链前提)
- [x] audit.jsonl 鉴权失败记录 (安全回归测试通过)
- [x] 3条核心埋点路径未改动

## 执行中修复的问题

1. **alert_id 契约断裂** (M1 Task 1.6): `_build_alerts()` 未生成 alert_id → M2 L2响应率无法追溯。已在 M1 验收时修复。
2. **beacon 测试隔离**: 速率限制状态跨测试残留 → 测试中显式清空 `_beacon_rate_state`
3. **monkeypatch 路径**: 测试需 patch `routes.api_eval.time.time` 而非 `time.time`
4. **scores.json 结构**: 实际为 `{"scores": [...], "updated_at": ...}` 而非直接列表 → alert_id 检查脚本已适配

## 下一步 (M3: Dashboard 可探索性升级)

**等待用户指令后执行。** M3 包含 3 个任务：

| Task | 内容 |
|------|------|
| 3.1 | 评分卡三层折叠 — L2=子指标+建议(为什么), L3=参照系+计算说明(意味着什么) |
| 3.2 | 创新信号区+概念提示 — 可配置位置(tab/overview) + 可配置密度(sparse/dense) |
| 3.3 | eval_coverage 检测器 — 三态空状态(cold_start/partial/load_failed) |

M3 验收包含用户路径测试: "安全评分为什么从0.85降到0.72？" 30秒内4步追问链路。

## 关键文件清单 (本次修改)

| 文件 | M1 | M2 | 说明 |
|------|:--:|:--:|------|
| `config.py` | ● | | 扫描资源限制 |
| `services/eval/trace_logger.py` | ● | | emit_event + 白名单 |
| `routes/api_eval.py` | ● | ● | beacon + trace-chain |
| `server.py` | ● | | L2 Timer |
| `services/eval/eval_engine.py` | ● | | alert_id 修复 |
| `services/eval/eval_store.py` | | ● | chain_hash + 决策面加载器 |
| `services/eval/meta_evaluator.py` | | ● | run_l2_self_check |
| `static/js/modules/eval-api.js` | ● | | sendBeacon |
| `templates/pages/eval.html` | ● | | 隐私披露 |
| `scripts/perf_check.sh` | ● | | 性能基准 |
| `tests/test_eval_core.py` | ● | ● | emit_event + chain_hash + 决策面 测试 |
| `tests/test_eval_api.py` | ● | ● | beacon + trace-chain 测试 |

## 会话恢复协议 🔴

**恢复后默认姿态是「等待」。** 不要自动开始 M3。确认用户意图后再执行。
