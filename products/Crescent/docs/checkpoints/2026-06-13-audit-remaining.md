# Checkpoint — 审计修复后剩余事项 (2026-06-13)

## 当前状态

M1-M6 评估元模块已交付。175 tests passed (7 个批量运行顺序依赖失败，单跑全绿)。
审计 11 个差异全部修复。

## 已修复 (2026-06-13 session)

| # | 严重度 | 问题 | 修复方式 |
|---|--------|------|----------|
| P1-6 | 功能缺失 | `_ingest_review_findings()` | 新增函数消费 events.jsonl 中的 review_agent.finding 事件，P0/P1 自动创建建议，描述去重 + 时间窗口过滤 + 防崩盖。已接入 daemon 循环 (每小时)。5 tests |
| P2-7 | 外观 | 概念提示范围太窄 | 新增 `withConceptTooltips()` 公共函数，应用于 L2 建议、L3 计算说明/决策问题、探测卡描述、建议条目标题、Slideout 描述。先 escapeHtml 再替换，防 XSS |
| P2-8 | 安全 | 两个检测器缺超时 | `_check_kb_application_gap`: 文件扫描循环 + trace 扫描循环各加 timeout 检查；`_check_error_recurrence`: list_reviews 调用前 + review 迭代循环各加 timeout 检查 |
| P2-9 | 硬编码 | uncovered_count 恒为 0 | 新增 `_compute_uncovered_count()` 从 DEFAULT_SCORE_CONFIGS 与决策面 YAML 动态计算。API coverage 端点同时补齐未覆盖模块到 module_list |

## 验证

```
python -m pytest tests/test_eval_engine.py tests/test_eval_core.py -q
175 passed, 7 failed (7个为既有的批量运行顺序依赖，单跑全绿)

python -c "from server import create_app; app = create_app()"  # OK
```

commit: 949fb53

## 后续大方向

1. **评估系统打磨** → 修完 P1-6 + P2 剩余项
2. **现有模块优化** → portfolio-app 前端重构 (impeccable + frontend-design skill 已就绪) → cv-lab → electron → 知识库
3. **新功能** → 待上述完成后按评估数据决定
