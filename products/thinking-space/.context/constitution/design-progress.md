---
date: 2026-07-08
status: 设计完成 — 8 节全部确认，审阅问题已解决，待转入实施计划
context: 全景整合后产生的"思考空间"元系统构想
next: 写实施计划（writing-plans）
review: 2026-07-08 完成设计审阅，C1-C3 + I1-I6 已解决
---

# 思考空间 — 设计文档

## 概念定义

**思考空间**是一个面向自己的思维元系统。核心功能是**诊断**——输入一个问题，沿着层次链告诉你"这一层你知道什么、缺什么"。围绕诊断，支持写（倒出混乱想法）、连（跨层发现关联）、看（全景可视化）三种辅助操作。

## 关键决策

1. **性质**：元系统，不绑定 Crescent。可以复用 portfolio 下任何已有资源
2. **用户**：单人使用，产出可分享/导出
3. **层次链**：不预设固定骨架——层次分解是核心方法，但具体链可自定义。V1 用"细胞→组织→器官→系统→人→社会→国家→世界→星系→宇宙"作为第一条链
4. **核心操作**：诊断（B 优先），写/连/看围绕诊断运转
5. **已知来源**：手动录入 + portfolio 自动索引 + 对话积累，三者都有。额外关注"不知道自己知道什么"的问题
6. **输出**：差距地图 → 行动清单 → 持续更新的活模型（分阶段验证）
7. **维度策略**：V1 只做一条物质链（A），但数据模型从第一天起就是多维的（为 C 留扩展），不预设三维交叉（B 不是 V1 范围）

---

## 第一节：架构

| 层 | 技术 | 复用来源 |
|----|------|----------|
| 后端 | Python + FastAPI | 复用 Crescent 的 FastAPI 模式 |
| 前端 | React + TypeScript + CSS Modules | 借鉴 Crescent 的组件风格，不直接复用 |
| 数据 | SQLite（本地单用户，未来可换） | 零依赖 |
| 知识索引 | 读 portfolio 其他项目的 constitution、memory、session | 现有的 `.context/` 和 memory 系统 |
| 测试 | pytest + React Testing Library | 复用 Crescent 的测试基础设施 |

项目位置：`products/thinking-space/`，独立项目，不放入 Crescent。

---

## 第二节：数据模型

```
Dimension（维度/层次链）
├── id: UUID
├── name: str          — "物质层次"
├── description: str   — "从物理本质出发的层级分解"
├── sort_order: int    — 多维度时的展示顺序
├── created_at, updated_at
└── layers: List[Layer]

Layer（层级）
├── id: UUID
├── dimension_id: FK → Dimension
├── name: str          — "细胞", "组织", "器官"...
├── level: int         — 在链中的位置 (0=细胞, 9=宇宙)
├── description: str?  — 该层的简短说明
├── sort_order: int    — 同维度内的排序（默认=level）
├── created_at, updated_at
└── entries: List[Entry]

Entry（知识条目）
├── id: UUID
├── title: str
├── content: text?     — 详细内容（可选，支持"只知道标题"的情况）
├── entry_type: enum   — known | unknown | question
├── layer_id: FK → Layer
├── dimension_id: FK → Dimension  — 冗余FK，加速单维度查询
├── source_type: enum? — manual | portfolio_index | conversation
├── source_link: str?  — 来源URL或文件路径
├── status: enum       — pending | confirmed | ignored (默认 manual→confirmed, indexed→pending)
├── tags: JSON/str?    — 自由标签，不做结构化预设
├── confidence: 0-100? — 我对这条认知的确信度（自动索引的条目可带 LLM 估计值）
├── created_at, updated_at
└── cross_links: List[CrossLink]

CrossLink（跨层连线）
├── id: UUID
├── source_entry_id: FK → Entry
├── target_entry_id: FK → Entry
├── relation_type: str — "supports" | "contradicts" | "relates_to" | "explains"
├── note: text?        — 连线说明
├── created_at
```

### 索引策略

- `Layer(dimension_id, level)` — 主查询路径：取某维度下所有层，按层级排序
- `Entry(layer_id, entry_type)` — 诊断查询：某层下的已知/未知/问题
- `Entry(dimension_id)` — 按维度取全部条目
- `CrossLink(source_entry_id)`, `CrossLink(target_entry_id)` — 查找条目的所有连线

