# Phase A: 日志驱动反思回路 — 设计文档

> 2026-06-08 | 自进化系统第一层地基
> 目标：让系统拥有"看见自己"的能力——定期审视运行日志和历史文档，发现模式，产出改进建议

---

## 一、定位

Phase A 是 A→B→C 三层自进化路线的基础层：

```
Phase A (本设计)   → 日志反思回路      → "看见自己"
Phase B (后续)     → Skill 策展系统     → "能力可量化可优化"
Phase C (远期)     → Continual Harness  → "自动闭环自改进"
```

Phase A 不涉及 Skill 自动创建（B）或多 Agent 自博弈（C），只做一件事：**把散落的日志和历史文档串起来，让 LLM 定期审视、发现模式、产出建议。**

---

## 二、四层记忆模型

日志像人脑记忆——越近越清晰，越远越凝练，但从不可删除。

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Hot (原始) │ → │Warm (周摘要)│ → │Cold (结晶) │ → │  Archive  │
│ 最近10会话 │    │ 每周浓缩  │    │ 每月固化  │    │ 永久存储  │
│ ~5K/次    │    │ ~2K/周    │    │ ~500/月   │    │ 按需检索  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
  在上下文里                                    不在上下文里
                                                 ChromaDB 存储
                                                 RAG 唤醒
