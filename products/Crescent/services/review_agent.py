"""ReviewAgent 核心 — 日志聚合 + LLM分析 + 实际修改文件 + 自指闭环 + 自动触发"""
from __future__ import annotations
import json
import time
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from services.deepseek_client import chat, load_prompt
from services.review_store import (
    add_review, update_suggestion_status, save_snapshot, restore_snapshot,
    increment_session_count, should_auto_review, mark_review_triggered, get_session_count,
)
from services.review_memory import (
    save_hot_session, list_hot_sessions, hot_count,
    should_generate_warm, get_oldest_hot_sessions, save_warm_summary, list_warm_summaries,
    should_generate_cold, get_oldest_warm_summaries, save_cold_crystallization,
    list_cold_rules, search_archive, archive_to_chromadb, find_stale_rules,
    mark_rule_triggered, get_memory_state,
    HOT_DIR, WARM_DIR, COLD_DIR,
)
from services.doc_indexer import get_all_indexed
from services.agent_logger import get_log_stats, get_event_summary, list_recent_events, log_event

ROOT = Path(__file__).parent.parent.parent
PARAMS_FILE = ROOT / "data" / "user_data" / "review_params.json"


# ── 自指参数管理 ──

def _load_params() -> dict:
    defaults = {
        "compression_level": 0.5,
        "max_input_tokens": 18000,
        "budget_exceeded_streak": 0,
        "max_budget_streak": 3,
        "analysis_weights": {"error_repeat": 1.0, "token_anomaly": 0.8, "improvement": 0.6},
        "auto_apply": False,  # Shadow mode: 前 2 周只生成建议不自动应用
        "shadow_started_at": datetime.now(timezone.utc).isoformat(),
    }
    if not PARAMS_FILE.exists():
        return defaults
    try:
        loaded = json.loads(PARAMS_FILE.read_text(encoding="utf-8"))
        merged = {**defaults, **loaded}
        # 2 周后自动关闭 shadow mode
        if merged["auto_apply"] is False:
            try:
                started = datetime.fromisoformat(merged["shadow_started_at"])
                if (datetime.now(timezone.utc) - started).days >= 14:
                    merged["auto_apply"] = True
                    _save_params(merged)
            except (ValueError, TypeError, OSError):
                pass
        return merged
    except (json.JSONDecodeError, IOError):
        return defaults


def _save_params(params: dict):
    PARAMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PARAMS_FILE.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")


def _adjust_compression():
    """自指：超预算次数达到阈值时自动提高压缩率"""
    params = _load_params()
    params["budget_exceeded_streak"] += 1
    if params["budget_exceeded_streak"] >= params["max_budget_streak"]:
        params["compression_level"] = min(1.0, params["compression_level"] + 0.15)
        params["budget_exceeded_streak"] = 0
    _save_params(params)


def _reset_budget_streak():
    params = _load_params()
    params["budget_exceeded_streak"] = 0
    _save_params(params)


# ── 文件写入白名单 — 只允许修改知识文档，不允许修改运行代码 ──

ALLOWED_TARGETS = [
    "CLAUDE.md",
    "知识库/参考/审查清单.md",
    "知识库/错误与修正与优化/",
]


# ── 压缩失败跟踪 ──

_COMPRESS_FAIL_STREAK = {"warm": 0, "cold": 0}
_MAX_COMPRESS_FAILS = 3


# ── 核心审查逻辑 ──

