# Console 关键决策

## ADR-001: 独立项目
- **决策**: products/console/ 独立项目
- **理由**: 不耦合已有项目，独立演进

## ADR-002: FastAPI + React
- **决策**: 双进程架构，后端 API + 前端 SPA
- **理由**: 匹配现有技术栈，完整文件系统权限

## ADR-003: 纯文件驱动
- **决策**: 无数据库，JSONL trace + 文件解析
- **理由**: STATUS.md 和 .context/ 已是 source of truth

## ADR-004: tracer 横切层
- **决策**: 每个有副作用操作自动打点 JSONL
- **理由**: 可观测是一等公民，人机皆可读

## ADR-005: 写操作二次确认
- **决策**: create_project / commit_changes 需用户确认
- **理由**: 安全底线
