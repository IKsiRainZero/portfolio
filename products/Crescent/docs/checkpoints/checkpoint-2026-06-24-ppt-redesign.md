# Checkpoint: 答辩PPT重构设计完成 — 2026-06-24 晚

## 核心决策

- **命名**: ContinuumAgent → **CrescentAgent**（拉丁语 crēscēns = 生长/渐增，现在分词 = 永远在进行时）
- **叙事转变**: 从"Agent技术展示" → "整个项目全面展示 + 个人心路历程"
- **风格**: 瑞士国际主义B（guizang-ppt-skill），IKB蓝，保持旧PPT模板

## 13页结构（已确认）

| # | 页面 | 版式 | 截图 |
|---|------|------|------|
| 01 | 封面 · CrescentAgent | S01 IKB满屏 | 无 |
| 02 | 我为什么做这个 | S03 Split Statement | 无 |
| 03 | 技术选择与理由 | S19 Four Cards | 无 |
| 04 | 系统架构总览 | S17 System Diagram | 无 |
| 05 | 知识管道 | S11 Horizontal Timeline | SC-01/02/03 |
| 06 | 学习闭环 | S14 Loop Form | 无（技术视角，非功能截图）|
| 07 | 设计到落地:3个鸿沟 | S13 Three Forces | 无 |
| 08 | Agent技术内核 | S17变体 | SC-08(打断演示) |
| 09 | 可靠性 | S12 Manifesto | 无 |
| 10 | 持续迭代 | S02 Vertical Timeline+KPI | 无 |
| 11 | 检索Benchmark | S21 Tech Spec | 无 |
| 12 | 不足与自检中心 | S19 Four Cards | SC-09(Eval仪表盘) |
| 13 | Crescent | S01 IKB满屏 | 无 |

**13页后的空页**: 放备用截图，需要时切出来给评委看

## 每页设计细节

### 01 · 封面
- CHROME: CrescentAgent · Defense / 2026-06
- KICKER: SELF-EVOLVING LEARNING SYSTEM
- TITLE: Crescent / Agent
- SUBTITLE: 从ReAct循环到自评估闭环 / 从功能堆叠到系统化架构 / ——一个在不断变好的终生学习伙伴

### 02 · 我为什么做这个
- 左暗底(INK): "今年1月每天醒来，AI都能多做一件事。知识触手可及，但哪些值得学？学了，真的会了吗？"
- 右亮底: "不是AI发展太快我们就不用学了。反而是因为AI替人做了很多，我才意识到：能长在自己身上的，终究有限。"

### 03 · 技术选择与理由
- FastAPI / ReAct+意图分类 / ChromaDB+BGE-M3 / 原生JS(零依赖)
- 每项：选择+理由

### 04 · 系统架构总览
- CORE: ReAct循环+12 Tool(10静态+2数据源动态注入)+asyncio.Event取消
- MIDDLE: RAG混合检索(向量+BM25+RRF融合+Cross-Encoder精排)+查询改写+查询扩展+Harness校验链+Eval自评估(16评分+影子模式)
- OUTER: FastAPI异步+ChromaDB(bge-m3 1024维,4015+chunks)+DeepSeek+Ollama双后端+三级降级链

### 05 · 知识管道
- 五步: 搜索(cn.bing+搜狗)→审查(勾选/预览/URL可点击)→清洗(安全过滤/长度校验/去重)→切分嵌入(500字+150重叠/bge-m3)→入库(ChromaDB本地)
- 截图: SC-01搜索结果卡片, SC-02入库进度, SC-03 chunk预览

### 06 · 学习闭环
- 技术视角: 意图分类→Tool调度→RAG检索→Eval反馈
- 右侧环形SVG(保留旧版)

### 07 · 设计到落地
- 01意图分类(闲聊fast-path) / 02迭代RAG(渐进式披露top-2→top-5) / 03 Plan-first(轻量计划生成,失败回退标准ReAct,实现在agent_service.py:918-977)

### 08 · Agent技术内核
- 01真正取消(asyncio.Event) / 02三级降级(DeepSeek→Ollama→Mock) / 03工具画像(消息关键词→工具组) / 04 Harness校验链 / 05 Session管理(TTL+LRU+消息压缩)
- 截图: SC-08(打断演示)

### 09 · 可靠性
- 左: "模型会有幻觉？硬性约束规范。校验用代码，不用prompt。"
- 右: Harness校验链+Eval自评估+安全基础设施
- 底部Ink Banner: "可靠性不是事后补救，而是设计起点。"

### 10 · 持续迭代
- 时间线: 2026-05功能堆叠期→06上旬设计系统失败(23 commit废弃)→06中旬Eval系统上线+文档版本铁律→06月22-23演示阻塞Bug马拉松→06月23-24 Phase1-3冲刺→现在Crescent
- KPI: 41+修复/115 API端点/12 Tool/4015+ chunks

### 11 · 检索Benchmark
- Before ~70% / Now 100%(内部30条) / CRUD-RAG 99.3%(第三方150条)
- 诚实附注: 内部高是因为KB小，大规模会降，但第三方基准证明管道可行

### 12 · 不足与自检中心
- 延迟/覆盖/冷启动/训练器未接Agent
- 截图: SC-09(Eval自检中心仪表盘，**需先开发施工页深层页面**)

### 13 · Crescent
- "Crescent 永远在进行时"

## 口述风格
PPT摆事实(截图+数据)，人讲心路(从随便搞搞→越不满意越想做→成本爆炸/API泄露/注意力涣散/设计系统全废/演示前5个Bug→坚持下来)

## 待做

1. **PPT HTML代码** — 基于旧`templates/ppt/index.html`修改，瑞士风B，13页+空页备用
2. **施工页Eval自检中心深层页面** — reviewAgent+eval 16维度可视化仪表盘（SC-09前置依赖）
3. **截图注册表** — SC-01~SC-11，不需要的: SC-04/05/06/07(06页不截图), SC-10(11页不截图), SC-11(12页保留SC-09)
4. **演讲稿** — 13页完整口述稿
5. **PPT副本同步** — 改完后同步到 `portfolio-app/docs/交付/templates/ppt/index.html`

## 下次读这些文件
- `portfolio-v3/portfolio-app/templates/ppt/index.html`（旧PPT源文件，基于此修改）
- `portfolio-v3/guizang-ppt-skill-main/guizang-ppt-skill-main/assets/template-swiss.html`（瑞士风种子模板）
- `portfolio-v3/guizang-ppt-skill-main/guizang-ppt-skill-main/references/layouts-swiss.md`（版式参考）
- `portfolio-v3/guizang-ppt-skill-main/guizang-ppt-skill-main/references/themes-swiss.md`（主题色参考）
- `portfolio-v3/portfolio-app/services/review_agent.py`（reviewAgent，施工页深层页参考）
- `portfolio-v3/portfolio-app/routes/api_review.py`（已deprecated，迁移到eval）
- `portfolio-v3/portfolio-app/templates/pages/construction.html`（施工页现状）
- 本checkpoint文件
