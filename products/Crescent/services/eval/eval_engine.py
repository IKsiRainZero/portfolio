"""
eval_engine — 链2 因果循环引擎

职责:
  - 孤儿 Span 清理 (_cleanup_orphan_spans)
  - 数据完整度计算 (_compute_data_completeness) — 宪法 Metric
  - 效果追踪循环 (_effect_tracking_loop)
  - 优先级违规检查 (_check_priority_violation)
  - 评分聚合查询 (_aggregation_query)

设计保证:
  - 所有后台任务 TraceContext 包裹，自追踪
  - 防崩盖: 所有函数吞异常，绝不阻断调用方
  - 红线违规触发审查，但限制频率（1小时内不重复）
"""
from __future__ import annotations
import time
import json
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path

from services.eval import eval_store
from services.eval.trace_logger import (
    _read_jsonl, _generate_id, TraceContext, emit_event,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "eval"
HEARTBEAT_FILE = DATA_DIR / "heartbeat.json"

# ── 上一次红线触发审查的时间戳 (防风暴) ──
_last_review_triggered_at = 0.0

# ── Trace 类型 → 必需的 Span 种类 ──
#   来源: trace_logger._safe_record_llm_span() 写 kind="LLM"
#         TraceContext / agent_service 写 kind="TOOL" (含检索器调用)
#   ⚠️  修改前先 grep span kind 实际值，勿从计划文档复制常量名
TRACE_TYPE_SPAN_REQUIREMENTS = {
    "agent_chat": ["LLM", "TOOL"],
    "rag_query":  ["LLM", "TOOL"],
}


def _classify_trace_type(trace):
    """从 trace name/kind 推断逻辑类型"""
    name = trace.get("name", "")
    kind = trace.get("kind", "")
    if "/agent" in name or "/api/agent" in name:
        return "agent_chat"
    if "/knowledge" in name or "/api/knowledge" in name:
        return "rag_query"
    if "/api/ai" in name:
        return "agent_chat"
    if kind == "http_request":
        return "http_request"
    if kind == "system_task":
        return "system_task"
    return "http_request"


def _get_trace_spans(trace_id):
    """获取某个 Trace 的所有 Span"""
    rows = _read_jsonl("traces.jsonl")
    spans = []
    for r in rows:
        if r.get("trace_id") == trace_id and "span_id" in r:
            spans.append(r)
    return spans


# ══════════════════════════════════════════════
# 孤儿 Span 清理
# ══════════════════════════════════════════════

def _cleanup_orphan_spans():
    """每小时扫描孤儿 Span，时间窗口重关联，超1h标记确认。"""
    try:
        orphans = eval_store.list_orphan_spans(hours=24)
    except Exception:
        return {"scanned": 0, "reattached": 0, "confirmed": 0}

    stats = {"scanned": len(orphans), "reattached": 0, "confirmed": 0, "error_count": 0}
    now_ts = datetime.now().isoformat()

    for span in orphans:
        if span.get("orphan_confirmed"):
            continue
        if span.get("status") == "error":
            stats["error_count"] += 1
        try:
            matched = eval_store.find_trace_by_window(
                span["timestamp"], window_seconds=5,
            )
            if matched:
                eval_store.attach_span_to_trace(
                    span["span_id"], matched["trace_id"],
                )
                stats["reattached"] += 1
            else:
                # 超过 1 小时的孤儿，确认不可修复
                try:
                    span_time = datetime.fromisoformat(span["timestamp"])
                    age_hours = (datetime.now() - span_time).total_seconds() / 3600
                except Exception:
                    age_hours = 0
                if age_hours > 1:
                    eval_store.mark_orphan_confirmed(span["span_id"])
                    stats["confirmed"] += 1
        except Exception:
            logger.warning("eval_engine: orphan cleanup failed for span", exc_info=True)

    return stats


# ══════════════════════════════════════════════
# 孤儿 Span 错误率健康检查 (P2)
# ══════════════════════════════════════════════

def _orphan_error_health_check(window_hours=24):
    """
    检查孤儿 Span 中错误占比，作为"丢失的故障信号"指标。
    如果大量孤儿 Span 携带 error，说明系统存在 trace 断裂导致
    故障信号未被正确归因。
    """
    try:
        orphans = eval_store.list_orphan_spans(hours=window_hours)
    except Exception:
        return None

    total = len(orphans)
    if total == 0:
        return None  # 冷启动保护

    error_count = sum(1 for s in orphans if s.get("status") == "error")
    ratio = error_count / total

    score = {
        "score_id": _generate_id(),
        "config_id": "orphan_error_rate",
        "target_type": "system",
        "target_id": "eval_system",
        "value": round(ratio, 4),
        "details": {
            "total_orphans": total,
            "error_orphans": error_count,
            "window_hours": window_hours,
            "note": "孤儿 Span 中 error 占比。越低越好，高值表示故障信号在丢失。",
        },
        "created_at": datetime.now().isoformat(),
        "source": "CODE",
    }
    eval_store.save_score(score)
    return score


# ══════════════════════════════════════════════
# 数据完整度 (宪法 Metric, Priority 0)
# ══════════════════════════════════════════════

def _compute_data_completeness(window_hours=24):
    """
    检查核心 Trace 类型是否包含必需的 Span。
    评分: 完整 Trace 数 / 适用 Trace 总数。
    <5 个适用 Trace 时跳过（冷启动保护）。
    """
    try:
        traces = eval_store._query_traces(window_hours=window_hours, limit=500)
    except Exception:
        return None

    by_type = {}
    applicable_total = 0
    complete_total = 0

    for trace in traces:
        ttype = _classify_trace_type(trace)
        if ttype not in TRACE_TYPE_SPAN_REQUIREMENTS:
            continue

        applicable_total += 1
        spans = _get_trace_spans(trace["trace_id"])
        span_kinds = {s.get("kind", "") for s in spans}
        required = set(TRACE_TYPE_SPAN_REQUIREMENTS[ttype])
        is_complete = required.issubset(span_kinds)

        key = ttype
        if key not in by_type:
            by_type[key] = {"total": 0, "complete": 0}
        by_type[key]["total"] += 1
        if is_complete:
            by_type[key]["complete"] += 1
            complete_total += 1

    if applicable_total < 5:
        return None  # 冷启动保护

    score_value = complete_total / applicable_total

    score = {
        "score_id": _generate_id(),
        "config_id": "data_completeness",
        "target_type": "system",
        "target_id": "eval_system",
        "value": round(score_value, 4),
        "details": {
            "applicable_traces": applicable_total,
            "complete_traces": complete_total,
            "by_type": by_type,
            "window_hours": window_hours,
            "required_spans": TRACE_TYPE_SPAN_REQUIREMENTS,
        },
        "created_at": datetime.now().isoformat(),
        "source": "CODE",
    }
    eval_store.save_score(score)
    return score


# ══════════════════════════════════════════════
# 数据完整度交叉验证 (P1)
# ══════════════════════════════════════════════

def _cross_validate_data_completeness(sample_size=5):
    """
    从最近24h的适用 Trace 中随机采样，生成 LLM 交叉验证请求。
    不自动调用 LLM（避免费用），保存为 CROSSVAL_PENDING 评分。
    Phase 3 接入 LLM Judge 后可直接消费这些待处理条目。
    """
    try:
        traces = eval_store._query_traces(window_hours=24, limit=500)
    except Exception:
        return None

    applicable = []

    for trace in traces:
        ttype = _classify_trace_type(trace)
        if ttype not in TRACE_TYPE_SPAN_REQUIREMENTS:
            continue
        applicable.append(trace)

    if len(applicable) < sample_size:
        return None  # 冷启动保护

    sample = random.sample(applicable, min(sample_size, len(applicable)))
    crossval_items = []

    for trace in sample:
        spans = _get_trace_spans(trace["trace_id"])
        span_kinds = sorted({s.get("kind", "") for s in spans})
        required = sorted(TRACE_TYPE_SPAN_REQUIREMENTS[_classify_trace_type(trace)])

        item = {
            "crossval_id": _generate_id(),
            "trace_id": trace["trace_id"],
            "trace_name": trace.get("name", ""),
            "trace_type": _classify_trace_type(trace),
            "span_kinds_present": span_kinds,
            "span_kinds_required": required,
            "code_judgment": "complete" if set(required).issubset(set(span_kinds)) else "incomplete",
            "llm_prompt": (
                f"Trace: {trace.get('name')} (type={trace.get('kind')})\n"
                f"Spans found: {', '.join(span_kinds) if span_kinds else '(none)'}\n"
                f"Required spans for {_classify_trace_type(trace)}: {', '.join(required)}\n"
                f"Based on the span coverage above, is this trace data-complete? Answer YES/NO."
            ),
            "llm_judgment": None,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }
        crossval_items.append(item)

    score = {
        "score_id": _generate_id(),
        "config_id": "data_completeness_crossval",
        "target_type": "system",
        "target_id": "eval_system",
        "value": -1.0,  # placeholder: LLM 判定前无有效值
        "details": {
            "sample_size": len(sample),
            "items": crossval_items,
            "window_hours": 24,
            "note": "LLM cross-validation pending — POST /api/eval/cross-validate/run to execute",
        },
        "created_at": datetime.now().isoformat(),
        "source": "CROSSVAL_PENDING",
    }
    eval_store.save_score(score)
    return score


# ══════════════════════════════════════════════
# 优先级违规检查
# ══════════════════════════════════════════════

def _check_priority_violation(suggestion, delta_details):
    """
    硬编码逻辑: 优先级 1-2 的指标出现负 delta → 标记为违规。
    LLM 不可判断此逻辑。

    delta_details: {metric_key: delta_value, ...}
    返回: {"violated": bool, "violations": [{"metric": ..., "priority": ..., "delta": ...}]}
    """
    try:
        import config
    except Exception:
        return {"violated": False, "violations": []}

    priority_map = getattr(config, "METRIC_PRIORITY", {})
    violations = []

    for metric_key, delta in (delta_details or {}).items():
        priority = priority_map.get(metric_key, 99)
        if priority <= 2 and delta < 0:
            violations.append({
                "metric": metric_key,
                "priority": priority,
                "delta": round(delta, 4),
            })

    return {"violated": len(violations) > 0, "violations": violations}


# ══════════════════════════════════════════════
# 效果追踪循环
# ══════════════════════════════════════════════

def _effect_tracking_loop():
    """
    每小时检查已应用 >24h 未验证效果的建议。
    对比基线 vs 当前评分，检测 git 冲突，运行优先级检查。
    返回: {"checked": N, "attributed": M, "violations": K, "conflicts": C}
    """
    try:
        suggestions = eval_store._find_applied_unverified_suggestions(min_hours=24)
    except Exception:
        return {"checked": 0, "attributed": 0, "violations": 0, "conflicts": 0}

    stats = {
        "checked": len(suggestions),
        "attributed": 0,
        "violations": 0,
        "conflicts": 0,
    }

    for sug in suggestions:
        sid = sug.get("suggestion_id")
        baseline = sug.get("baseline_scores", {})
        if not baseline:
            continue

        # 计算每个子指标的 delta
        delta_details = {}
        for metric_key, baseline_info in baseline.items():
            baseline_val = baseline_info.get("value") if isinstance(baseline_info, dict) else baseline_info
            try:
                parts = metric_key.split(".", 1)
                config_id = parts[0]
                sub_key = parts[1] if len(parts) > 1 else None
                current = eval_store.get_latest_sub_score(
                    sug.get("target_type", "module"),
                    sug.get("target_id", ""),
                    config_id,
                    sub_key=sub_key,
                )
                current_val = current["value"] if current else None
                if current_val is not None and baseline_val is not None:
                    delta_details[metric_key] = current_val - baseline_val
            except Exception:
                logger.warning("eval_engine: delta calc failed for %s", metric_key, exc_info=True)

        if not delta_details:
            continue

        # Git 冲突检测
        has_conflict = False
        try:
            target_file = sug.get("target_file")
            applied_commit = sug.get("applied_commit")
            if target_file and applied_commit:
                other_commits = eval_store._git_commits_touching_file(target_file, applied_commit)
                if other_commits:
                    has_conflict = True
                    stats["conflicts"] += 1
        except Exception:
            pass

        # 归因判定
        if has_conflict:
            attribution = "conflict"
            note = "同一文件在建议采纳后被其他提交修改，无法归因"
        else:
            violation = _check_priority_violation(sug, delta_details)
            if violation["violated"]:
                attribution = "likely_failed"
                note = f"优先级违规: {violation['violations']}"
                stats["violations"] += 1
                _trigger_review_on_violation(sug, violation)
            else:
                avg_delta = sum(delta_details.values()) / len(delta_details)
                if avg_delta >= 0:
                    attribution = "attributed"
                    note = f"效果确认: 平均 delta = {avg_delta:+.4f}"
                else:
                    attribution = "attributed_mixed"
                    note = f"部分指标下降: 平均 delta = {avg_delta:+.4f}"

        avg_delta = sum(delta_details.values()) / len(delta_details) if delta_details else 0
        try:
            eval_store.update_suggestion_effect(
                sid,
                effect_score_delta=round(avg_delta, 4),
                attribution_status=attribution,
                attribution_note=note,
                delta_details=delta_details,
            )
            stats["attributed"] += 1
        except Exception:
            logger.warning("eval_engine: effect update failed for %s", sid, exc_info=True)

    return stats


# ══════════════════════════════════════════════
# 评分聚合查询
# ══════════════════════════════════════════════

def _aggregation_query(config_id=None, target_type=None, target_id=None, limit=100):
    """评分查询入口。始终排除空 Trace 和已确认孤儿 Span。"""
    return eval_store.query_scores(
        config_id=config_id,
        target_type=target_type,
        target_id=target_id,
        exclude_empty_traces=True,
        exclude_orphan_spans=True,
        limit=limit,
    )


# ══════════════════════════════════════════════
# 后台守护心跳
# ══════════════════════════════════════════════

def _daemon_heartbeat(cycle_stats=None):
    """每次后台循环完成时写入心跳时间戳。供 _build_alerts 检测守护线程存活。"""
    try:
        heartbeat = {
            "last_heartbeat": datetime.now().isoformat(),
            "cycle_stats": cycle_stats or {},
        }
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
            json.dump(heartbeat, f)
    except Exception:
        pass


def _check_heartbeat_stale():
    """检查守护心跳是否 > 2h 未更新。返回 (stale: bool, last_beat: str|None)。"""
    try:
        if not HEARTBEAT_FILE.exists():
            return True, None
        with open(HEARTBEAT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        last = data.get("last_heartbeat")
        if not last:
            return True, None
        last_dt = datetime.fromisoformat(last)
        stale = (datetime.now() - last_dt).total_seconds() > 7200
        return stale, last
    except Exception:
        return True, None


# ══════════════════════════════════════════════
# 红线违规 → 触发审查 (防风暴)
# ══════════════════════════════════════════════

def _trigger_review_on_violation(suggestion, violation):
    """红线违规时触发审查。1小时防风暴 + 影子模式纵深守卫。"""
    # 纵深防御第1层: 影子模式下不触发真实审查
    try:
        import config
        if not getattr(config, "EVAL_ENABLED", False) or getattr(config, "EVAL_SHADOW_MODE", True):
            return None
    except Exception:
        return None

    # 纵深防御第2层: 1小时防风暴
    global _last_review_triggered_at
    now = time.time()
    if now - _last_review_triggered_at < 3600:
        return None

    _last_review_triggered_at = now
    try:
        from services.review_agent import run_review
        with TraceContext(
            name="eval_triggered_review",
            kind="scheduled_task",
            metadata={
                "trigger": "red_line_violation",
                "suggestion_id": suggestion.get("suggestion_id"),
                "violations": violation.get("violations", []),
            },
        ):
            result = run_review()
            return result
    except Exception:
        logger.error("eval_engine: review trigger failed", exc_info=True)
        return None


# ══════════════════════════════════════════════
# ScoreConfig 初始化
#   来源: 每个 config_id 被以下位置引用:
#     - eval_store.SUGGESTION_CATEGORY_SUB_METRICS (category→config_id 映射)
#     - _compute_data_completeness / _orphan_error_health_check 等评分函数
#     - API 查询 (routes/api_eval.py) 按 config_id 过滤
#   ⚠️  增删 config 时同步检查上述引用点
# ══════════════════════════════════════════════

DEFAULT_SCORE_CONFIGS = [
    {
        "config_id": "data_completeness",
        "name": "数据采集完整度",
        "display_name": "数据完整度",
        "evaluator_type": "CODE",
        "chain": "chain1",
        "constitutional": True,
        "priority": 0,
        "weight": 0.0,
        "threshold": 0.9,
        "direction": "above",
        "computation": "count(complete_traces) / count(applicable_traces)，≥5 条适用 Trace 时触发，<5 条时跳过（冷启动保护）",
        "sub_indicators": [
            {"name": "agent_chat spans", "value": 0.85},
            {"name": "rag_query spans", "value": 0.92},
            {"name": "tool spans", "value": 0.78},
        ],
        "decision_question": "缺少的 span 类型是否集中在一个业务模块？如果是，为该模块增加埋点。",
        "user_value_statement": (
            "核心埋点数据覆盖所有关键路径，系统没有可观测性盲区——"
            "每一次用户请求、每一次LLM调用、每一次工具执行都被准确记录，"
            "任何数据丢失都能在1小时内发现并定位。"
        ),
    },
    {
        "config_id": "eval_system_freshness",
        "name": "评估体系新鲜度",
        "evaluator_type": "LLM_JUDGE",
        "chain": "chain3",
        "constitutional": True,
        "priority": 0,
        "weight": 0.0,
        "threshold": 0.7,
        "direction": "above",
        "user_value_statement": (
            "评估系统的指标配置定期接受审查和更新，过时的指标被及时废弃——"
            "系统始终用最相关的标准评估自身，而非用过时的标准自欺欺人。"
        ),
    },
    {
        "config_id": "security_score",
        "name": "安全合规评分",
        "display_name": "安全合规",
        "evaluator_type": "CODE",
        "chain": "chain2",
        "priority": 1,
        "weight": 0.25,
        "threshold": 0.7,
        "direction": "above",
        "computation": "sub_indicators 加权平均: 0.35×鉴权覆盖 + 0.35×输入校验 + 0.30×审计日志",
        "sub_indicators": [
            {"name": "API 鉴权覆盖", "value": 0.95},
            {"name": "输入校验", "value": 0.88},
            {"name": "审计日志", "value": 0.82},
        ],
        "decision_question": "安全评分下降时：是新增端点未鉴权，还是现有校验规则被绕过？",
        "user_value_statement": (
            "每次安全评分提升10%意味着：用户数据被SSRF/端口扫描/命令注入"
            "等常见攻击向量攻击的风险显著降低，项目的安全审计通过率提高。"
        ),
    },
    {
        "config_id": "agent_success_rate",
        "name": "Agent 任务成功率",
        "display_name": "任务成功率",
        "evaluator_type": "LLM_JUDGE",
        "chain": "chain2",
        "priority": 2,
        "weight": 0.20,
        "threshold": 0.5,
        "direction": "above",
        "computation": "LLM Judge 评分: 判断 Agent 最终回答是否满足用户意图（0=完全失败, 1=完全成功）",
        "user_value_statement": (
            "Agent成功率每提升10%意味着：用户用自然语言下达的10个任务中"
            "多出1个可以一次性成功完成，无需手动干预或重试。"
        ),
    },
    {
        "config_id": "agent_efficiency",
        "name": "Agent Token 效率",
        "display_name": "Token 效率",
        "evaluator_type": "CODE",
        "chain": "chain2",
        "priority": 3,
        "weight": 0.15,
        "computation": "1 − (wasted_tokens / total_tokens)，其中 wasted_tokens = 重试消耗 + 无效工具调用消耗",
        "user_value_statement": (
            "Token效率每提升10%意味着：同样的任务消耗更少的API调用费用，"
            "用户等待响应的时间更短，同时保持相同的任务完成质量。"
        ),
    },
    {
        "config_id": "agent_tool_accuracy",
        "name": "Agent 工具选择准确度",
        "display_name": "工具准确度",
        "evaluator_type": "HYBRID",
        "chain": "chain2",
        "priority": 3,
        "weight": 0.15,
        "computation": "correct_tool_calls / total_tool_calls，每轮 ReAct 循环的工具调用由 LLM Judge 判定正确性",
        "user_value_statement": (
            "工具选择准确度每提升10%意味着：Agent在需要调用外部工具时"
            "更少犯'用错工具'的错误，减少无效的工具调用往返。"
        ),
    },
    {
        "config_id": "code_health",
        "name": "代码健康度",
        "display_name": "代码健康",
        "evaluator_type": "CODE",
        "chain": "chain2",
        "priority": 4,
        "weight": 0.10,
        "computation": "静态分析聚合: (测试覆盖率得分 + lint 通过率 + 复杂度评分) / 3",
        "user_value_statement": (
            "代码健康度每提升10%意味着：新功能开发时的认知负担更低，"
            "Bug修复时间更短，代码审查时发现的问题更少。"
        ),
    },
    {
        "config_id": "doc_coverage",
        "name": "文档覆盖度",
        "display_name": "文档覆盖",
        "evaluator_type": "CODE",
        "chain": "chain2",
        "priority": 4,
        "weight": 0.10,
        "computation": "count(documented_endpoints) / count(total_endpoints) × 0.5 + count(documented_modules) / count(total_modules) × 0.5",
        "user_value_statement": (
            "文档覆盖度每提升10%意味着：新成员上手项目的时间减少，"
            "API使用时出现的困惑和误用减少，设计决策的可追溯性提高。"
        ),
    },
    {
        "config_id": "data_completeness_crossval",
        "name": "数据完整度交叉验证",
        "evaluator_type": "HYBRID",
        "chain": "chain3",
        "constitutional": False,
        "priority": 1,
        "weight": 0.0,
        "threshold": 0.85,
        "direction": "above",
        "user_value_statement": (
            "CODE评分的正确性由LLM独立交叉验证——"
            "当自动评分与人工判断出现系统性偏差时能被及时发现和纠正，"
            "防止评分逻辑的静默退化。"
        ),
    },
    {
        "config_id": "code_llm_consensus",
        "name": "CODE vs LLM 一致性",
        "evaluator_type": "CODE",
        "chain": "chain3",
        "constitutional": True,
        "priority": 0,
        "weight": 0.0,
        "threshold": 0.8,
        "direction": "above",
        "user_value_statement": (
            "CODE 评分判定与 LLM Judge 独立判定高度一致——"
            "当自动评分与人工判断出现系统性偏差时能被及时发现，"
            "防止评分逻辑的静默退化。"
        ),
    },
    {
        "config_id": "score_drift",
        "name": "评分漂移检测",
        "evaluator_type": "CODE",
        "chain": "chain3",
        "constitutional": True,
        "priority": 0,
        "weight": 0.0,
        "threshold": 0.9,
        "direction": "above",
        "user_value_statement": (
            "所有指标评分保持稳定或上升——"
            "连续7天下降的指标被自动检测和告警，"
            "评估系统不会在无人察觉的情况下持续退化。"
        ),
    },
    {
        "config_id": "document_integrity",
        "name": "文档完整性",
        "evaluator_type": "CODE",
        "chain": "chain3",
        "constitutional": False,
        "priority": 1,
        "weight": 0.0,
        "threshold": 0.8,
        "direction": "above",
        "user_value_statement": (
            "关键文档的所有修改均经过版本化——"
            "非版本化覆写被自动检测，"
            "文档变更历史完整可追溯。"
        ),
    },
    {
        "config_id": "kb_protection_coverage",
        "name": "知识库防护覆盖率",
        "evaluator_type": "CODE",
        "chain": "chain3",
        "constitutional": False,
        "priority": 2,
        "weight": 0.0,
        "threshold": 0.7,
        "direction": "above",
        "user_value_statement": (
            "知识库中记录的每个错误都有对应的系统防护措施——"
            "犯过的错误不会因为遗忘而再次发生。"
        ),
    },
    {
        "config_id": "eval_process_adherence",
        "name": "Phase 1-3 过程合规",
        "evaluator_type": "CODE",
        "chain": "chain3",
        "constitutional": True,
        "priority": 0,
        "weight": 0.0,
        "threshold": 0.8,
        "direction": "above",
        "user_value_statement": (
            "Phase 1-3 确定的设计原则在后续执行中被严格遵守——"
            "30秒信任法则、零信任鉴权、20英里行军、文档版本纪律"
            "不是写在计划里的空话，而是在代码中可验证的实践。"
        ),
    },
    {
        "config_id": "orphan_error_rate",
        "name": "孤儿Span错误率",
        "display_name": "Span 健康",
        "evaluator_type": "CODE",
        "chain": "chain2",
        "priority": 2,
        "weight": 0.10,
        "threshold": 0.1,
        "direction": "below",
        "computation": "count(error_orphan_spans) / count(total_orphan_spans)，高于 0.1 时扣分（方向=below，越低越好）",
        "user_value_statement": (
            "孤儿Span中的错误占比每降低10%意味着："
            "被丢失的故障信号更少，异常检测的盲区更小，"
            "因trace断裂而未被归因的生产问题能在1小时内定位。"
        ),
    },
    {
        "config_id": "knowledge_health",
        "name": "知识管线健康度",
        "display_name": "知识管线",
        "evaluator_type": "CODE",
        "chain": "chain1",
        "priority": 2,
        "weight": 0.05,
        "threshold": 0.7,
        "direction": "above",
        "computation": "max(0, 1 − pending_items / max(total_items, 1))，无知识条目时 = 0.5（neutral），同步异常时 = 0（critical）",
        "user_value_statement": (
            "知识库与ChromaDB保持同步，无孤岛标签——"
            "知识管线健康度每提升10%意味着RAG检索结果更准确，"
            "知识库同步延迟更短，未被索引的新知识更少。"
        ),
    },
    {
        "config_id": "error_pattern_match",
        "name": "错误模式匹配",
        "evaluator_type": "CODE",
        "chain": "chain2",
        "priority": 2,
        "weight": 0.05,
        "threshold": 0.8,
        "direction": "above",
        "user_value_statement": (
            "历史审查中相同错误类型不会重复出现——"
            "当同一错误类型在多个审查中被标记时说明根本原因未被修复，"
            "模式匹配每发现一个重复错误扣15%直至归零。"
        ),
    },
]


# ══════════════════════════════════════════════
# M4: 知识管线健康检查
# ══════════════════════════════════════════════

def _knowledge_health_check():
    """检查知识管线健康度。防崩盖，所有异常吞掉返回降级值。"""
    checks = {
        "json_total_items": 0,
        "chroma_chunks": 0,
        "pending_items": 0,
        "needs_sync": False,
        "pending_domains": [],
        "health_score": 1.0,  # 0-1, 1=完全健康
    }
    try:
        from services.knowledge_sync import sync_status
        status = sync_status()
        checks["json_total_items"] = status["json_total_items"]
        checks["chroma_chunks"] = status["chroma_knowledge_chunks"]
        checks["pending_items"] = status["pending_items"]
        checks["needs_sync"] = status["needs_sync"]
        checks["pending_domains"] = status["pending_domains"]

        # 健康评分: 如果无知识条目 → 0.5 (partial); 如果有pending → 按比例扣分
        if checks["json_total_items"] == 0:
            checks["health_score"] = 0.5
        elif checks["pending_items"] > 0:
            ratio = checks["pending_items"] / max(checks["json_total_items"], 1)
            checks["health_score"] = max(0.0, 1.0 - ratio)
        else:
            checks["health_score"] = 1.0
    except Exception:
        checks["health_score"] = 0.0
        checks["error"] = "knowledge_sync query failed"

    try:
        from services.eval.eval_store import save_score
        save_score({
            "score_id": _generate_id(),
            "config_id": "knowledge_health",
            "source": "CODE",
            "value": checks["health_score"],
            "details": checks,
            "created_at": datetime.now().isoformat(),
            "duration_ms": 0,
        })
    except Exception:
        pass

    try:
        from services.eval.trace_logger import emit_event
        emit_event("knowledge.health_check", {
            "health_score": checks["health_score"],
            "pending_items": checks["pending_items"],
            "needs_sync": checks["needs_sync"],
        })
    except Exception:
        pass

    return checks


# ══════════════════════════════════════════════
# M4: 错误模式匹配 — 扫描历史审查中的重复错误
# ══════════════════════════════════════════════

def _check_error_patterns(days=30):
    """扫描历史审查中的错误模式，检测跨审查重复出现的错误类型。
    同一错误类型出现在 >= 2 个不同审查中视为"模式"。
    防崩盖，异常吞掉返回 None。
    """
    try:
        from services.review_store import list_reviews
    except ImportError:
        return None

    try:
        reviews = list_reviews(50)
    except Exception:
        return None

    cutoff = datetime.now()
    error_type_reviews = {}
    total_suggestions = 0
    scanned = 0

    for review in reviews:
        created = review.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created)
                if (cutoff - dt).days > days:
                    continue
            except Exception:
                pass
        scanned += 1
        for s in review.get("suggestions", []):
            total_suggestions += 1
            for et in s.get("linked_error_types", []):
                if et not in error_type_reviews:
                    error_type_reviews[et] = set()
                error_type_reviews[et].add(review.get("review_id", ""))

    # 识别模式：同一错误类型出现在 >= 2 个不同审查中
    patterns = []
    for error_type, review_ids in error_type_reviews.items():
        if len(review_ids) >= 2:
            patterns.append({
                "error_type": error_type,
                "occurrence_count": len(review_ids),
                "review_ids": sorted(review_ids),
            })

    if total_suggestions == 0 or len(patterns) == 0:
        pattern_score = 1.0
    else:
        pattern_score = max(0.0, 1.0 - len(patterns) * 0.15)

    result = {
        "reviews_scanned": scanned,
        "total_suggestions": total_suggestions,
        "patterns_found": len(patterns),
        "patterns": patterns,
        "pattern_score": round(pattern_score, 4),
    }

    try:
        eval_store.save_score({
            "score_id": _generate_id(),
            "config_id": "error_pattern_match",
            "source": "CODE",
            "value": pattern_score,
            "details": result,
            "created_at": datetime.now().isoformat(),
            "duration_ms": 0,
        })
    except Exception:
        pass

    try:
        emit_event("eval.error_pattern_match", {
            "patterns_found": len(patterns),
            "pattern_score": pattern_score,
            "top_patterns": [p["error_type"] for p in patterns[:3]],
        })
    except Exception:
        pass

    return result


# ══════════════════════════════════════════════
# M5: 前瞻性检测器 (Prospective Water Sources)
# ══════════════════════════════════════════════

def _check_kb_application_gap():
    """知识-应用差距检测。
    扫描知识库条目，对比 RAG 查询日志，发现"有知识但从未被查询"的领域。
    资源限制: 单文件 ≤1MB, 最多 1000 文件, 30s 超时。
    防崩盖，异常吞掉返回空列表。
    """
    import config as _cfg
    probes = []
    start_time = time.time()
    try:
        kb_dir = Path(__file__).parent.parent.parent / "data" / "knowledge"
        if not kb_dir.exists():
            return probes

        # 资源限制: 文件数上限
        json_files = sorted(kb_dir.glob("*.json"))[:_cfg.SCAN_MAX_FILES]
        if len(json_files) == 0:
            return probes

        kb_domains = set()
        for jf in json_files:
            if time.time() - start_time > _cfg.SCAN_TIMEOUT_SECONDS:
                break
            # 资源限制: 单文件大小
            if jf.stat().st_size > _cfg.SCAN_MAX_FILE_BYTES:
                continue
            try:
                with open(jf, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        domain = item.get("domain") or item.get("category") or item.get("source")
                        if domain:
                            kb_domains.add(domain)
                elif isinstance(data, dict):
                    domain = data.get("domain") or data.get("category")
                    if domain:
                        kb_domains.add(domain)
            except Exception:
                continue

        if not kb_domains:
            return probes

        # 扫描最近 RAG 查询中的领域
        if time.time() - start_time > _cfg.SCAN_TIMEOUT_SECONDS:
            return probes
        traces = eval_store._query_traces(trace_type="rag_query", window_hours=168, limit=200)
        queried_domains = set()
        for t in traces:
            if time.time() - start_time > _cfg.SCAN_TIMEOUT_SECONDS:
                break
            payload = t.get("payload") or {}
            domain = payload.get("domain") or payload.get("category") or t.get("name", "")
            if domain:
                queried_domains.add(domain)

        # 差距: 知识库有但从未查询的领域
        gap_domains = kb_domains - queried_domains
        for domain in sorted(gap_domains):
            probe_id = f"kb_gap_{domain}"[:64]
            probes.append({
                "probe_id": probe_id,
                "source": "kb_application_gap",
                "title": f"知识领域未被使用: {domain}",
                "description": f"知识库中存在 '{domain}' 领域条目，但过去7天内无相关RAG查询。考虑引入该知识到实际应用，或评估该领域是否仍然相关。",
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
                "recurrence_count": _count_probe_recurrence(probe_id) + 1,
                "resolution": None,
            })
    except Exception:
        pass
    return probes


def _check_module_staleness():
    """模块变更停滞检测。
    通过 git log 检查超过 90 天未修改的 Python 模块，生成探测卡。
    资源限制: 30s 超时 (git log 自带轻量)。
    防崩盖，异常吞掉返回空列表。
    """
    probes = []
    try:
        import subprocess
        repo_root = Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["git", "log", "--since=90.days.ago", "--name-only", "--pretty=format:", "--", "services/"],
            capture_output=True, text=True, timeout=30, cwd=str(repo_root)
        )
        if result.returncode != 0:
            return probes

        changed_files = set()
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line.endswith(".py"):
                changed_files.add(line)

        # 扫描 services/ 下所有 Python 文件
        services_dir = repo_root / "services"
        all_py = set()
        for pyf in services_dir.rglob("*.py"):
            rel = str(pyf.relative_to(repo_root)).replace("\\", "/")
            all_py.add(rel)

        stale = all_py - changed_files
        if len(stale) > 20:
            # 超过20个未变更文件 → 只报总览，不在每个文件生成探测卡
            stale_list = sorted(stale)[:5]
        else:
            stale_list = sorted(stale)

        for fpath in stale_list:
            probe_id = f"stale_{fpath.replace('/', '_').replace('.', '_')}"[:64]
            probes.append({
                "probe_id": probe_id,
                "source": "module_staleness",
                "title": f"模块超过90天未变更: {fpath}",
                "description": f"'{fpath}' 在过去90天内无任何 git commit。该模块可能已稳定，也可能被遗忘 — 建议审查是否需要更新或归档。",
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
                "recurrence_count": _count_probe_recurrence(probe_id) + 1,
                "resolution": None,
            })
    except Exception:
        pass
    return probes


def _check_error_recurrence():
    """重复错误指纹检测 (前瞻性)。
    扫描历史审查中的错误类型，对出现 ≥3 次的错误类型生成探测卡。
    同一错误类型的探测卡如已存在 → 增加 recurrence_count。
    资源限制: SCAN_TIMEOUT_SECONDS。
    防崩盖，异常吞掉返回空列表。
    """
    import config as _cfg
    probes = []
    start_time = time.time()
    try:
        from services.review_store import list_reviews
    except ImportError:
        return probes

    try:
        if time.time() - start_time > _cfg.SCAN_TIMEOUT_SECONDS:
            return probes
        reviews = list_reviews(100)
        if not reviews:
            return probes
    except Exception:
        return probes

    cutoff = datetime.now()
    error_type_reviews = {}

    for review in reviews:
        if time.time() - start_time > _cfg.SCAN_TIMEOUT_SECONDS:
            break
        created = review.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created)
                if (cutoff - dt).days > 90:
                    continue
            except Exception:
                pass
        for s in review.get("suggestions", []):
            for et in s.get("linked_error_types", []):
                if et not in error_type_reviews:
                    error_type_reviews[et] = set()
                error_type_reviews[et].add(review.get("review_id", ""))

    for error_type, review_ids in error_type_reviews.items():
        count = len(review_ids)
        if count >= 3:
            probe_id = f"err_recur_{error_type}"[:64]
            probes.append({
                "probe_id": probe_id,
                "source": "error_recurrence",
                "title": f"重复错误模式: {error_type}",
                "description": f"'{error_type}' 在过去90天出现在 {count} 个不同审查中。建议审查根本原因是否已被修复，或是否需要架构层面的改进。",
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
                "recurrence_count": _count_probe_recurrence(probe_id) + 1,
                "meta": {"review_ids": sorted(review_ids)},
                "resolution": None,
            })
            # ≥3 次 → 升级为建议
            if count >= 3:
                try:
                    sug_id = eval_store._generate_id()
                    eval_store.add_suggestion({
                        "suggestion_id": sug_id,
                        "severity": "P1",
                        "category": "error_recurrence",
                        "description": f"重复错误模式: {error_type} ({count}次)",
                        "status": "pending",
                        "created_at": datetime.now().isoformat(),
                    })
                    # 升级探测卡
                    from services.eval.eval_store import _resolve_probe
                    _resolve_probe(probe_id, "promoted_to_suggestion",
                                   f"升级为建议 {sug_id} (>=3次重复)")
                except Exception:
                    pass
    return probes