### V1 实际数据

- 1 条 Dimension："物质层次"
- 10 个 Layer：细胞→组织→器官→系统→人→社会→国家→世界→星系→宇宙
- Entry 从手动录入 + portfolio 索引开始填充
- CrossLink 暂时为零，表建好等涌现

### 扩展预留

- `Dimension` 天生复数 → 加第二条链不改任何现有数据
- `Entry.dimension_id + layer_id` 复合定位 → 未来同一 Entry 可挂多链多层（加关联表）
- `tags` 自由 JSON → 分类体系在使用中涌现
- `CrossLink` 独立实体 → V1 空表，有连线时自然长出来
- `source_type` enum 可随时加新值

---

## 第三节：交互流程

### 主流程：诊断（B — 入口）

```
用户打开思考空间
  → 看到 ZUI 画布全景（10 层纵向排列）
  → 底部 Dock 输入问题（如"我为什么焦虑"）
  → 系统逐层展开：每层显示已知/未知/问题卡片
  → 用户点击任意层缺口可展开/添加 Entry
  → 诊断完成后可导出"差距地图"
```

### 辅助流程：写（A）

```
在任意层点击"+"
  → 弹出输入框：标题 + 内容 + 类型(已知/未知/问题) + 来源链接(可选)
  → 保存后卡片立即出现在该层
  → 支持从 portfolio 文件路径自动生成来源链接
```

### 辅助流程：连（C）

```
在 Entry 卡片上
  → 点击"连线到另一个条目"
  → 搜索/浏览其他 Entry
  → 选择目标 + 关系类型
  → 连线出现在两个 Entry 的详情中
```

### 辅助流程：看（D — 全景底图）

全景画布 = 默认视图（ZUI 画布），是诊断的持久空间上下文：
- 纵向：10 层从上到下排列
- 横向：每层 known/unknown/question 三列
- 颜色编码：绿色(已知) / 红色(未知) / 黄色(问题) / 虚线边框(待确认)
- 缩放导航：缩到最小=全景，放大=层级详情，再放大=卡片编辑

**全景与诊断的关系：全景是底图，诊断是透镜。** 诊断输入不切换页面——它在同一画布上叠加滤镜：相关条目高亮，无关条目变淡。结构不变，焦点变了。"通过结构暴露问题"（全景）+ "动态具体分析"（诊断）= 同一画布的两种模式。

### 诊断时序模型

诊断逐层展开的节奏：
- 用户输入问题 → LLM 逐层分析（每层一次推理调用，共 10 次）
- 每层完成后立即在画布上更新该层的卡片高亮（不等全部完成）
- 空层（0 条目）不跳过——显示"该层暂无记录"并标记为潜在探索区
- 全部 10 层完成后 → Dock 显示"差距摘要"入口

### 关键交互约束

- 不存在页面切换——只有缩放层级变化
- 底部 Dock 自动显隐（鼠标靠近底部=展开，离开=收起）
- 诊断结果可保存为"诊断记录"快照

---

## 第四节：UI 结构

### 方案：ZUI 画布（Zoomable User Interface）

灵感：Miro 无限画布 + Figma 色块体系

```
┌──────────────────────────────────────────────────┐
│                                                    │
│   ┌─ 细胞 ────┐  ┌─ 组织 ────┐  ┌─ 器官 ────┐    │
│   │ 🟢🟡🔴  │  │ 🟢🟢🔴  │  │ 🟢🟢🟢🔴│    │
│   │           │  │          │  │           │    │   ← 全景 = 默认视图
│   └───────────┘  └──────────┘  └───────────┘    │     可缩放、可平移
│                                                    │
│   ┌─ 系统 ────┐  ┌─ 人 ─────┐  ┌─ 社会 ────┐    │
│   │ 🟢🟢🟡🔴│  │ 🟢🟢🟡  │  │ 🟢       │    │
│   │           │  │          │  │           │    │
│   └───────────┘  └──────────┘  └───────────┘    │
│                                                    │
│   ... 共 10 层，纵向排列，滚轮缩放 ...             │
│                                                    │
├──────────────────────────────────────────────────┤
│  🔍 诊断输入...    │  +  │  ✦ 连线  │  ⬇ 导出  │  ← Dock
└──────────────────────────────────────────────────┘
```