def run_review() -> dict:
    """执行一次完整审查。返回 review_id 和摘要。"""
    t0 = time.time()

    # 0. 先执行记忆压缩（Warm/Cold/Archive 维护）
    warm_result = _compress_to_warm()
    cold_result = _crystallize_to_cold()
    _maintain_archive()

    # 1. 聚合日志
    agent_summary = get_log_stats(days=7)
    event_summary = get_event_summary(days=7)
    hot_sessions = list_hot_sessions(20)
    warm_summaries = list_warm_summaries(10)
    cold_rules = list_cold_rules()
    doc_index = get_all_indexed()

    # 2. Archive RAG 唤醒：用当前日志中的错误关键词检索历史
    archive_context = _wake_archive(agent_summary, event_summary)

    # 3. 构建 LLM 输入（受自指参数控制的压缩）
    params = _load_params()
    user_msg = _build_review_message(
        agent_summary, event_summary, hot_sessions,
        warm_summaries, cold_rules, doc_index, archive_context,
        compression=params["compression_level"]
    )

    system_prompt = load_prompt("review_agent") or _default_prompt()

    # 4. 调用 LLM
    try:
        reply, usage = chat(
            messages=[{"role": "user", "content": user_msg}],
            system_prompt=system_prompt,
            temperature=0.15,
            max_tokens=3000,
            timeout=120,
        )
    except Exception as e:
        return {"error": f"LLM call failed: {e}", "review_id": "", "duration_ms": (time.time() - t0) * 1000}

    # 5. 解析 LLM 输出
    findings_data = _parse_json(reply)

    # 6. 处理自指反馈（使用真实 token 数据，而非 LLM 估计）
    prompt_tokens = usage.get("prompt_tokens", 0) if isinstance(usage, dict) else 0
    params = _load_params()
    max_input = params["max_input_tokens"]

    # 用 chat() 返回的真实 prompt_tokens 判断是否超预算
    if prompt_tokens > max_input * 0.9:
        _adjust_compression()
    else:
        _reset_budget_streak()

    # LLM self_check 仅作辅助：当实际未超但 LLM 感知到信息密度不足时
    self_check = findings_data.get("self_check", {})
    if self_check.get("should_increase_compression") and prompt_tokens < max_input * 0.5:
        # LLM 觉得信息不够但实际预算充足 — 不调压缩率，可能是日志本身就少
        pass

    # 7. 自动回滚评估：检查已应用建议是否已失效
    auto_rollbacks = _auto_evaluate_and_rollback()
    suggestions = []
    for i, f in enumerate(findings_data.get("findings", [])):
        action = f.get("action", {})
        # ── 二次校验：验证 LLM 输出的 action 是否有效 ──
        validated_action = _validate_action(action)
        if validated_action != action:
            # 降级无效 action：type 改为 "none"，清除文件写入字段
            f["action"] = validated_action
            action = validated_action
        # 从 finding 的 evidence/description 中提取关联的错误类型指纹
        linked_errors = _extract_error_types_from_finding(f)
        suggestions.append({
            "index": i,
            "dimension": f.get("dimension", ""),
            "severity": f.get("severity", "P2"),
            "description": f.get("description", ""),
            "suggestion": f.get("suggestion", ""),
            "action": action,
            "linked_error_types": linked_errors,
            "status": "pending",
        })

    memory_state = get_memory_state()
    review = {
        "summary": findings_data.get("summary", ""),
        "findings": findings_data.get("findings", []),
        "suggestions": suggestions,
        "token_usage": usage,
        "self_check": self_check,
        "memory_state": memory_state,
    }

    duration_ms = (time.time() - t0) * 1000
    review_id = add_review(review)

    # M4: 发射 review_agent.finding 事件，供 error pattern matching 消费
    try:
        from services.eval.trace_logger import emit_event
        for s in suggestions:
            if s["severity"] in ("P0", "P1") or s.get("linked_error_types"):
                emit_event("review_agent.finding", {
                    "review_id": review_id,
                    "severity": s["severity"],
                    "dimension": s.get("dimension", ""),
                    "description": s.get("description", "")[:200],
                    "linked_error_types": s.get("linked_error_types", []),
                })
    except Exception:
        pass

    mark_review_triggered()

    return {
        "review_id": review_id,
        "summary": findings_data.get("summary", ""),
        "findings_count": len(findings_data.get("findings", [])),
        "warm_generated": warm_result,
        "cold_generated": cold_result,
        "self_check": self_check,
        "memory_state": memory_state,
        "auto_rollbacks": auto_rollbacks,  # 本次审查中自动回滚的记录
        "duration_ms": round(duration_ms, 1),
        "token_usage": usage,
    }