def _count_probe_recurrence(probe_id):
    """查询同一 probe_id 在此之前出现的次数"""
    try:
        existing = eval_store._load_probes()
        return sum(1 for p in existing if p.get("probe_id") == probe_id)
    except Exception:
        return 0


def _ingest_review_findings(window_hours=24):
    """消费 review_agent.finding 事件，路由到建议链。
    从 events.jsonl 读取 review_agent.finding 事件，
    对 P0/P1 发现自动创建建议（去重：相同描述不重复创建）。
    防崩盖，异常吞掉返回统计信息。
    """
    stats = {"total_findings": 0, "new_suggestions": 0}
    start_time = time.time()
    try:
        events = _read_jsonl("events.jsonl")
    except Exception:
        return stats

    cutoff = datetime.now() - timedelta(hours=window_hours)

    try:
        existing_descs = set()
        for s in eval_store.list_suggestions(limit=200):
            desc = s.get("description", "")[:80].strip().lower()
            if desc:
                existing_descs.add(desc)
    except Exception:
        existing_descs = set()

    for event in events:
        if event.get("event_type") != "review_agent.finding":
            continue
        ts_str = event.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts < cutoff:
                continue
        except Exception:
            continue

        payload = event.get("payload") or {}
        severity = payload.get("severity", "")
        if severity not in ("P0", "P1"):
            continue

        stats["total_findings"] += 1
        description = payload.get("description", "")
        desc_key = description[:80].strip().lower()
        if not description or desc_key in existing_descs:
            continue

        try:
            sug_id = eval_store._generate_id()
            eval_store.add_suggestion({
                "suggestion_id": sug_id,
                "severity": severity,
                "category": "review_agent_finding",
                "description": description[:200],
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "linked_error_types": payload.get("linked_error_types", []),
                "source_event_id": event.get("event_id", ""),
            })
            existing_descs.add(desc_key)
            stats["new_suggestions"] += 1
        except Exception:
            pass

    return stats


