# Crescent API 模块

## 端点总览

| 模块 | 文件 | 职责 |
|------|------|------|
| pages | `routes/pages.py` | 页面路由 (Jinja2 模板 + SPA fallback) |
| workbench | `routes/api_workbench.py` | SSE pipeline (profile→direction→gap→path→action) |
| ai | `routes/api_ai.py` | DeepSeek API 代理 |
| agent | `routes/api_agent.py` | Agent 模式 (ReAct loop) |
| eval | `routes/api_eval.py` | 评估系统 CRUD + 影子模式 |
| resume | `routes/api_resume.py` | 简历解析/审阅 |
| interview | `routes/api_interview.py` | 模拟面试 |
| papers | `routes/api_papers.py` | 论文管理 |
| knowledge | `routes/api_knowledge.py` | 知识库导入/检索 |
| exercises | `routes/api_exercises.py` | 练习题生成/批改 |
| code | `routes/api_code.py` | 代码执行沙箱 |
| config | `routes/api_config.py` | 系统配置 |
| impressions | `routes/api_impressions.py` | 用户行为记录 |
| progress | `routes/api_progress.py` | 学习进度追踪 |
| review | `routes/api_review.py` | 复习调度 |
| source_trace | `routes/api_source_trace.py` | 知识溯源 |
| sync | `routes/api_sync.py` | 数据同步 |
| tokens | `routes/api_tokens.py` | Token 统计 |
| import | `routes/api_import.py` | 数据导入 |

## 鉴权规则
- 写操作 (POST/PUT/DELETE): `_check_admin()` 守卫
- 读操作 (GET): 一般不鉴权，需鉴权在注释说明
- `/api/eval/*` 额外要求: `_verify_admin_token()` 数据层鉴权

## 关键端点

### Workbench
- `POST /api/workbench/start` — 启动 session，返回 SSE stream
- `POST /api/workbench/respond` — 发送用户消息
- `GET /api/workbench/status/{session_id}` — 查询 session 状态

### Eval
- `GET /api/eval/snapshots` — 列出快照
- `POST /api/eval/snapshots` — 创建快照 (admin)
- `DELETE /api/eval/snapshots/{id}` — 删除快照 (admin)
