# Compact 恢复检查点 — 2026-06-03 (晚间更新)

## 当前进度

```
Phase 0: ✅ 环境搭建
Phase 1: ✅ 向量知识库 (ChromaDB + bge-m3, 3724 docs)
Phase 2: ✅ RAG 管线 (动态阈值 + 英文回退)
Phase 3: ✅ Agent 核心 (LangGraph ReAct + MemorySaver)
Phase 4: ✅ Agent↔前端集成 (AI chat迁移, thinking展示, 知识检索, 题目保存)
Phase 5: ✅ 听说读写用 (费曼教练, 简答题, 错题本, 场景迁移, 深度追问, 寓言故事, 阅读进度)
Phase 6: ✅ 模拟面试 Agent化 (原计划Phase 6, Phase 5中提前完成)
Phase 7: ✅ 仪表盘+自反馈闭环 (streak天数, 继续上次, 最近活动, dashboard API)
Phase 8: ✅ 设置+打磨+离线降级 (settings模块化, 数据导入导出, offline banner, 响应式CSS)
```

## Phase 5-8 新增文件清单

```
static/js/modules/
  trainer-mcq.js      — MCQ + 自适应难度 + 错题本(localStorage)
  trainer-code.js      — 编程题 (从trainer.js拆分)
  trainer-flash.js     — 闪卡 (从trainer.js拆分)
  trainer-review.js    — 复习清单 + 错题本展示 + SRS计划
  trainer-short.js     — 简答题 + Agent评分
  dashboard.js         — 仪表盘 (从home.html内联JS提取)
  feynman-coach.js     — 费曼教练 (新建)
  mock-interview.js    — 模拟面试 Agent化 (从内联JS重构)
  knowledge-browse.js  — 知识库浏览器 + 阅读进度 + 寓言故事 + 相关概念
  settings.js          — 设置页面 (从内联JS提取)

templates/pages/
  feynman.html         — 费曼教练页面 (新建)
  mock_interview.html  — 模拟面试 (重构为模块化)

services/
  agent_service.py     — 9 tools (新增 feynman_check)
  progress_tracker.py  — 新增 streak/compute, get_dashboard(), last_active

routes/
  pages.py             — 新增 /feynman 路由
  api_progress.py      — 新增 GET /api/progress/dashboard

static/css/
  global.css           — 新增 quick-actions CSS, 640px响应式断点
  print.css            — 排除 offlineBanner
  components.css       — 未变

templates/
  base.html            — 新增 offlineBanner, AI quick-actions栏, 费曼教练nav, favicon fix
```

## JS 模块总数: 11

```
app.js                     — 核心: serverStatus, AI面板, sendAIMsg, quickAction, escapeHtml, UI helpers
modules/trainer.js         — 训练器核心: state, data load, topic filter, import modal, tabs
modules/trainer-mcq.js     — MCQ: render, answer, streak, error notebook
modules/trainer-code.js    — 编程: render, runCode
modules/trainer-flash.js   — 闪卡: render, flip, AI compare, rate
modules/trainer-review.js  — 复习: SRS plan, progress, weak areas, error notebook
modules/trainer-short.js   — 简答: render, submit, Agent评分
modules/knowledge-browse.js — 知识库: domain load, render, Agent search, fable, reading progress, related
modules/mock-interview.js  — 面试: setup→QA loop→report, Agent-driven
modules/feynman-coach.js   — 费曼: concept→explain→check→revise loop
modules/dashboard.js       — 仪表盘: SRS stats, dashboard data, weak areas, study plan, continue last, recent
modules/settings.js        — 设置: API key, export/import, cache clear, system status
modules/resume-view.js     — 简历 (Phase 4已有)
```

## API 蓝图: 10 个

```
pages_bp         — 7 页面路由 (home, trainer, knowledge, resume, interview, feynman, settings)
config_bp        — /api/config (GET/POST)
code_bp          — /api/code/run
knowledge_bp     — /api/knowledge/sets, /<set_id>, /search
progress_bp      — /api/progress/record, /summary, /dashboard; /api/srs/*
ai_bp            — 旧AI端点 (tutor, interview/start, interview/next, resume-review, import-knowledge, temp CRUD, rag-query, internalize)
exercises_bp     — /api/exercises/<type>, /temp, /temp/classify, /temp/clear
resume_bp        — /api/resume/data
agent_bp         — /api/agent/chat, /agent/reset, /exercises/save-generated
```

## Agent Tools: 9 个

```
1. search_knowledge     — RAG搜索知识库
2. generate_question    — 生成练习题(mcq/coding/flashcards)
3. analyze_progress     — 查询学习进度统计
4. diagnose_weakness    — 诊断薄弱点
5. save_question_to_trainer — 保存题目到临时题库
6. evaluate_answer      — 评估简答题回答质量
7. deep_question        — 生成场景迁移/举一反三题
8. feynman_check        — 费曼检查（简单性/完整性/清晰度/具体性）
9. create_study_plan    — 生成个性化学习计划
```

## 工程问题 (P0 — compact后优先修)

1. **config.py:34-35** — 硬编码 D:/models/BAAI/ 路径，不可移植
2. **temp_exercises.json 读写逻辑** — 在 api_agent.py, api_ai.py, agent_service.py 三处重复
3. **agent_service.py:290** — _compute_weak_areas 与 progress_tracker.py 重复实现
4. **api_ai.py (485行)** — 9个路由7个功能混在一个文件，应拆分
5. **Tool prompts 硬编码** — evaluate_answer/deep_question/feynman_check/create_study_plan 的 prompt 用 f-string 内联，应提取到 prompts/*.txt

## 交付物需求 (对标课程要求)

通用7件套: 源码✅ | README❌ | 智能体设计文档⚠️ | 数据集说明⚠️ | PPT❌ | 演示视频❌ | 调试报告⚠️
量化指标: ❌ 关键缺口 — 需30条QA评测集 + Hit Rate/MRR/Recall + Agent vs 直接LLM对比

## 快速启动

```bash
cd portfolio-app
python server.py          # http://localhost:5000
bash check-js.sh          # JS语法检查
```

## Git 状态

当前所有 Phase 5-8 变更未提交。compact后第一件事应commit。
