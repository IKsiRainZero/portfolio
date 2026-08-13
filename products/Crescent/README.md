# Portfolio App — 求职备战工作台

基于 Flask + 自定义 ReAct Agent 的个人学习系统。SSE 流式输出、向量+BM25+Reranker 混合检索、AI 课程体系、费曼教练、模拟面试。

> v3.0 | 2026-06-04

## 环境要求

- Python 3.10+
- 5GB+ 磁盘空间（embedding 模型 ~2GB，reranker ~1.3GB）
- DeepSeek API Key（[获取地址](https://platform.deepseek.com)）
- （可选）Ollama — 本地小模型做历史压缩，省 API token

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 首次初始化（下载模型 + 构建向量库，约 3-5 分钟）
python setup_models.py

# 4. 启动
python server.py
# → http://localhost:5000
```

**可选：** Ollama 本地模型压缩 Agent 历史（省 token）
```bash
ollama pull qwen2.5:0.5b
# Agent 会自动检测并启用历史压缩
```

## 项目结构

```
Crescent/
├── server.py              # Flask 入口
├── config.py              # 全局配置
├── requirements.txt       # Python 依赖
├── prompts/               # AI 提示词模板（.txt，可直接编辑）
│   ├── agent_system.txt   # Agent 系统提示词
│   ├── tutor.txt          # 通用答疑教练
│   ├── mock_interview.txt # 模拟面试官
│   ├── tool_*.txt         # Agent Tool 提示词 (4个)
│   └── ...
├── services/              # 业务逻辑层
│   ├── agent_service.py   # 自定义 ReAct Agent (9 Tools, 历史压缩, max_steps=6)
│   ├── rag_service.py     # RAG 混合检索 (向量+BM25+Reranker)
│   ├── llm_service.py     # DeepSeek + BGE Embedding 封装
│   ├── local_llm.py       # Ollama 本地小模型 (历史压缩)
│   ├── deepseek_client.py # DeepSeek API 客户端
│   ├── knowledge_sync.py  # JSON 知识库 → ChromaDB 增量同步
│   ├── code_runner.py     # 安全 Python 沙箱
│   ├── knowledge_loader.py# 知识库加载/搜索
│   ├── progress_tracker.py# 学习进度追踪 + 仪表盘
│   ├── exercise_store.py  # 临时题库存储
│   └── insight_store.py   # 方法论卡片存储
├── routes/                # Flask 路由层 (12 Blueprints)
│   ├── pages.py           # 页面路由 (含 /changelog)
│   ├── api_agent.py       # Agent SSE 流式 + 非流式 API
│   ├── api_sync.py        # 知识库同步 API
│   └── ...
├── data/                  # 结构化数据
│   ├── chroma_db/         # Chroma 向量库 (~4000 chunks)
│   ├── changelog.json     # 版本更新日志
│   ├── exercises/         # 正式题库 (mcq/coding/flashcards)
│   ├── knowledge/         # 知识库 JSON (含 AI 课程体系)
│   ├── eval/              # RAG 评测集
│   ├── resume/            # 简历结构化数据
│   └── user_data/         # 用户进度 (.gitignore)
├── scripts/               # 工具脚本
│   ├── eval_rag.py        # RAG 检索评测 (Hit Rate/MRR)
│   ├── compare_chunks.py  # Chunk Size 对比实验
│   └── setup_models.py    # 首次初始化
├── static/
│   ├── css/               # 样式 (global.css, components.css, print.css)
│   └── js/
│       ├── app.js         # 核心框架 (导航/AI面板/快捷操作)
│       └── modules/       # 11 个功能模块
└── templates/
    ├── base.html          # 共享布局 (侧栏+AI面板+离线横幅)
    └── pages/             # 7 个页面模板
```

## 功能页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 仪表盘 | `/` | 学习统计、连续天数、薄弱点、快捷入口 |
| 训练器 | `/trainer` | MCQ/编程/闪卡/简答/错题本/复习清单 |
| 知识库 | `/knowledge` | 领域浏览、搜索、寓言故事、阅读进度 |
| 费曼教练 | `/feynman` | 概念解释 → AI 评估 → 改进循环 |
| 模拟面试 | `/interview` | 领域选择 → Q&A 循环 → 综合反馈报告 |
| 简历 | `/resume` | 结构化简历 + 打印 + AI 审阅 |
| 设置 | `/settings` | API Key、数据导出/导入、缓存管理 |

## AI 功能使用

1. **页面右下角 AI 面板** — 在任何页面点击 "AI 助手" 唤起
2. **快捷操作按钮** — 举一反三、深度追问、出题练习、学习诊断
3. **Agent 思考过程** — AI 回复下方 "查看思考过程" 可展开 Tool 调用详情
4. **保存到题库** — Agent 生成的题目可一键存入临时题库

## 离线使用

非 AI 功能在服务器离线时仍可用：
- 训练器从 localStorage 加载缓存题目
- 错题本、阅读进度存储在本地
- 服务器恢复后自动重连

## 依赖说明

| 依赖 | 用途 |
|------|------|
| flask | Web 框架 |
| langchain, langchain-deepseek, langchain-huggingface | LLM + Embedding 接入 |
| chromadb | 向量数据库 |
| sentence-transformers | Embedding (bge-m3) + Reranker (bge-reranker-large) |
| jieba, rank-bm25 | BM25 关键词检索 |
| pymupdf | PDF 文档解析 |
| pandas | 数据处理 |

## 常见问题

**Q: 启动后页面空白？**
检查浏览器控制台（F12）。确保 `static/` 目录完整。

**Q: AI 面板显示 "Key未设"？**
复制 `.env.example` 为 `.env` 并填写 `DEEPSEEK_API_KEY`，或在设置页面输入。

**Q: Embedding 模型加载失败？**
运行 `python setup_models.py` 自动下载，或手动下载到 `models/BAAI/bge-m3/`。也可设置 `MODELS_DIR` 指向已有模型目录。

**Q: ChromaDB 报错？**
删除 `data/chroma_db/`，运行 `python setup_models.py --no-models` 重建。

**Q: 如何备份学习数据？**
设置页面 → 导出数据，下载完整 JSON 备份文件。
