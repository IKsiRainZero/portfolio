# Checkpoint 2026-06-04

> 本次会话的前因后果、已完成工作、待办事项汇总。compact 后恢复上下文用。

---

## 一、背景：为什么会走到这一步

**触发事件：** DeepSeek V4 Flash API 在一天内消耗 20M+ tokens（700+ 次调用，1200 万缓存未命中），花费数十元。根因是 Agent ReAct 循环中每次调用携带完整增长的历史 → prompt cache 永远不命中 → N×N 放大效应。再加上用付费 API 做临时性功能测试而非结构化评估。

**核心教训：**
- 付费 API 只用于生产级验证，不用于临时调试
- Agent/RAG 测试需要先写评估脚本（`scripts/eval_agent.py`），然后用本地模型跑
- 本地模型跑通 = 工程能力证明；云模型只是锦上添花
- 已记入 memory: [[feedback_cost-control]]

---

## 二、今日完成的工作

### 上午（上一轮会话）

**RAG 管线重写（5 个 commit）：**
- `build_vector_db support JSON` — JSON 知识库接入向量库
- `知识库同步API + 启动自动检测` — `knowledge_sync.py`：增量嵌入 + content_hash 编辑检测
- `BM25+向量混合检索(RRF融合)` — jieba + BM25 + RRF 加权融合
- `RAG v2 混合检索评测结果` — Hit Rate@5: 76.67% → 80.00%, MRR: 0.7000 → 0.7117
- `文档更新` — 三份 docs 同步

**Agent 架构重构（plan Phase 1-3）：**
- Session TTL 自动清理（`_SESSION_META` + `_SESSION_HISTORY`）
- Thought 阶段捕获（LLM 推理文本不再丢失）
- SSE 流式输出（threading+queue 桥接，Thought→Action→Observation 实时推送）
- BGE Reranker 精排（粗召回 k=20 → cross-encoder → top-5）
- Chunk Size 对比脚本（`compare_chunks.py`）
- API Key import-time snapshot 修复（7 文件改延迟读取）
- LangGraph 移除 → 手写 ReAct 循环 + 历史压缩 + max_steps=6

**Phase 4-5：**
- AI 课程体系扩展（ai-curriculum.json schema 扩展）
- 更新日志页面（/changelog + changelog.json）
- 三份 docs 版本对比更新

### 下午（本轮会话）

**分发打包：**
- `requirements-offline.txt` — 只含 flask+requests，不装 chromadb/langchain/PyTorch
- `.env.example` — 含所有配置项说明
- `setup_models.py` — 一键初始化
- `README.md` — v3.0 更新
- 重依赖懒加载 — 不装 chromadb 也能启动服务器

**前端面试知识库：**
- `data/knowledge/frontend-interview.json` — 47 道面试题，覆盖 Vue3/React/小程序/TypeScript/工程化/网络

**本地模型化（架构级改造）：**

| 文件 | 改动 |
|------|------|
| `config.py` | 新增 `LLM_PROVIDER`(默认local)、`LOCAL_MODEL_NAME`、`LOCAL_COMPRESS_MODEL` |
| `services/local_llm.py` | 新增 `get_agent_llm()` — Ollama `/api/chat` 原生 tool calling；`FakeAIMessage` 兼容 LangChain |
| `services/llm_service.py` | `get_llm()` 根据 `LLM_PROVIDER` 切换本地/云端，本地模型自动 fallback |
| `services/agent_service.py` | 传入 `tools=TOOLS` 给 `get_llm()`，本地模型也能 function calling |
| `.env.example` | 新增 LLM 提供商全部配置项 |

**本地模型矩阵：**

| 模型 | 大小 | 用途 | 状态 |
|------|------|------|------|
| `llama3.1:8b` | 4.9 GB | Agent 推理 | ✅ 已装，tool calling 已验证通过 |
| `qwen2.5:0.5b` | 397 MB | 历史压缩 | ✅ 刚下完，待验证 |
| `qwen3-vl:8b` | 6.1 GB | 视觉（备选）| ⚠️ VL 变体，非最佳 Agent 模型 |
| `deepseek-r1:8b` | 5.2 GB | 推理 | ❌ 不适合 tool calling |

**当前默认：** `LLM_PROVIDER=local`，Agent 用 `llama3.1:8b`，压缩用 `qwen2.5:0.5b`。切 DeepSeek 只需 `.env` 改 `LLM_PROVIDER=deepseek`。

---

## 三、用户的可视化与架构想法（下次实现）