### 缩放层级

| 层级 | 看到什么 | 操作 |
|------|----------|------|
| 全景（默认） | 10 层概览 + 每层卡片数量 | 滚轮缩放、拖拽平移 |
| 层级视图 | 单层展开，三列卡片详情 | 点击卡片编辑、拖入新卡片 |
| 卡片视图 | 单张卡片完整内容 + 连线 | 编辑、连线、删除 |

### 底部 Dock

- 位置：屏幕底部居中
- 内容：诊断输入框 + 添加按钮 + 连线模式开关 + 导出按钮
- 行为：鼠标离开底部区域 2 秒后自动收起（留一条细线），靠近后展开
- 参考：macOS Dock 行为模式

### 色块体系

- 绿色卡片 = 已知（known）
- 红色卡片 = 未知缺口（unknown）
- 黄色卡片 = 问题（question）
- 半透明/虚线边框 = 自动索引发现、待确认
- 每层可有独立的微妙色调区分（参考 Figma 的 lime/lilac/mint/coral 色块）

### 设计原则

- UI 退让，内容说话（参考 Apple：chrome 只在对的时候出现）
- 不做暗色主题——亮色画布更接近"思考的白板"
- 不切换页面——缩放即导航
- 不直接复用 Crescent 组件——借鉴其工具依赖（framer-motion, CSS Modules），代码结构和教训

---

## 第五节：集成方案（知识索引）

### 索引来源

| 来源 | 路径模式 | 提取内容 |
|------|----------|----------|
| 项目 constitution | `products/*/.context/constitution/` | 设计决策、技术栈、已知限制 |
| Memory 系统 | `~/.claude/projects/.../memory/` | 用户关注点、经验教训、偏好 |
| Session 归档 | `products/*/.context/sessions/archive/` | 历史讨论主题、解决的问题 |
| 项目 CLAUDE.md | `products/*/CLAUDE.md` | 项目定位、关键路径 |
| Git 提交记录 | `git log --oneline` (各项目) | 实际做过什么、频率、方向 |

### 索引策略

```
知识索引器（独立 Python 模块）
  │
  ├── FileScanner   — 遍历 portfolio 文件树，匹配路径模式
  ├── TextExtractor — 读文件内容，提取 YAML frontmatter + markdown 段落
  └── EntryMapper   — 关键词匹配映射到物质层次链 + 未分类回退
```

### 映射逻辑（V1 关键词规则）

- 包含层次链关键词（"细胞""组织""社会"等）→ 直接映射对应层
- 包含技术关键词（"FastAPI""React""SQLite"等）→ 映射到"人"层
- 包含经济/资本关键词 → 映射到"社会"或"国家"层
- 无法匹配 → "未分类"区，用户手动拖拽到对应层

### 触发方式

- 启动时自动扫描（首次 + 文件变更检测）
- 底部 Dock 手动"刷新索引"按钮

### 索引结果呈现

- 自动发现的条目 = 半透明/虚线边框卡片（区别于手动录入的实心卡片）
- 用户点击 → 确认/编辑/忽略
- 确认后变成正常 Entry

### 索引条目生命周期

参考 D:\2026-6_xiaoxueqi\2026-7-03 智能文档管理项目的 Document 模型（upload→parse→extract 状态流转），定义自动索引条目的完整生命周期：

```
文件被扫描到
  → status="pending"（待确认），以虚线边框卡片出现在对应层级
  → 用户点击卡片：
      ├── "确认" → status="confirmed"，变实心，可正常编辑/连线
      ├── "编辑后确认" → 修改 title/content/layer 后确认
      └── "忽略" → status="ignored"，从画布消失（可过滤查看）
```

**字段填充规则：**
- `title`：取源文件第一个 `# 标题` 或文件名（去扩展名）
- `content`：截取前 500 字符作为摘要，source_link 指向完整文件
- `entry_type`：一律初始化为 `known`（因为你写了它 = 你某种程度上知道它）
- `confidence`：关键词匹配到的层 = 低置信度(30)，LLM 辅助匹配 = 中置信度(60)，手动确认 = 100

