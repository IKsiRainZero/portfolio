# Checkpoint — 2026-06-06

## 会话成果

### 仓库重构
- `main` 分支已创建并推送，仅保留核心项目 (portfolio-app/site, cv-lab, 知识库)
- 侧分支: `quant-trading`, `fourth-wall`, `tech-notes`
- 141 个过期文件已删除 (22,865 行)

### 超级规划 (Phase 1 Spec)
- 完整设计文档: `docs/superpowers/specs/2026-06-06-ai-companion-phase1-design.md`
- 双核架构: 主动学习教练 + 信息免疫系统
- 三阶段路线图: A(本地桌面 0-18月) → B(混合云 18-36月) → C(家庭节点 36-60月)
- 差异化三角: 信息免疫 + 主动智能 + 本地隐私

### 信息免疫系统设计
- 核心: 过程透明 + 工具可信度透明，非只给结论
- L1 来源追溯: 用户主动触发，实时展示搜索路径+工具+来源，所有链接可点击验证
- 不确定原则已写入 CLAUDE.md: 不知道就直说，不脑补

### Karpathy 编码原则
- 完整中文版已写入 CLAUDE.md + memory
- 四原则: 编码前思考 / 简洁优先 / 精准修改 / 目标驱动执行

### 阶段 0 完成
- [x] MCQ 手动前进 (已完成)
- [x] 错题追问弹窗 (已完成，前后端全通)
- [x] 闪卡手动前进 (已修复 — flashDetail 容器缺失)
- [x] markitdown 接入 (pip install markitdown[pdf]，PDF→MD 验证通过: 86,989字符)

### 已下载工具 (portfolio/ 下)
- `markitdown-main/` — MIT, PDF→MD 已验证
- `Scrapling-main/` — BSD-3, 自适应爬虫
- `token-monitor-main/` — MIT, token 消耗监控
- `codegraph-main/` — npm 包, 代码属性图 + MCP Server

### 权限系统清理 (2026-06-06 续)
- 项目 settings 从 191 条精简到 ~70 条，按用途分组
- 全局 settings Bash 语法修复: `git:*` → `git *`（冒号语法从未生效）
- chrome-devtools-mcp 已配置，重启后可用
- deny 列表: `rm -rf /`, `format`, `shutdown`, `git push --force main/master`
- 问题根因: 全局冒号语法无效 + 项目级缺 Read/Write/Edit/Glob/Grep

### 阶段 1 进度
- [x] **Agent 结构化日志** — `services/agent_logger.py` 新建，JSONL 按天分文件
  - 每条记录: ts/session_id/user_message/reply/steps/duration_ms/model
  - `agent_chat()` 和 `agent_chat_stream()` 均已接入
- [x] **关键路径降级** — RAG 向量不可用→纯 BM25；LLM 超时→提示切换模型
  - `rag_service.py`: `search()` embedding 失败时走 `_search_bm25_only()`
  - `local_llm.py`: 超时/连接失败给出具体切换建议
- [x] **RAG 评估可重复化** — `scripts/eval_rag.py` 重构为可配置评估管道
  - 4 种预设配置: hybrid / hybrid+reranker / vector-only / bm25-only
  - `--config compare` 一键全对比 + 汇总表
  - `--test-set` 支持自定义测试集，结果自动版本化
- [x] **Harness 校验链可插拔** — `services/harness.py` 新建
  - 3 个校验器: EmptyReply / ToolError / ToolCallLoop
  - 新增规则只需继承 Validator 加入 VALIDATORS 列表
  - `agent_chat()` 和 `agent_chat_stream()` 均返回 `harness` 字段
- [x] **token-monitor 接入** — `scripts/monitor_tokens.sh` 启动脚本
  - 三种模式: widget(桌面小部件) / agent(后台守护) / once(单次采集)
  - 自动读取 `~/.claude/transcripts/`，无需额外数据管道

### 阶段 1 完成  ✅
全部五项任务已完成。阶段 2 (信息健康原型) 待用户确认后启动。

## 当前状态
- 分支: `main`
- 新增文件: `services/agent_logger.py`, `services/harness.py`, `scripts/monitor_tokens.sh`
- 修改文件: `services/agent_service.py`, `services/rag_service.py`, `services/local_llm.py`, `scripts/eval_rag.py`, `.claude/settings.local.json`, `~/.claude/settings.json`
- 服务端路由: 无变更
- 服务器: 未运行

## 待讨论
- portfolio-app / portfolio-site / cv-lab 集成策略 (暂不合并，接口先行)
- cv-lab 课程分支 vs 自有 lab 方向
