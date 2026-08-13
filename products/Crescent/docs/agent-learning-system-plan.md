# 个性化学习 Agent 系统 — 完整规划

> 创建于 2026-06-02 | 状态: 规划完成，待执行

---

## 项目一句话

基于 LangChain 从零构建 ReAct Agent，嵌入已有 Flask 教学网站，让 Agent 接管知识检索、自适应出题、学习诊断和复习调度。

## 技术选型

| 决策 | 选择 |
|------|------|
| 向量数据库 | Chroma (轻量 Python 原生) |
| Embedding | bge-large-zh (MTEB 中文最佳) |
| Agent 框架 | LangChain ReAct → 后续升级 LangGraph |
| 联网搜索 | DuckDuckGo 免费 → 不够换 Tavily |
| 存储 | JSON 文件 (progress.json / srs_schedule.json) |

## 符号说明

```
■ 已完成    ◧ 部分完成需升级    □ 待建设    ★ 最高优先级
```

---

# 一、完整规划树

## 1. 基础设施层

```
□ 1.1 开发环境
  □ 1.1.1 pip install langchain langchain-community chromadb sentence-transformers pandas
  □ 1.1.2 pip install pymupdf python-docx python-pptx duckduckgo-search
  □ 1.1.3 requirements.txt 更新

□ 1.2 配置系统扩展
  □ 1.2.1 config.py 新增 CHROMA_PATH, EMBEDDING_MODEL, LANGSMITH_TRACING
  □ 1.2.2 .env 统一管理 API Key (DEEPSEEK_API_KEY)
  □ 1.2.3 DeepSeek LLM 封装为 LangChain ChatDeepSeek
```

## 2. 知识库系统

```
□ 2.1 数据来源
  □ 2.1.1 PDF 导入 → pymupdf 读取 论文原文/ 12篇
  □ 2.1.2 Markdown 导入 → 知识库/导出/ 25领域 200+闪卡
  □ 2.1.3 个人项目导入 → Desktop docx/pptx → MD 转换
  □ 2.1.4 外部数据源评估 → UltraData / HuggingFace / arXiv API
  □ 2.1.5 Agent 联网搜索 Tool → DuckDuckGo

□ 2.2 数据处理
  □ 2.2.1 多格式转换器 (PDF→MD, DOCX→MD, PPTX→MD)
  □ 2.2.2 数据清洗管道 (去噪/去重/格式标准化)
  □ 2.2.3 元数据提取 (标题/作者/日期/标签/来源)
  □ 2.2.4 文档分类 (面试/论文/项目/灵感 自动分领域)

□ 2.3 文档切分
  □ 2.3.1 固定长度切分 (chunk_size=500, overlap=50)
  □ 2.3.2 递归字符切分 (RecursiveCharacterTextSplitter)
  □ 2.3.3 语义切分 (按 ## 标题 + 段落边界)
  □ 2.3.4 chunk_size/overlap 参数对比实验
  □ 2.3.5 父子文档模式 (小chunk检索 + 大chunk返回)

□ 2.4 向量化与存储
  □ 2.4.1 Embedding 模型选型对比 (bge vs m3e vs text2vec)
  □ 2.4.2 Chroma 向量库初始化 + 按领域分 Collection
  □ 2.4.3 批量向量化脚本 (文档 → embed → Chroma)
  □ 2.4.4 增量更新机制 (新增/修改 → 自动同步)
  □ 2.4.5 向量库备份方案
```

## 3. RAG 系统

```
□ 3.1 检索管道
  □ 3.1.1 基础向量检索 (similarity_search_with_score, k=5)
  □ 3.1.2 混合检索 (BM25 稀疏 + 向量 密集 加权融合)
  □ 3.1.3 重排序 (bge-reranker-large)
  □ 3.1.4 查询预处理 (改写/扩展/HyDE)
  □ 3.1.5 多路召回融合 (RRF)
  □ 3.1.6 上下文压缩 (ContextualCompressionRetriever)
  □ 3.1.7 来源引用 (chunk来源文档 + 页码/段落)

□ 3.2 生成管道
  □ 3.2.1 RAG Prompt 模板 (context + question + 指令)
  □ 3.2.2 答案引用标注 ([来源: 文档名])
  □ 3.2.3 幻觉检测 (答案 vs 检索上下文 一致性)
  □ 3.2.4 降级策略 (检索无结果 → 纯LLM + "未找到相关资料")

□ 3.3 RAG 评估
  □ 3.3.1 检索指标 (Recall@5, Precision@5, MRR, NDCG@5)
  □ 3.3.2 生成指标 (Faithfulness, Answer Relevance)
  □ 3.3.3 人工测试集 (每领域5题 + 标准答案)
  □ 3.3.4 RAGAS 自动化评估框架
```