**去重策略：**
- 同一 `source_link` 只生成一条 Entry（文件→条目一对一）
- 用户手动创建的条目不受去重影响（source_link 为空或用户自定义）

**文件变更检测：**
- 启动时对比文件修改时间 vs Entry 的 updated_at
- 源文件被修改 → 条目标记为 "源文件已更新"，提示用户重新确认
- 源文件被删除 → 条目保留（知识不因源消失而消失），source_link 变灰

**未分类区：**
- 在 DB 中 = `layer_id = null` 的 Entry，挂在 "未分类" UI 区域（画布底部或侧边独立区域）
- 用户拖拽到某层 → layer_id 赋值，从未分类区移除

---

## 第六节：诊断引擎

### 技术方案

诊断不是关键词搜索——它是 LLM 驱动的逐层知识审计。核心流程：

```
用户输入问题（如"我为什么焦虑"）
  → 系统收集当前 Dimension 下所有 Entry
  → 逐层调用 LLM（10 次推理，按 level 0→9）：
      每层 Prompt：
        "你是思维诊断助手。用户在思考「{问题}」。
         当前层级：{layer.name}（{layer.description}）
         用户在这一层已有的认知：
           - [已知条目列表]
           - [未知缺口列表]
           - [待解答问题列表]
         请诊断：
           1. 这一层跟「{问题}」有什么关系？
           2. 用户在这一层的认知中存在什么缺口？
           3. 建议用户在这一层补充什么知识或提出什么问题？
         输出格式：JSON { relation, gaps[], suggestions[], new_questions[] }"
  → 每层 LLM 结果立即推送到前端 → 画布上该层卡片高亮/新增建议条目
  → 全部 10 层完成后 → 聚合为"差距地图"
```

### Agent 架构（Pi + 7 层栈）

借用 Pi（@mariozechner/agent）的核心模式和 Agent范式.txt 的 7 层技术栈：

| 层 | Pi 对应 | 思考空间实现 |
|----|---------|-------------|
| 基础模型 | `Model` + `Transport` | OpenAI/Anthropic SDK，可切换 |
| 编排框架 | `AgentLoop` + `runAgentLoop` | 诊断专用循环：逐层调用 + 结果聚合 |
| 记忆系统 | `AgentState.messages` | 短期=当前诊断会话，长期=Entry 数据库 |
| 检索增强 | `transformContext` | 诊断前检索该层所有 Entry → 拼入 prompt |
| 工具层 | `AgentTool<T>` | Entry CRUD、索引扫描、导出报告 |
| 可观测性 | `AgentEvent` + `subscribe()` | 逐层事件→前端 SSE 推送 |
| 部署基础设施 | Pi `@earendil-works/pi-ai` | FastAPI + SQLite 本地部署 |

**关键设计决策：**
- Pi 是 TypeScript 项目，思考空间后端是 Python。不直接复用代码，但**借鉴架构模式**：Agent 状态机、事件驱动 streaming、工具执行并行/串行策略、steering/followUp 双队列
- 诊断 Agent 作为 FastAPI 的 `DiagnosisService`，内部管理 10 次 LLM 调用的状态机
- 前端通过 SSE（Server-Sent Events）接收逐层结果，实时更新画布

### 诊断输出结构

```json
{
  "question": "我为什么焦虑",
  "dimension": "物质层次",
  "created_at": "...",
  "layers": [
    {
      "level": 0,
      "name": "细胞",
      "relation": "焦虑的生理基础：皮质醇、肾上腺素在细胞层面的作用",
      "gaps": ["不了解神经递质的作用机制", "缺乏对压力激素的认知"],
      "suggestions": ["了解HPA轴", "学习呼吸法对自主神经的影响"],
      "new_questions": ["我的作息是否影响了激素周期？"],
      "existing_entries_highlighted": ["entry-uuid-1", "entry-uuid-2"],
      "new_suggested_entries": [
        {"title": "皮质醇与焦虑", "entry_type": "unknown", "content": "..."}
      ]
    }
    // ... 10 layers
  ],
  "gap_summary": "你的认知主要集中在 人/社会 两层，细胞/组织/器官 三层几乎是空白..."
}
```