def _run_prospective_detectors():
    """运行所有前瞻性检测器，保存探测卡，处理自动过期。
    返回 dict 汇总。防崩盖，单个检测器失败不影响其他。
    """
    results = {"kb_gap": 0, "staleness": 0, "error_recurrence": 0, "expired": 0, "errors": []}
    detectors = [
        ("kb_gap", _check_kb_application_gap),
        ("staleness", _check_module_staleness),
        ("error_recurrence", _check_error_recurrence),
    ]
    for name, detector in detectors:
        try:
            probes = detector()
            for p in probes:
                eval_store._save_probe(p)
            results[name] = len(probes)
        except Exception as e:
            results["errors"].append(f"{name}: {e}")

    try:
        results["expired"] = eval_store._cleanup_expired_probes()
    except Exception as e:
        results["errors"].append(f"expiry: {e}")

    return results


# ══════════════════════════════════════════════
# Dashboard _build_summary 聚合 (Phase 3)
# ══════════════════════════════════════════════

def _compute_uncovered_count(surfaces):
    """计算 DEFAULT_SCORE_CONFIGS 中未被决策面覆盖的配置数。"""
    all_ids = {c["config_id"] for c in DEFAULT_SCORE_CONFIGS}
    covered_ids = set()
    for s_data in surfaces.values():
        covered_ids.update(s_data.get("config_ids", []))
    return len(all_ids - covered_ids)