## 4. Agent 系统

```
□ 4.1 LLM 接入
  □ 4.1.1 LangChain ChatDeepSeek 封装 (复用 config.py)
  □ 4.1.2 流式输出支持 (SSE)
  □ 4.1.3 Token 计数与成本追踪
  □ 4.1.4 速率限制与指数退避重试

□ 4.2 Prompt 模板
  ■ 4.2.1 基础 System Prompt (已有 services/deepseek_client.py)
  □ 4.2.2 Agent System Prompt (角色 + 工具规则 + 输出格式)
  □ 4.2.3 寓言故事 Prompt (Amanda Askell 版 Fable Prompt)
  □ 4.2.4 费曼检查 Prompt (用户解释质量评估)
  □ 4.2.5 深度提问 Prompt (概念迁移场景生成)
  □ 4.2.6 出题 Prompt (MCQ/编程/问答 按领域+难度)

□ 4.3 Tool 工具系统 (Agent 的手)
  □ 4.3.1 search_knowledge(query) → 向量检索 + RAG 回答
  □ 4.3.2 generate_question(topic, type, difficulty) → 出题
  □ 4.3.3 evaluate_answer(question, user_answer) → 评分+反馈
  □ 4.3.4 analyze_progress() → 读 progress.json + 统计
  □ 4.3.5 diagnose_weakness() → 弱项识别 + 推荐
  □ 4.3.6 create_study_plan(weak_areas) → 学习计划
  □ 4.3.7 fable_explain(concept) → 寓言故事 + 揭示
  □ 4.3.8 feynman_check(concept, user_explanation) → 评估+追问
  □ 4.3.9 deep_question(concept, user_level) → 场景迁移题

□ 4.4 Agent 核心 (大脑)
  □ 4.4.1 意图路由器 (问答/学习/出题/复习/闲聊 五分类)
  □ 4.4.2 ReAct Agent 主循环 (Thought→Action→Observation→Final)
  □ 4.4.3 短期记忆 (ConversationBufferWindowMemory, k=10)
  □ 4.4.4 长期记忆 (读写 progress.json + srs_schedule.json)
  □ 4.4.5 摘要记忆 (ConversationSummaryMemory 超长对话)
  □ 4.4.6 安全护栏 (输入过滤 + 输出拦截 + Topic 边界)

□ 4.5 Agent 集成
  □ 4.5.1 API 路由 POST /api/agent/chat + GET /api/agent/stream
  □ 4.5.2 SSE 流式输出 → 前端展示 Agent 思考步骤
  □ 4.5.3 升级 ai-chat.js → Agent 交互面板
  □ 4.5.4 /trainer 对接 Agent (代替当前简单API调用)
  □ 4.5.5 /knowledge 对接 Agent (智能检索入口)
  □ 4.5.6 /interview 对接 Agent (Agent 作为面试官)
  □ 4.5.7 / 仪表盘对接 Agent (推荐今日学习计划)
```

## 5. 教学系统 (听·说·读·写·用)