def apply_suggestion(review_id: str, suggestion_index: int) -> dict:
    """应用一条建议：校验白名单 → 快照目标文件 → 实际写入 → 更新状态"""
    from services.review_store import get_review
    review = get_review(review_id)
    if not review:
        return {"error": "review not found"}

    suggestions = review.get("suggestions", [])
    if suggestion_index >= len(suggestions):
        return {"error": "suggestion index out of range"}

    suggestion = suggestions[suggestion_index]
    action = suggestion.get("action", {})

    if action.get("type") != "rule":
        return {"error": "suggestion has no actionable modification (action.type != 'rule')"}

    target_file = action.get("target_file", "")
    content = action.get("content_to_append", "")

    if not target_file or not content:
        return {"error": "action missing target_file or content_to_append"}

    # 白名单校验 — 只允许写入知识文档，拒绝代码文件
    allowed = False
    for prefix in ALLOWED_TARGETS:
        if target_file.replace("\\", "/").startswith(prefix.replace("\\", "/")):
            allowed = True
            break
    if not allowed:
        return {
            "error": f"target_file '{target_file}' not in whitelist. Allowed: {ALLOWED_TARGETS}",
            "hint": "自动修改仅限于知识文档（CLAUDE.md/审查清单/错误记录），不可修改运行代码",
        }

    # 解析目标文件路径（相对于项目根）
    target_path = Path(target_file)
    if not target_path.is_absolute():
        target_path = ROOT / target_file

    # 只做追加，不做覆盖
    if not target_path.exists():
        # 如果目标文件不存在（如错误文档目录下的新文件），创建它
        target_path.parent.mkdir(parents=True, exist_ok=True)

    # 快照
    snapshot_id = save_snapshot(str(target_path)) if target_path.exists() else ""

    # 实际写入（追加模式）
    try:
        existing = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
        if existing and not existing.endswith("\n"):
            existing += "\n"
        new_content = existing + "\n" + content.strip() + "\n"
        target_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        # 写入失败，恢复快照
        if snapshot_id:
            restore_snapshot(snapshot_id, str(target_path))
        return {"error": f"write failed: {e}"}

    update_suggestion_status(review_id, suggestion_index, "applied")
    return {"ok": True, "snapshot_id": snapshot_id, "target": str(target_path),
            "message": f"Content appended to {target_file}"}


def rollback_suggestion(review_id: str, suggestion_index: int) -> dict:
    """回滚一条已应用的建议：从快照恢复"""
    from services.review_store import get_review, list_snapshots
    review = get_review(review_id)
    if not review:
        return {"error": "review not found"}

    suggestions = review.get("suggestions", [])
    if suggestion_index >= len(suggestions):
        return {"error": "suggestion index out of range"}

    suggestion = suggestions[suggestion_index]
    target_file = suggestion.get("action", {}).get("target_file", "")
    if not target_file:
        return {"error": "no target file to rollback"}

    # 找最新的匹配快照
    target_name = Path(target_file).name
    snapshots = list_snapshots()
    matching = [s for s in snapshots if target_name in s["id"]]
    if not matching:
        return {"error": "no snapshot found for rollback"}

    target_path = ROOT / target_file
    ok = restore_snapshot(matching[0]["id"], str(target_path))
    if not ok:
        return {"error": "restore failed"}

    update_suggestion_status(review_id, suggestion_index, "rolled_back")
    return {"ok": True, "message": f"Rolled back to snapshot {matching[0]['id']}"}


def evaluate_past_suggestions() -> list[dict]:
    """评估已应用的建议是否有效：用 linked_error_types 精确比对近期错误"""
    from services.review_store import list_reviews
    events = list_recent_events(days=30)
    recent_error_types = {}
    for e in events:
        if e.get("event_type") == "error":
            et = e.get("error_type", "")
            if et:
                recent_error_types[et] = recent_error_types.get(et, 0) + 1

    evaluations = []
    for review in list_reviews(30):
        rid = review.get("review_id", "")
        for i, s in enumerate(review.get("suggestions", [])):
            if s.get("status") != "applied":
                continue
            # 使用建议中存储的 linked_error_types 做精确匹配
            linked = s.get("linked_error_types", [])
            if not linked:
                continue
            match_count = sum(
                recent_error_types.get(et, 0) for et in linked
            )
            if match_count > 0:
                evaluations.append({
                    "review_id": rid, "suggestion_index": i,
                    "status": "likely_failed" if match_count >= 3 else "suspect",
                    "recurring_count": match_count,
                    "linked_errors": linked,
                    "reason": f"Linked errors occurred {match_count} times since applied",
                })
    return evaluations