def _latest_by_config(scores):
    """按 config_id 分组取最新值 → {config_id: value, ...}"""
    by_config = {}
    for s in scores:
        cid = s.get("config_id")
        if not cid:
            continue
        if cid not in by_config or s.get("created_at", "") > by_config[cid].get("created_at", ""):
            by_config[cid] = s
    return {cid: s["value"] for cid, s in by_config.items()}


def _weighted_avg(radar):
    """按 ScoreConfig 权重计算加权总分"""
    configs = {c["config_id"]: c for c in eval_store.list_score_configs()}
    total_w = 0.0
    total_s = 0.0
    for cid, val in radar.items():
        w = configs.get(cid, {}).get("weight", 0.0)
        if w > 0:
            total_w += w
            total_s += val * w
    return round(total_s / total_w, 4) if total_w > 0 else None


def _build_alerts():
    """聚合告警: 守护心跳 + P0 pending 建议 + 评分低于阈值

    M1 契约: 每条告警必须携带 alert_id，M2 的 L2 响应率统计依赖此 ID 追溯告警→建议链路。
    """
    from services.eval.trace_logger import _generate_id
    alerts = []
    stale, last_beat = _check_heartbeat_stale()
    if stale:
        alerts.append({
            "alert_id": _generate_id(),
            "severity": "P0",
            "type": "daemon_stale",
            "message": f"后台任务心跳超过2小时未更新 (上次: {last_beat or '从未'}) — 评估数据可能已过时",
        })
    for s in eval_store.list_suggestions(severity="P0", status="pending", limit=5):
        alerts.append({
            "alert_id": _generate_id(),
            "severity": "P0",
            "type": "suggestion",
            "config_id": s.get("category", ""),
            "message": s.get("description", "")[:120],
            "suggestion_id": s.get("suggestion_id"),
        })
    configs = {c["config_id"]: c for c in eval_store.list_score_configs()}
    latest = _latest_by_config(_aggregation_query(limit=200))
    for cid, val in latest.items():
        cfg = configs.get(cid, {})
        threshold = cfg.get("threshold")
        direction = cfg.get("direction", "above")
        if threshold is not None:
            if (direction == "above" and val < threshold) or \
               (direction == "below" and val > threshold):
                priority = cfg.get("priority", 99)
                sev = f"P{priority}" if priority <= 2 else "P3"
                alerts.append({
                    "alert_id": _generate_id(),
                    "severity": sev,
                    "type": "threshold",
                    "config_id": cid,
                    "current": val,
                    "threshold": threshold,
                    "message": f"{cfg.get('name', cid)}: {val} (阈值 {threshold})",
                })
    return alerts


