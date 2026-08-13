# 工作空间架构

## 目录结构
```
portfolio/                       ← Git 仓库根
├── products/                    ← 活跃开发
│   ├── Crescent/                ← FastAPI + React 作品集
│   ├── console/                 ← FastAPI + React 管理控制台 [进行中: V1]
│   ├── cv-lab/                  ← CV 教学实验室
│   └── Where_is_it/              ← 前瞻记忆辅助系统
├── earn_money/                  ← 接单操作系统（meta-project）
├── experiments/                 ← 实验/课程项目
├── archive/                     ← 已完成/不再维护
├── .context/                    ← 工作空间级共享知识
│   ├── constitution/            ← 必读：技术栈、架构、规范、决策、坑点、原则
│   ├── reference/               ← 按需：技能分类、模块清单、技能参考
│   ├── knowledge/               ← 按需：灵感、论文、笔记、分析
│   ├── sessions/                ← 读写：跨项目会话记录
│   ├── records/                 ← 按需：checkpoints、phase-plans、防御答辩
│   └── templates/               ← 会话模板
├── 知识库/                      ← 待迁移到 .context/（迁移完成后删除）
├── docs/                        ← 待迁移到 .context/records/（迁移完成后删除）
├── _vendor/  scripts/  data/    ← 共享资源
└── CLAUDE.md                    ← AI 入口
```

## 每项目内部结构（规范）
```
<project>/.context/
├── constitution/                ← 项目级必读（技术栈、架构、决策、坑点）
├── modules/                     ← 模块文档（API、数据流、组件）
├── sessions/                    ← 项目专属会话记录
└── reference/                   ← 项目专属参考（论文、设计参考）
```

## 知识加载流程
1. 会话启动 → CLAUDE.md 自动注入
2. CLAUDE.md 导航 → 读 `.context/constitution/` 全部文件
3. 涉及具体项目 → 读 `products/<name>/.context/constitution/`
4. 需要深入模块 → 读 `products/<name>/.context/modules/`
5. 检索共享知识 → `.context/reference/` + `.context/knowledge/`

## 会话结束流程
1. 新发现/新决策 → 更新对应 constitution（gotchas / decisions）
2. 新资源 → 归类到对应 .context/ 子目录
3. 复盘记录 → sessions/archive/
4. 不更新 = 丢失