def _auto_evaluate_and_rollback() -> list[dict]:
    """自动回滚：检查已应用建议，用 linked_error_types 精确匹配。≥3 次则回滚并归档"""
    from services.review_store import list_reviews
    events = list_recent_events(days=30)

    # 按 error_type 指纹统计近期错误出现次数
    error_counts = {}
    for e in events:
        if e.get("event_type") == "error":
            et = e.get("error_type", "unknown")
            if et:
                error_counts[et] = error_counts.get(et, 0) + 1

    rollbacks = []
    for review in list_reviews(30):
        rid = review.get("review_id", "")
        for i, s in enumerate(review.get("suggestions", [])):
            if s.get("status") != "applied":
                continue
            # 精确匹配：用写入建议时提取的 linked_error_types 指纹
            linked = s.get("linked_error_types", [])
            if not linked:
                continue
            total_recurring = sum(
                error_counts.get(et, 0) for et in linked
            )
            if total_recurring >= 3:
                rb_result = rollback_suggestion(rid, i)
                archive_to_chromadb({
                    "rule": s.get("suggestion", s.get("description", "")),
                    "_source_month": rid,
                }, "fix_failed")
                rollbacks.append({
                    "review_id": rid,
                    "suggestion_index": i,
                    "recurring_count": total_recurring,
                    "linked_errors": linked,
                    "rollback_result": rb_result,
                })
    return rollbacks


# ── 自动触发 ──

def check_auto_trigger() -> dict | None:
    """检查是否应自动触发审查，如果是则执行"""
    if not should_auto_review(max_sessions=10, max_days=7):
        return None
    print(f"[review_agent] Auto-triggering review (sessions: {get_session_count()})")
    # ★ 链1: 后台任务显式 TraceContext
    try:
        from services.eval.trace_logger import TraceContext
        with TraceContext(name="auto_review", kind="scheduled_task",
                          metadata={"trigger": "session_count_threshold"}):
            return run_review()
    except Exception:
        return run_review()


# ── 内部函数 ──

def _wake_archive(agent_summary: dict, event_summary: dict) -> str:
    """从 ChromaDB Archive 中检索与当前错误模式相关的历史规则"""
    keywords = []
    for e in event_summary.get("recent_errors", [])[:5]:
        msg = e.get("message", "")
        keywords.append(msg[:100])
    if not keywords:
        return ""
    query = " ".join(keywords)[:500]
    results = search_archive(query, k=5)
    if not results:
        return ""
    lines = ["## Archive 唤醒（相关历史规则）"]
    for r in results:
        lines.append(f"- {r['text'][:300]}")
    return "\n".join(lines)


def _maintain_archive():
    """维护 Archive：将过期 Cold 规则归档，将 fix_failed 规则归档"""
    # 注意：不在每次审查时自动归档！
    # 先做 Cold 规则"续命"——未被推翻的规则续期
    _renew_active_rules()
    # 只归档被标记为 fix_failed 或被评估为无效的规则
    for rule in find_stale_rules(weeks=4):
        # stale 规则先降权而非直接删除：降低 confidence
        rule["confidence"] = rule.get("confidence", 0.8) * 0.5
        # 如果降权后 confidence < 0.2 或者在 Cold 中存在 >8 周且从未触发，才归档
        created = rule.get("_created_at", "")
        try:
            age_weeks = (datetime.now(timezone.utc) - datetime.fromisoformat(created)).days / 7
        except (ValueError, TypeError, OSError):
            age_weeks = 0
        if rule.get("confidence", 0.8) < 0.2 or (age_weeks > 8 and not rule.get("last_triggered")):
            archive_to_chromadb(rule, "archived")
    # fix_failed 规则由 auto-rollback 触发归档


