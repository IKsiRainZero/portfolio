# Console 项目架构

## 定位
Portfolio 工作空间管理控制台。可视化看进展 + AI Agent 操作 + 一键创建项目。
独立项目 `products/console/`。

## 目录结构
products/console/
├── backend/
│   ├── app/
│   │   ├── main.py           ← FastAPI 入口 (port 8000)
│   │   ├── config.py          ← 配置
│   │   ├── readers/           ← 只读聚合
│   │   ├── executors/         ← 写操作
│   │   ├── ai/                ← LLM 代理 (chat + tools + context)
│   │   ├── tracer/            ← 横切可观测层
│   │   └── routes/            ← API 路由
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/               ← API client
│   │   ├── components/        ← Dashboard, ChatPanel, Observability, Layout
│   │   ├── hooks/
│   │   └── types/
│   └── tests/
└── .context/
    └── constitution/

## 当前状态
V1 实施中。详见 .context/records/superpowers/plans/2026-07-21-console-implementation.md
