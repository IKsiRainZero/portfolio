# Portfolio

个人多项目工作空间。项目按状态分三级：products/（活跃）、experiments/（实验）、archive/（归档）。

## 项目

| 项目 | 是什么 | 技术栈 | 状态 |
|---|---|---|---|
| console | 多 Agent 可观测性控制台：追踪 Claude Code / Codex / DSH 会话与 git 痕迹 | FastAPI · React · SSE | 活跃（V1） |
| Crescent | AI 驱动的个人学习系统：知识库 RAG、SRS 复习、面试训练、自指评估 | FastAPI · React · DeepSeek | Phase 3（235 tests） |
| singularity | 黑洞屏保 | Rust · DirectX11 · HLSL | Phase 2 |
| may-i-help-u | 可复用问题解决器官系统 | Python (pip) | v0.1.0 |
| thinking-space | 思维卡片无限画布 | FastAPI · React · Canvas | V2 |
| Where_is_it | 前瞻记忆辅助小程序（Ebbinghaus 间隔重复 + 地理围栏） | 微信小程序 | MVP |

## 目录结构

```
products/      活跃项目
experiments/   实验项目
archive/       归档项目
.context/      AI 协作上下文：constitution（协作规则）、reference、knowledge
```

## AI 原生工作流

- constitution：与 AI 协作的规则与边界（.context/constitution/）
- 会话复盘协议：每个 session 结束写复盘，不更新 = 丢失
- 双 Agent 协作：Claude Code 与 Codex 各管一摊，hooks 互通
- 实验隔离：git worktree

## 许可证

MIT