def _renew_active_rules():
    """每次审查后对 Cold 规则做条件续期。
    只续期满足以下条件之一的规则：
    1. 本次审查中 LLM 明确引用了该规则（在 findings 的 evidence 中）
    2. 规则已被 mark_rule_triggered() 标记为触发过
    3. 规则的 confidence > 0.9（高置信度规则不需要频繁验证）

    不再无条件续期所有规则——这会导致冷规则永远不会过期。
    """
    from services.review_store import list_reviews
    recent_reviews = list_reviews(2)

    # 收集被回滚的规则文本（这些不续期）
    deprecated_rules = set()
    for rv in recent_reviews:
        for s in rv.get("suggestions", []):
            if s.get("status") in ("rolled_back",):
                deprecated_rules.add(s.get("description", "")[:80])

    # 收集本次审查中 LLM 引用了哪些 Cold 规则
    referenced_rules = set()
    for rv in recent_reviews:
        for f_item in rv.get("findings", []):
            evidence = f_item.get("evidence", "")
            # 从 evidence 中提取被引用的规则片段
            if "Cold" in evidence or "规则" in evidence:
                referenced_rules.add(evidence[:120])

    for f in sorted(COLD_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            modified = False
            for rule in data.get("rules", []):
                rule_text = rule.get("rule", "")[:80]
                if rule_text in deprecated_rules:
                    continue
                # 条件续期判断
                confidence = rule.get("confidence", 0.5)
                was_triggered = bool(rule.get("last_triggered"))
                is_referenced = any(
                    rule_text[:40] in ref or ref in rule_text[:40]
                    for ref in referenced_rules
                )
                if is_referenced or was_triggered or confidence > 0.9:
                    rule["last_triggered"] = datetime.now(timezone.utc).isoformat()
                    rule["trigger_count"] = rule.get("trigger_count", 0) + 1
                    modified = True
            if modified:
                f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except (json.JSONDecodeError, IOError):
            pass


def _build_review_message(agent_summary, event_summary, hot_sessions,
                          warm_summaries, cold_rules, doc_index,
                          archive_context, compression=0.5) -> str:
    """构建 LLM 审查消息，compression 越高越精简"""
    parts = ["## 运行时日志（最近 7 天）"]
    parts.append(f"Agent 调用: {agent_summary.get('total_calls', 0)} 次")
    parts.append(f"工具调用: {agent_summary.get('total_tool_calls', 0)} 次")
    parts.append(f"活跃会话: {agent_summary.get('sessions', 0)}")

    # 事件摘要
    parts.append(f"\n### 结构化事件")
    parts.append(f"总事件: {event_summary.get('total_events', 0)}")
    for etype, count in event_summary.get("by_type", {}).items():
        parts.append(f"  {etype}: {count}")
    recent = event_summary.get("recent_errors", [])[:15]
    if recent:
        parts.append("近期错误:")
        for e in recent:
            parts.append(f"  - {e.get('ts', '')[:16]} {e.get('message', '')[:200]}")

    # Hot 层 — compression 控制数量
    max_hot = max(3, int(20 * (1 - compression)))
    if hot_sessions[:max_hot]:
        parts.append(f"\n## Hot 层会话（最近 {min(len(hot_sessions), max_hot)} 次）")
        for s in hot_sessions[:max_hot]:
            parts.append(f"- {s.get('saved_at', '')[:16]} errors:{s.get('error_count', 0)} tools:{s.get('tool_calls', 0)}")

    # Warm 层
    if warm_summaries:
        parts.append(f"\n## Warm 层周摘要（{len(warm_summaries)} 周）")
        for w in warm_summaries[:5]:
            parts.append(f"- {w.get('week', '')}: {w.get('raw_text', '')[:200]}")

    # Cold 层
    if cold_rules:
        parts.append(f"\n## Cold 层规则（{len(cold_rules)} 条）")
        for r in cold_rules[:10]:
            parts.append(f"- [{r.get('_source_month', '')}] {r.get('rule', '')[:200]}")

    # Archive
    if archive_context:
        parts.append(f"\n{archive_context}")

    # 文档索引
    parts.append(f"\n## 文档索引")
    parts.append(f"错误文档: {[e['title'] + '[' + e['fix_status'] + ']' for e in doc_index.get('errors', [])[:10]]}")
    pending_cps = [cp for cp in doc_index.get('checkpoints', []) if cp.get('pending')]
    if pending_cps:
        parts.append(f"未完成 checkpoint: {pending_cps[0]['date']} — {pending_cps[0]['pending'][:3]}")

    # compression > 0.7 时进一步削减
    msg = "\n".join(parts)
    if compression > 0.7:
        lines = msg.split("\n")
        msg = "\n".join(lines[:max(20, int(len(lines) * (1 - compression)))])
    return msg[:18000]


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        import re
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"summary": "JSON parse failed", "findings": [], "self_check": {}}