---

## 第七节：API 契约（草图）

V1 端点，按优先级排列：

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| GET | `/api/dimensions` | 所有维度列表（含嵌套 layers） | P0 |
| GET | `/api/entries?dimension_id=&layer_id=&type=&status=&q=` | 筛选条目 | P0 |
| POST | `/api/entries` | 创建条目 | P0 |
| PUT | `/api/entries/:id` | 更新条目 | P0 |
| DELETE | `/api/entries/:id` | 删除条目 | P0 |
| POST | `/api/diagnose` | 发起诊断（body: `{question, dimension_id}`），返回 SSE 流 | P0 |
| GET | `/api/diagnose/:id` | 获取历史诊断记录 | P1 |
| POST | `/api/index/scan` | 触发文件扫描 | P1 |
| PUT | `/api/entries/:id/confirm` | 确认待确认条目 | P1 |
| PUT | `/api/entries/:id/ignore` | 忽略待确认条目 | P1 |
| POST | `/api/cross-links` | 创建连线 | P2 |
| DELETE | `/api/cross-links/:id` | 删除连线 | P2 |
| GET | `/api/export/gap-map?diagnose_id=` | 导出差距地图（markdown） | P2 |

**诊断端点（SSE）事件流：**
```
event: layer_start    data: {"level": 0, "name": "细胞"}
event: layer_complete data: {"level": 0, "name": "细胞", "relation": "...", "gaps": [...], ...}
event: layer_start    data: {"level": 1, "name": "组织"}
...
event: diagnose_end   data: {"diagnose_id": "...", "gap_summary": "..."}
event: error          data: {"level": 5, "message": "LLM 调用失败，正在重试..."}
```

---

## 设计审阅问题解决记录（2026-07-08）

| 问题 | 严重度 | 解决方案 |
|------|--------|----------|
| C1: 诊断引擎是黑箱 | Critical | 第六节：LLM 逐层推理 + Pi Agent 架构 + SSE streaming |
| C2: ZUI 对 AI 太难 | Critical | 接受风险，参考 Miro/Apple/Figma DESIGN.md，先做不行回滚 |
| C3: 索引生命周期未定义 | Critical | 第五节补充：pending→confirmed→ignored 状态流转、字段填充、去重、变更检测、未分类区 |
| I1: 诊断时序未定义 | Important | 第三节：10 次 LLM 调用，逐层即时推送，不等全部完成 |
| I2: Entry 缺少 status | Important | 第二节：新增 `status` 字段（pending/confirmed/ignored） |
| I3: 全景 vs 诊断冲突 | Important | 第三节：全景=底图，诊断=透镜，同一画布两种模式 |
| I4: CrossLink UI vs 零使用 | Important | 保留 V1 架构，UI 推迟到 P2（API 优先，UI 后补） |
| I5: API 契约缺失 | Important | 第七节：14 个端点 + SSE 事件流规范 |
| I6: 文件扫描安全 | Important | 明确：仅存路径+摘要，不存文件全文；SQLite 不入 git |
| M1-M7 | Minor | 置信度字段保留（移除 UI 引用）、Dock 动画推迟 V2、导出格式=markdown、扫描器 handle missing paths |

---

## 设计进度

大脑风暴 checklist：

1. ✅ 探索项目上下文（Crescent 前端结构、portfolio 布局）
2. ✅ 澄清问题（7 个问题，逐一确认）
3. ✅ 方案取舍（A 实现 / 数据模型多维 / 不出 B）
4. ✅ 出设计（8 节全部完成：架构、数据模型、交互流程、UI 结构、集成方案、诊断引擎、索引生命周期、API 契约）
5. ✅ 写设计文档（当前文件）
6. ✅ 设计审阅（2026-07-08，C1-C3 + I1-I6 已解决）
7. ⬜ 用户审阅
8. ⬜ 过渡到实施计划（writing-plans）

---

*从 portfolio 主对话（Crescent 重构会话）转移过来。设计灵感参考：Miro DESIGN.md（无限画布+便签卡片）、Apple DESIGN.md（UI 退让+单强调色）、Figma DESIGN.md（色块打断+黑白框架）。*
