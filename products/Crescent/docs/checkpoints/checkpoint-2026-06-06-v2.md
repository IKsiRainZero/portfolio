# Checkpoint — 2026-06-06 (下半场)

## 会话成果

### 权限系统清理
- 全局 settings 22 个 Bash 冒号语法修复: `git:*` → `git *`（从未生效，所有 Bash 都在弹窗）
- 项目 settings 191 条 → ~75 条，补上 Read/Edit/Write/Glob/Grep
- deny 列表: `rm -rf /`, `format`, `shutdown`, `git push --force main/master`
- chrome-devtools-mcp 已配置，重启后可用

### 阶段 1：稳定化 — 全部完成 ✅

| # | 任务 | 文件 | 关键 |
|---|------|------|------|
| 1 | Agent 结构化日志 | `services/agent_logger.py` 新建 | JSONL 按天分文件，每次调用记录完整 chain |
| 2 | 关键路径降级 | `rag_service.py`, `local_llm.py` | embedding 失败→纯 BM25；LLM 超时→切换建议 |
| 3 | RAG 评估可重复化 | `scripts/eval_rag.py` 重写 | 4 种预设 + `--config compare` + 自动版本化 |
| 4 | Harness 校验链 | `services/harness.py` 新建 | 3 个校验器，插入即用；返回 `harness` 字段 |
| 5 | token-monitor 接入 | `scripts/monitor_tokens.sh` 新建 | widget/agent/once 三模式 |

### 验证结果
- ✅ Flask 启动: HTTP 200，所有模块 import 正常
- ✅ Agent API: harness.passed=True, 3 validators 生效
- ✅ Agent 日志: 5 条 JSONL 记录，`get_log_stats()` 可查询
- ✅ eval_rag pipeline: 4 配置均可运行，结果自动版本化
- 🟡 **发现并修复**: `routes/api_agent.py` 漏传 `harness` 字段（验证时发现）

### 交付文档同步
- `docs/交付/agent-design-doc.md` — v1.0 → v1.1，加 4 项新能力
- `docs/交付/debug-report.md` — v3.1 → v3.2，加 8 个问题 + 4 条详情
- `docs/交付/optimization-roadmap.md` — v3.1 收尾，v3.2 新增 7 项完成记录

### 文档结构确认
- `docs/交付/` — agent-design-doc / debug-report / optimization-roadmap / dataset-doc
- `docs/checkpoints/` — 压缩前检查点
- 其他 docs 文件 — 用户手动管理的临时参考，不管

## 当前状态
- 分支: `main`
- 新增: `agent_logger.py`, `harness.py`, `monitor_tokens.sh` (eval_rag.py 重写)
- 修改: `agent_service.py`, `rag_service.py`, `local_llm.py`, `api_agent.py`, settings ×2
- 未提交: 全部改动
- 服务器: 运行中 (port 5000, qwen3:8b)

## 下一步
按 Phase 1 Spec，阶段 2（信息健康原型）：
1. L1 来源追溯核心链路 — URL/文本输入 → Scrapling 抓取 → 来源链分析
2. 来源追溯结果展示 UI — 来源链 + 差异标注 + 可信度摘要卡片
3. 主动提醒框架 — 定时轻提醒（基于时间/频率触发，不监控内容）