```
□ 5.1 听 — 寓言故事学习
  □ 5.1.1 寓言 Prompt 模板 + 生成管道
  □ 5.1.2 知识卡增加 "用故事学" 按钮
  □ 5.1.3 多叙事风格 (寓言/科幻/历史/日常)
  □ 5.1.4 故事后检验题 + 理解评估
  □ 5.1.5 故事收藏与回顾

□ 5.2 说 — 费曼学习法
  □ 5.2.1 用户选择概念 → 用自己的话解释
  □ 5.2.2 Agent 评估 (准确性/完整性/清晰度/通俗度)
  □ 5.2.3 Agent 盲区追问
  □ 5.2.4 标准解释 vs 用户解释 差距对比
  □ 5.2.5 掌握度更新 (写入 progress.json)

□ 5.3 读 — 结构化阅读
  ■ 5.3.1 知识卡浏览 (已有 /knowledge)
  □ 5.3.2 关联概念推荐 (读完A → 推荐B/C)
  □ 5.3.3 阅读进度可视化
  □ 5.3.4 阅读理解检查 (读后弹出1题)

□ 5.4 写 — 主动练习
  ■ 5.4.1 MCQ 选择题 (已有 trainer-mcq.js)
  ■ 5.4.2 编程题 (已有 trainer-code.js)
  ■ 5.4.3 闪卡 (已有 trainer-flash.js)
  □ 5.4.4 自适应难度 (根据正确率调整)
  □ 5.4.5 干扰项智能生成 (Agent 出干扰项)
  □ 5.4.6 简答题 (Agent 语义评分)
  □ 5.4.7 错题本 (自动收集 + 归类 + 定时推送)
  □ 5.4.8 题目质量评估 (Agent 标记低质量题)

□ 5.5 用 — 概念迁移与应用
  □ 5.5.1 场景迁移题 (同一概念 → 新场景)
  □ 5.5.2 深层追问链 (Agent 多轮深度提问)
  □ 5.5.3 跨概念联结 (概念A+B 交叉应用题)
  □ 5.5.4 真实案例挑战 (论文/项目提取真实场景)
  ■ 5.5.5 模拟面试 (已有 /interview, 需 Agent 升级)
```

## 6. 知识管道整合

```
□ 6.1 知识库 ↔ 题库打通
  □ 6.1.1 知识卡自动出题 (每卡 → 3道关联题)
  □ 6.1.2 错题反哺知识卡 (高错题率 → 标记重写)
  □ 6.1.3 进度双向同步 (Trainer ↔ 知识卡掌握度)
  □ 6.1.4 SRS 联动 (低评分 → 推荐寓言/费曼重学)

□ 6.2 Obsidian ↔ 网站打通
  ■ 6.2.1 Obsidian Vault (知识库/ 目录)
  □ 6.2.2 笔记同步到网站知识库
  □ 6.2.3 学习记录回写 Obsidian Daily Note
  □ 6.2.4 Claudian 作为 Obsidian 内开发助手

□ 6.3 外部数据源
  □ 6.3.1 数据源选型 (arXiv vs Semantic Scholar vs UltraData vs HuggingFace)
  □ 6.3.2 Agent 联网搜索 Tool (DuckDuckGo)
  □ 6.3.3 定时拉取脚本 (Cron/手动 → 最新论文摘要 → Inbox)
  □ 6.3.4 网页内容提取 (BeautifulSoup + readability-lxml)
  □ 6.3.5 视频转文字 (yt-dlp + whisper → MD笔记)

□ 6.4 GitHub 发布管道
  □ 6.4.1 代码自动推送 (dev → commit → push)
  □ 6.4.2 README 自动生成 (Agent 读项目结构)
  □ 6.4.3 演示素材 (录屏脚本 + 关键功能截图)
  □ 6.4.4 作品集页面自动更新
```

## 7. 评估与课程交付

```
□ 7.1 评估体系
  □ 7.1.1 RAG 检索评估 (Hit Rate, MRR, Recall@5)
  □ 7.1.2 Agent 任务成功率 (意图识别准确率、工具选择正确率)
  □ 7.1.3 教学效果评估 (答题正确率变化、薄弱点收敛)
  □ 7.1.4 用户满意度 (评分 + 开放式反馈)

□ 7.2 课程交付物
  □ 7.2.1 源码工程 (GitHub 仓库)
  □ 7.2.2 部署文档 (README: 环境/安装/配置/启动)
  □ 7.2.3 设计文档 (Agent 架构章节)
  □ 7.2.4 数据集说明 (知识库规模/来源/清洗流程)
  □ 7.2.5 答辩 PPT (场景→架构→技术→效果→分工)
  □ 7.2.6 演示视频 (5分钟完整流程)
  □ 7.2.7 调试报告 (问题与解决方案)
```

---

# 二、执行顺序

