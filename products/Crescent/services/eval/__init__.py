"""
eval — 项目评估系统

三条强制逻辑链:
  链1 (行为→数据): trace_logger 强制性核心埋点 ✅ Phase 1
  链2 (数据→行动): eval_engine 评分 + 因果闭环 ✅ Phase 2
  链3 (行动→进化): meta_evaluator 元评估 + 动态标准 (Phase 4)

模块:
  - trace_logger: Trace/Span 埋点，防崩盖，影子模式
  - eval_store: 数据存储层 (JSONL+JSON)，Trace/Span/Suggestion 查询
  - eval_engine: 因果循环引擎，孤儿清理，效果追踪，数据完整度
"""