def _validate_action(action: dict) -> dict:
    """二次校验 LLM 输出的 action 是否有效。无效则降级为 type="none"。
    校验项：白名单、content_to_append 长度、是否含 markdown 标题。
    """
    if not isinstance(action, dict):
        return {"type": "none"}
    if action.get("type") != "rule":
        return action

    target = action.get("target_file", "")
    content = action.get("content_to_append", "")

    # 白名单检查
    allowed = any(
        target.replace("\\", "/").startswith(prefix.replace("\\", "/"))
        for prefix in ALLOWED_TARGETS
    )
    if not allowed:
        return {"type": "none"}

    # 内容长度检查
    if len(content.strip()) < 50:
        return {"type": "none"}

    # 必须包含 markdown 标题（## 或 ###）
    if "##" not in content:
        return {"type": "none"}

    return action


def _extract_error_types_from_finding(finding: dict) -> list[str]:
    """从 LLM 输出的 finding 中提取关联的错误类型指纹。
    优先从 evidence 字段中搜索已知的错误指纹关键词；
    也检查 description 中是否引用了特定错误类型。
    返回去重后的错误指纹列表（供 linked_error_types 使用）。
    """
    evidence = finding.get("evidence", "")
    description = finding.get("description", "")
    combined = f"{evidence} {description}"

    # 从近期事件中匹配已知错误指纹
    fingerprint_set = set()
    try:
        recent = list_recent_events(days=30)
        for e in recent:
            et = e.get("error_type", "")
            if not et:
                continue
            msg = e.get("error_message", "")
            # 如果 evidence/description 中提到该错误的消息或类型，关联之
            if et in combined or (msg and msg[:50] in combined):
                fingerprint_set.add(et)
    except Exception:
        pass
    return list(fingerprint_set)


# ── 记忆压缩 (Warm / Cold) ──

def _compress_to_warm():
    """将最旧的 5 条 Hot 会话压缩为一份 Warm 周摘要。带失败跟踪和统计降级。"""
    global _COMPRESS_FAIL_STREAK
    if not should_generate_warm():
        return None
    # 跳过已在孤儿 manifest 中的文件（上次压缩可能崩溃了但 Warm 已写）
    orphan_files = set()
    for mf in WARM_DIR.glob("*.manifest.json"):
        try:
            mdata = json.loads(mf.read_text(encoding="utf-8"))
            orphan_files.update(mdata.get("files", []))
        except (json.JSONDecodeError, IOError):
            pass
    sessions = [s for s in get_oldest_hot_sessions(10)
                if str(HOT_DIR / f"{s.get('session_id', '')}.json") not in orphan_files][:5]
    if len(sessions) < 3:
        return None

    prompt_text = (
        "TASK: COMPRESS\n"
        "将以下 5 次会话摘要压缩为一份周报级摘要。提取：\n"
        "1. error_patterns: 重复出现的错误类型及次数\n"
        "2. key_metrics: 平均 token 消耗、工具调用次数\n"
        "3. improvements_tried: 尝试了哪些改进\n\n"
        "输出 JSON: {\"error_patterns\": [...], \"key_metrics\": {...}, \"improvements_tried\": [...], \"raw_text\": \"一句话总结\"}"
    )
    user_msg = prompt_text + "\n\n" + json.dumps(sessions, ensure_ascii=False, indent=2)[:8000]

    try:
        reply, _ = chat(messages=[{"role": "user", "content": user_msg}],
                        system_prompt="你是日志压缩器。只输出 JSON。", temperature=0.1, max_tokens=1500, timeout=90)
        result = _parse_json(reply)
        # 成功，重置失败计数
        _COMPRESS_FAIL_STREAK["warm"] = 0
    except Exception as e:
        _COMPRESS_FAIL_STREAK["warm"] += 1
        # 连续失败 3 次 → 统计降级：直接用最近 Hot 的关键字段拼一个摘要
        if _COMPRESS_FAIL_STREAK["warm"] >= _MAX_COMPRESS_FAILS:
            result = _statistical_fallback_warm(sessions)
        else:
            # 告警
            try:
                log_event("error", {
                    "error_type": "compression_warm_failed",
                    "phase": "memory_compression",
                    "error_message": f"Warm compression failed (streak={_COMPRESS_FAIL_STREAK['warm']}): {e}",
                    "recurring": _COMPRESS_FAIL_STREAK["warm"] >= 2,
                })
            except Exception:
                pass
            return None

    week_label = datetime.now(timezone.utc).strftime("%Y-W%W")
    result["sessions_compressed"] = len(sessions)
    result.setdefault("error_patterns", [])
    result.setdefault("key_metrics", {})
    result.setdefault("improvements_tried", [])
    result.setdefault("raw_text", "")
    save_warm_summary(week_label, result)
    return week_label


