# Stage 2: 信息免疫系统原型

> 2026-06-06 | 基于 Phase 1 Spec 双核架构

## 概要

实现信息免疫系统 L1：来源追溯。用户粘贴内容/链接 → Agent 驱动 6 步搜索管道 → SSE 流式展示 → 所有来源可点击验证。

## 后端

### `services/source_tracer.py` — 6 步固定管道

1. `extract_keywords(content)` — LLM 提取搜索关键词
2. `multi_search(keywords)` — Scrapling 多平台搜索
3. `extract_content(urls)` — markitdown 提取正文
4. `timeline_backtrack(results)` — 时间线回溯
5. `diff_annotate(original, user_version)` — LLM 逐句差异对比
6. `final_conclusion(chain)` — 阶段性结论 + 确定/不确定边界

### `POST /api/source-trace` — SSE 流式

每完成一步推 `{step, type, content}` 事件。

## 前端

### `/source-trace` 新页面
- 输入区：粘贴文本/URL
- 6 张可展开卡片，SSE 事件逐步填充和点亮
- 来源链接可点击

### 主动提醒（纯前端）
- localStorage 记录上次访问时间
- 超过 N 天未打开则在仪表盘显示轻提示

## 不做的
- 浏览器插件/被动监控
- L2 情绪检测 / L3 事实校验
- 自动内容过滤