```
Phase 0: 环境准备 (1天)
  [01] pip install langchain langchain-community chromadb sentence-transformers pandas pymupdf
  [02] 扩展 config.py (CHROMA_PATH, EMBEDDING_MODEL)
  [03] DeepSeek LLM 封装为 LangChain ChatDeepSeek

Phase 1: 向量知识库 (3天)
  [04] PDF→MD 转换脚本 (pymupdf)
  [05] DOCX/PPTX→MD 转换脚本 (python-docx, python-pptx)
  [06] 数据清洗管道 (去噪/去重/格式标准化)
  [07] 文档切分脚本 (RecursiveCharacterTextSplitter + 参数实验)
  [08] Embedding 模型选型对比 (bge vs m3e vs text2vec)
  [09] Chroma 向量库初始化 + 批量向量化
  [10] 验证: 基础向量检索 → 检查结果质量

Phase 2: RAG 管道 (2天)
  [11] RAG Prompt 模板 + 上下文拼接
  [12] 混合检索实现 (BM25 + 向量)
  [13] 重排序实现 (bge-reranker)
  [14] 来源引用 + 幻觉检测
  [15] RAG 评估: 人工测试集 + 指标计算

Phase 3: Agent 核心 (4天)
  [16] Tool 1-4: 知识检索、题目生成、进度分析、薄弱点诊断
  [17] Tool 5-9: 题目批改、学习计划、寓言讲解、费曼教练、深度提问
  [18] 意图路由器 (问答/学习/出题/复习 四分类)
  [19] ReAct Agent 主循环 (create_react_agent)
  [20] 记忆管理 (短期对话 + 长期 progress.json)
  [21] 安全护栏 (输入/输出过滤 + Topic 边界)
  [22] Agent API 路由 (POST /api/agent/chat)

Phase 4: Agent ↔ 前端集成 (2天)
  [23] SSE 流式输出 (前端展示 Thought→Action→Observation)
  [24] 升级 ai-chat.js → Agent 交互面板
  [25] Agent 对接 /trainer
  [26] Agent 对接 /knowledge
  [27] Agent 对接 / 仪表盘

Phase 5: 教学系统 — 听·说·读·写·用 (5天)
  [28] 听: 寓言 Prompt 模板 + 生成管道
  [29] 听: 知识卡 "用故事学" 按钮 + 前端交互
  [30] 说: 费曼学习法 — 输入→评估→追问 循环
  [31] 说: 前端费曼教练 UI
  [32] 读: 关联概念推荐 + 阅读进度可视化
  [33] 写: 自适应难度 + 干扰项智能生成
  [34] 写: 简答题 Agent 语义评分
  [35] 写: 错题本自动收集 + 定时推送
  [36] 用: 场景迁移题 + 深层追问链
  [37] 用: 模拟面试 Agent 驱动升级

Phase 6: 知识管道整合 (2天)
  [38] 知识卡自动出题 (每卡→3题)
  [39] 错题反哺知识卡 (高错题率 → 标记对应知识卡)
  [40] SRS 联动 (低评分 → 推荐寓言/费曼重学)
  [41] Agent 联网搜索 Tool (DuckDuckGo)
  [42] arXiv 定时拉取脚本

Phase 7: 评估 + 交付物 (3天)
  [43] RAG 评估: Hit Rate, MRR, Recall@5 跑分
  [44] Agent 评估: 意图识别准确率、工具选择正确率
  [45] 教学效果评估: 用户答题正确率变化
  [46] 设计文档更新 (Agent 架构章节)
  [47] 答辩 PPT + 演示视频
  [48] 调试报告 + README + 数据集说明
```

---

# 三、执行前确认

## 风险与应对

| 风险 | 应对 |
|------|------|
| LangChain Agent 不稳定 (选错工具/循环) | max_iterations=5, fallback 规则兜底 |
| Chroma 查询慢 | 文档量<500不慢, 真慢换 FAISS |
| DeepSeek API 限流 429 | 指数退避重试, 本地缓存常用回答 |
| Token 消耗超标 | 每次调用记录 cost, 设每日预算告警 |
| 某个 Tool 返回格式错误 | Tool 输出统一加结构化 schema |

## 权限控制

| 层面 | 措施 |
|------|------|
| Agent API | `/api/agent/*` 本地免认证 |
| 代码执行 | 复用已有 sandbox (code_runner.py), Agent 不直接 exec |
| 文件写入 | Agent 只写 `data/user_data/` |
| API Key | 环境变量, 不硬编码, .gitignore |

## 时间估算

| Phase | 内容 | 天数 |
|-------|------|------|
| 0 | 环境准备 | 1 |
| 1 | 向量知识库 | 3 |
| 2 | RAG 管道 | 2 |
| 3 | Agent 核心 | 4 |
| 4 | Agent↔前端集成 | 2 |
| 5 | 听说读写用 | 5 |
| 6 | 知识管道整合 | 2 |
| 7 | 评估+交付物 | 3 |
| **总计** | | **22天** |
```

---