def _statistical_fallback_warm(sessions: list[dict]) -> dict:
    """统计降级：不通过 LLM，直接用会话数据的聚合值构建 Warm 摘要"""
    total_errors = sum(s.get("error_count", 0) for s in sessions)
    total_tools = sum(s.get("tool_calls", 0) for s in sessions)
    avg_duration = sum(s.get("duration_ms", 0) for s in sessions) / max(len(sessions), 1)
    error_types = {}
    for s in sessions:
        for err in s.get("errors", []):
            et = err.get("error_type", "unknown")
            error_types[et] = error_types.get(et, 0) + 1
    return {
        "error_patterns": [{"error_type": et, "count": c} for et, c in sorted(error_types.items(), key=lambda x: -x[1])[:5]],
        "key_metrics": {"avg_tool_calls": total_tools / max(len(sessions), 1), "avg_duration_ms": round(avg_duration), "total_errors": total_errors},
        "improvements_tried": [],
        "raw_text": f"[统计降级] {len(sessions)}次会话，{total_errors}个错误，{total_tools}次工具调用",
    }


def _crystallize_to_cold():
    """将最旧的 4 条 Warm 摘要结晶为 Cold 规则。带失败跟踪。"""
    global _COMPRESS_FAIL_STREAK
    if not should_generate_cold():
        return None
    summaries = get_oldest_warm_summaries(4)
    if len(summaries) < 2:
        return None

    prompt_text = (
        "TASK: CRYSTALLIZE\n"
        "从以下 4 周的周摘要中提取可永久保留的规则和方法论。输出 JSON:\n"
        '{"rules": [{"rule": "具体规则", "confidence": 0.8, "evidence_weeks": 2}], '
        '"methodologies": [{"name": "方法名", "description": "描述", "effectiveness": 0.7}], "raw_text": "..."}'
    )
    user_msg = prompt_text + "\n\n" + json.dumps(summaries, ensure_ascii=False, indent=2)[:8000]

    try:
        reply, _ = chat(messages=[{"role": "user", "content": user_msg}],
                        system_prompt="你是方法论提取器。只输出 JSON。", temperature=0.1, max_tokens=2000, timeout=90)
        result = _parse_json(reply)
        _COMPRESS_FAIL_STREAK["cold"] = 0
    except Exception as e:
        _COMPRESS_FAIL_STREAK["cold"] += 1
        try:
            log_event("error", {
                "error_type": "compression_cold_failed",
                "phase": "memory_compression",
                "error_message": f"Cold crystallization failed (streak={_COMPRESS_FAIL_STREAK['cold']}): {e}",
                "recurring": _COMPRESS_FAIL_STREAK["cold"] >= 2,
            })
        except Exception:
            pass
        return None

    month_label = datetime.now(timezone.utc).strftime("%Y-%m")
    result["weeks_merged"] = len(summaries)
    result.setdefault("rules", [])
    result.setdefault("methodologies", [])
    result.setdefault("raw_text", "")
    save_cold_crystallization(month_label, result)
    return month_label


def _default_prompt() -> str:
    return "你是 Crescent 的自审查代理。分析日志和文档，输出可执行改进建议的 JSON。action.type 为 rule 时须包含 content_to_append。"


# ── 异步写入队列（避免 on_session_complete 阻塞用户请求线程） ──

_WRITE_QUEUE = queue.Queue()


def _background_writer():
    """守护线程：消费写入队列，执行文件 I/O"""
    while True:
        try:
            task = _WRITE_QUEUE.get()
            if task is None:  # 停止信号
                break
            func, args, kwargs = task
            try:
                func(*args, **kwargs)
            except Exception:
                pass  # 写入失败不影响主流程
            _WRITE_QUEUE.task_done()
        except queue.Empty:
            continue


_writer_thread = threading.Thread(target=_background_writer, daemon=True)
_writer_thread.start()


# ── 会话钩子（供 agent_service 调用） ──

def on_session_complete(session_id: str, session_summary: dict):
    """每次 Agent 会话完成后调用。写入操作入队到后台线程，不阻塞用户请求。"""
    _WRITE_QUEUE.put((save_hot_session, (session_id, session_summary), {}))
    _WRITE_QUEUE.put((increment_session_count, (), {}))