### 3.1 模型切换 UI

**现状：** 切换模型需要改 `.env` 文件 → 切后台 → 重启服务器。不合理。

**目标：** 前端可视化模型选择器，类似 Codex/ChatGPT 的模型切换下拉菜单。

**两个入口：**
1. **设置页面** — 用户配置自己的 model 名字和 API Key（填完才能在前端切换器中看到）
2. **模型切换按钮** — 顶部栏或 AI 面板旁，下拉显示已配置的模型 + 一个"+"按钮，点加号弹窗让用户填新模型的名称/API Key/provider

**字段：**
- 模型名称（如 `deepseek-v4-flash` 或 `llama3.1:8b`）
- Provider（local Ollama / 自定义 API）
- API Key（可选，local 不需要）
- API Base URL（可选，用于第三方 API）

**存储：** 这些配置存 `data/user_data/model_providers.json`（不存 .env，因为运行时动态切换）

### 3.2 知识库搜索推荐榜

**现状：** 知识库只在用户主动搜索时显示结果。

**目标：** 
- 统计用户搜索历史（存 localStorage 或 user_data）
- 按搜索频率排序，在知识库页面展示 "热门搜索" / "常看内容"
- 自动推荐相关领域（基于已有搜索词关联）

### 3.3 版本更新区域对接 docs

**现状：** `/changelog` 页面展示 `changelog.json` 的 3 个版本历史。

**问题：** 数据结构简单（只有文字），没有对接 docs 下的详细文档。

**目标：**
- 每个版本条目可展开，引用 docs 中对应章节（optimization-roadmap、debug-report、dataset-doc）
- 量化评估结果可视化（RAG Hit Rate/MRR 趋势图、ChromaDB chunks 增长图）
- 路线图进度条（已勾选/总数）

### 3.4 可视化的定位

**双层目标：**
1. **教学** — 可视化帮助用户（自己 + 朋友）理解 AI 系统如何工作（RAG 流程、Agent 决策链）
2. **展示** — 作为个人作品和作业展示，"我建了什么系统" 比 "我会什么知识" 更有说服力

### 3.5 Agent 扩展：MCP + Skill

**后期方向：**
- MCP (Model Context Protocol) — 让 Agent 接入外部工具和数据源
- Skill 系统 — 可插拔的能力模块（如多模态教学：图片识别解释、代码运行可视化、语音交互）
- 目的是多模态教学与学习，不只是文字问答

---

## 四、下次会话行动清单

**优先级排序：**

### P0 — 本地模型完善
- [ ] 验证 `qwen2.5:0.5b` 压缩管道端到端
- [ ] 运行一次完整 Agent 对话（用 llama3.1:8b），验证 ReAct 循环全流程
- [ ] 测试历史压缩在实际多轮对话中是否生效

### P1 — 模型切换 UI
- [ ] 设置页面加模型配置表单（provider/name/api-key/base-url）
- [ ] 前端全局模型切换下拉按钮
- [ ] "+" 弹窗添加新模型
- [ ] 后端 API：`GET/POST /api/config/models` 管理模型列表

### P2 — 知识库增强
- [ ] 搜索历史统计（localStorage）
- [ ] 热门搜索推荐榜 UI
- [ ] 知识库浏览页默认展示推荐而非空白

### P2 — 更新日志增强
- [ ] changelog.json 结构扩展：关联 docs 文件引用
- [ ] RAG 评测趋势可视化
- [ ] 路线图进度条

### P3 — 长期探索
- [ ] `qwen3:6b`（或更大）本地模型实验
- [ ] MCP 协议接入评估
- [ ] Agent Skill 插件架构设计
- [ ] 多模态教学原型

---

## 五、关键文件索引

| 文件 | 说明 |
|------|------|
| `services/agent_service.py` | 自定义 ReAct 循环 + 历史压缩 + Session 管理 |
| `services/local_llm.py` | Ollama 本地模型封装（Agent + 压缩） |
| `services/llm_service.py` | LLM 统一入口（local/deepseek 切换） |
| `services/rag_service.py` | BM25+向量+Reranker 混合检索 |
| `services/knowledge_sync.py` | JSON→ChromaDB 增量同步 |
| `config.py` | 全局配置（含 LLM_PROVIDER 等新项） |
| `data/knowledge/frontend-interview.json` | 前端实习面试 47 题 |
| `docs/checkpoint-2026-06-04.md` | 本文件 |

---

> 生成时间: 2026-06-04 20:30
> 下次 compact 恢复后优先读此文件