```

### 2.1 Hot — 原始日志
- 最近 10 次会话的完整结构化日志
- 不压缩，保持细节
- 来源：agent_logger、token_tracker、harness、_SESSION_HISTORY

### 2.2 Warm — 周摘要
- 触发：Hot >10 条时，最旧 5 条浓缩
- 内容：错误模式 + 改进效果 + 关键指标变化
- LLM 生成，~2K tokens/周

### 2.3 Cold — 知识结晶
- 触发：Warm >4 周时合并
- 内容：已验证的方法论 + 永久规则 + 可写入 CLAUDE.md 的候选
- LLM 生成，~500 tokens/月

### 2.4 Archive — 外部归档
- 触发：Cold 中规则连续 4 周未触发，或方案被回滚
- 存储：ChromaDB，metadata 含来源/时间/状态/关键词
- 唤醒：ReviewAgent 发现当前问题与归档条目相似时，RAG 检索
- 核心原则：**压缩≠删除，只是移出活跃上下文**

---

## 三、日志源：双层模型

### 3.1 运行时日志（结构化）
| 源 | 内容 |
|----|------|
| `agent_logger` | 会话决策链、工具调用、异常 |
| `token_tracker` | 按任务类型的 token 消耗 |
| `harness` | 校验通过/拦截/警告 |
| `_SESSION_HISTORY` | 会话级对话摘要 |

### 3.2 文档积累（非结构化 → 索引化）
| 源 | 内容 |
|----|------|
| `知识库/错误与修正与优化/` | 历史踩坑记录、修复方案 |
| `知识库/参考/审查清单.md` | 6 大类完成前门禁 |
| `portfolio-app/docs/checkpoints/` | 每阶段完成/未完成事项 |
| `知识库/论文索引.md` | 可借鉴的外部方法论 |

文档通过 `doc_indexer` 做轻量结构化提取（error_type、occurred_date、fix_status），不是全文嵌入。

### 3.3 交叉分析
ReviewAgent 同时查询运行时日志和文档索引，做交叉比对：

> "僵尸进程在 6/8 通过 restart.sh 修复（来源：错误文档），但 6/10 agent_logger 再次记录端口占用 → 修复未生效，建议加自动化检测"

---

## 四、ReviewAgent 设计

### 4.1 分析维度
| 维度 | 检查内容 | 严重性 |
|------|----------|--------|
| 错误重复 | 同一类错误出现 >1 次？上次修复是否生效？ | P0 |
| Token 异常 | 哪类任务消耗最高？是否有浪费模式？ | P1 |
| 改进机会 | Harness 拦截了什么？用户纠正是否可自动化？ | P2 |
| 自指 | ReviewAgent 自己是否超预算？需要调高压缩率？ | 内部 |

### 4.2 Token 预算
```
单次分析输入:  ≤ 18,000 tokens
周沉淀输出:    ≤ 12,000 tokens
月结晶输出:    ≤ 5,000 tokens
```

超预算时自动缩减上下文窗口，优先保留 Hot 层 + 最新 Cold 层。

### 4.3 触发方式
- **自动**: 每 10 次会话后，或每周一次
- **手动**: `POST /api/review/run`
- **启动时**: server.py 启动时检查是否有未处理的 P0 建议

---

## 五、Git 式回滚机制

不纠结"哪些该自动批哪些不该批"。**全自动执行，每步可逆。**

### 5.1 修改流程
```
1. 改前快照 → 备份目标文件
2. 执行修改 → 记录预期效果
3. 效果评估 → N次会话后比对指标
4. 回滚/确认 → 无效自动回滚，有效标记 confirmed
```

### 5.2 回滚触发条件
| 条件 | 动作 |
|------|------|
| 同类型错误 3 次内复现 | 自动回滚 + 标记 fix_failed |
| 修改导致新类型错误 | 自动回滚 + 关联记录因果 |
| Token 消耗 >修改前 1.5x | 警告 + 建议回滚 |
| 连续 10 次会话无复现 | 标记 confirmed → 候选进 Cold 结晶 |

### 5.3 回滚后的经验保留
被回滚的方案不丢弃，存入 Archive，标注 fix_failed，防止日后重复尝试同类方案。

---

## 六、文件变更清单

### 新建
| 文件 | 职责 |
|------|------|
| `services/review_agent.py` | ReviewAgent 核心：日志聚合、LLM 分析、建议生成、回滚管理 |
| `services/review_store.py` | 审查记录存取 (JSON)，变更历史追踪，按 paper_index 模式 |
| `services/doc_indexer.py` | 文档轻量索引（错误文档/审查清单/checkpoints → 结构化提取） |
| `prompts/review_agent.txt` | ReviewAgent 的 system prompt |
| `routes/api_review.py` | 6 个 REST 端点（见下方 API 设计） |

### 改造
| 文件 | 变更 |
|------|------|
| `services/agent_logger.py` | 增加结构化事件日志：错误类型、恢复策略、是否复现 |
| `services/token_tracker.py` | 增加按任务类型的消耗统计 |
| `server.py` | 注册 review_bp，启动时检查未处理 P0 建议 |

---

## 七、API 设计

```
POST   /api/review/run          — 手动触发审查
GET    /api/review/list         — 查看历史审查记录
GET    /api/review/<id>         — 单次审查详情
POST   /api/review/<id>/apply   — 批准并应用建议
POST   /api/review/<id>/reject  — 拒绝建议（含原因）
POST   /api/review/<id>/rollback — 回滚已应用的修改
GET    /api/review/stats        — 审查统计（建议数/应用数/回滚数/有效率）
```

---

## 八、自指闭环

> ReviewAgent 不仅审查业务日志，也审查自己的运行数据。

- 连续 3 次单次分析超 18K tokens → 自动调高压缩率
- 建议被回滚率 >50% → 降低该维度的分析权重
- Archive 中 fix_failed 条目被反复检索 → 标记为"待突破难题"

这对应 Harness Engineering 中的"自指循环"——在 Phase A 第一次变成可运行的代码。

---

## 九、成功标准

1. ReviewAgent 能产出至少 1 条/周的有效改进建议
2. 回滚率在运行 2 周后 <30%
3. 单次分析 token 消耗稳定在 18K 以内
4. Archive 中有条目能在后续会话中被 RAG 唤醒
5. 人工可随时查看、批准、拒绝、回滚任何建议

---

## 十、不在此范围内

- Skill 自动创建/评估/淘汰（→ Phase B）
- 多 Agent 自博弈循环（→ Phase C）
- 前端仪表板展示审查历史（后续 UI 迭代）
- 跨项目/跨仓库经验迁移（远期）
