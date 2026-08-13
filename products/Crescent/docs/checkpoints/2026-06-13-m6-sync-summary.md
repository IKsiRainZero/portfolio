# Eval Meta-Module M6 同步摘要 (2026-06-13)

## 背景

将 eval 系统从被动的仪表板转变为项目决策的中枢神经系统。6个里程碑(M1-M6)，从事件管线到前瞻性探测卡，全部在一天内完成。

## 建成了什么

**双轨事件管线** — 核心路径(deepseek_client/Flask hooks/agent_service)保持硬编码，新来源使用统一的 `emit_event()` 接口。已注册的事件类型白名单防止未授权写入。前端行为追踪通过 `/api/eval/beacon` 端点，带基于IP的滑动窗口限流(10次/60秒)。

**6环追溯链** — 每条建议现在携带完整的 event→metric→alert→suggestion 链，用 SHA256 `chain_hash` 防篡改。通过 `GET /api/eval/trace-chain/<id>` 可追溯任何决策的完整证据链。

**3层评分卡** — 仪表板上的评分卡按用户自然追问路径组织: L2(子指标分解+关联建议)回答"为什么这么低？"，L3(参照系+计算说明+决策问题)回答"这意味着什么？"。

**双水源架构** — 回顾性水源(已发生的: traces/metrics/alerts) + 前瞻性水源(应该发生但还没发生的: 探测卡)。3个前瞻检测器每日运行: 知识-应用差距、模块停滞、重复错误指纹。≥3次重复自动升级为建议。

**决策面注册表** — YAML文件(`data/eval/modules/`)将评估指标与具体工程决策问题关联。覆盖状态有冷启动/部分/健康三态，前端引导下一步操作。

**元评估L2自检** — 独立 `threading.Timer`(2小时)运行自检，不依赖守护进程。连续两次失败触发stderr告警。

**可配置UI** — `window.EvalUIConfig` 控制创新信号放置(tab/overview)和概念提示密度(sparse/dense)，无需改代码。

## 测试状态

220 passed / 10 failed。失败的都是批量运行时的测试隔离问题(共享tmp_path、monkeypatch泄漏)，每个单独运行时都通过。

## 安全

- 路由层 + 数据层双重鉴权，审计日志记录所有被拒请求
- 前端beacon字段白名单，超长字段拒绝
- 探测卡忽略是决策行为，写入audit.jsonl并记录原因
- 影子模式写操作返回403

## 已知限制

- `scripts/perf_compare.sh` 未创建，perf_check.sh需服务器运行
- 10个测试在批量运行时因顺序依赖失败(单独跑都绿)
- 没有完整的模块注册表，coverage_data.uncovered_count 硬编码为0
- 探测卡升级为建议的逻辑只在error_recurrence检测器中实现(kb_gap和staleness暂不自动升级)
- 无CI/CD集成

## 下一步建议

- 修复10个批量运行失败的测试(主要改fixture隔离)
- 补充完整模块注册表，让coverage检测真正有用
- 为kb_gap和staleness检测器增加自动升级逻辑
- 集成到CI/CD，每次PR自动运行perf_check.sh