def _build_annotations(config_id=None):
    """从 suggestions.json 提取已应用建议的标注 (含 value_before/value_after)"""
    suggestions = eval_store.list_suggestions(status="applied", limit=50)
    annotations = []
    for s in suggestions:
        if s.get("attribution_status") != "attributed":
            continue
        if s.get("status") != "applied":
            continue
        baseline = s.get("baseline_scores", {})
        delta_details = s.get("delta_details", {})
        for metric_key, baseline_info in baseline.items():
            if config_id and not metric_key.startswith(config_id):
                continue
            baseline_val = baseline_info.get("value") if isinstance(baseline_info, dict) else baseline_info
            delta_info = delta_details.get(metric_key, {})
            current_val = delta_info.get("current") if isinstance(delta_info, dict) else None
            annotations.append({
                "date": (s.get("applied_at") or s.get("created_at", ""))[:10],
                "type": "suggestion_applied",
                "title": s.get("description", "")[:80],
                "commit_sha": s.get("applied_commit", ""),
                "metric_key": metric_key,
                "value_before": baseline_val,
                "value_after": current_val,
                "delta": s.get("effect_score_delta"),
                "attribution_status": s.get("attribution_status"),
            })
    return annotations


def _build_summary():
    """总览聚合端点 (p95 < 500ms, 部分失败容错)"""
    from datetime import datetime
    import config as _cfg
    errors = []
    result = {
        "system_mode": "shadow" if getattr(_cfg, "EVAL_SHADOW_MODE", True) else "active",
        "total_score": None,
        "updated_at": datetime.now().isoformat(),
        "alerts": None,
        "trend": None,
        "radar": None,
        "annotations": None,
        "errors": errors,
    }

    try:
        scores = _aggregation_query(limit=200)
        radar = _latest_by_config(scores)
        # 只保留非宪法 Metric (有 weight > 0 的)
        configs = {c["config_id"]: c for c in eval_store.list_score_configs()}
        result["radar"] = {k: v for k, v in radar.items()
                          if configs.get(k, {}).get("weight", 0) > 0}
        result["radar_labels"] = {k: (configs.get(k, {}).get("display_name") or configs.get(k, {}).get("name", k))
                                  for k in result["radar"].keys()}
        result["total_score"] = _weighted_avg(radar)
        # sparkline: 每个非宪法 config 最近 7 个值
        sparklines = {}
        for cid in result["radar"].keys():
            vals = [s["value"] for s in scores if s.get("config_id") == cid]
            sparklines[cid] = vals[-7:] if len(vals) >= 2 else vals
        result["sparklines"] = sparklines
    except Exception as e:
        errors.append(f"radar: {e}")

    try:
        result["alerts"] = _build_alerts()
    except Exception as e:
        errors.append(f"alerts: {e}")

    try:
        result["trend"] = eval_store.get_score_trend("data_completeness", days=30)
    except Exception as e:
        errors.append(f"trend: {e}")

    try:
        result["annotations"] = _build_annotations()
    except Exception as e:
        errors.append(f"annotations: {e}")

    # ── M3: eval_coverage 检测 (三态: cold_start / partial / healthy) ──
    try:
        trace_count = len(eval_store._query_traces(window_hours=168, limit=500))  # 7 天
        score_count = len(result.get("radar") or {})
        if score_count == 0 and trace_count == 0:
            result["coverage"] = "cold_start"
        elif score_count < 3 or trace_count < 5:
            result["coverage"] = "partial"
        else:
            result["coverage"] = "healthy"

        # M3-7: 附加决策面覆盖统计
        try:
            from services.eval.eval_store import _load_decision_surfaces
            surfaces = _load_decision_surfaces()
            result["coverage_data"] = {
                "covered_count": len(surfaces),
                "uncovered_count": _compute_uncovered_count(surfaces),
            }
        except Exception:
            pass
    except Exception as e:
        result["coverage"] = "load_failed"
        errors.append(f"coverage: {e}")

    # ── M4-1: 知识管线健康数据 ──
    try:
        kh_scores = [s for s in eval_store.query_scores(limit=50)
                     if s.get("config_id") == "knowledge_health"]
        if kh_scores:
            latest = kh_scores[0]
            result["knowledge_health"] = {
                "health_score": latest.get("value"),
                "details": latest.get("details", {}),
                "updated_at": latest.get("created_at"),
            }
    except Exception:
        pass

    return result


def _seed_score_configs():
    """首次运行时注册 8 个指标的 ScoreConfig。幂等。"""
    created = 0
    skipped = 0
    for cfg in DEFAULT_SCORE_CONFIGS:
        existing = eval_store.get_score_config(cfg["config_id"])
        if existing:
            skipped += 1
            continue
        eval_store.save_score_config(cfg)
        created += 1
    return {"created": created, "already_existed": skipped}
