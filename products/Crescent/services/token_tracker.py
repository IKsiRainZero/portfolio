"""Token usage tracker — reads portfolio's own API call logs from agent_logger"""
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from config import USER_DATA_DIR

TOKEN_LOG_DIR = Path(USER_DATA_DIR) / "token_logs"
_cache = {}
_CACHE_TTL = 300  # 5 minutes


def _read_token_logs(days=7):
    """Read token_logs JSONL files for last N days. Returns list of dicts."""
    cutoff_ts = time.time() - days * 86400
    records = []
    if not TOKEN_LOG_DIR.exists():
        return records
    for f in sorted(TOKEN_LOG_DIR.glob("*.jsonl"), reverse=True):
        try:
            if f.stat().st_mtime < cutoff_ts:
                continue
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    records.append(obj)
        except Exception:
            continue
    return records


def _read_agent_stats(days=7):
    """Read agent call counts and durations from agent_logger."""
    from services.agent_logger import get_log_stats
    try:
        stats = get_log_stats(days=days)
        return {
            "total_calls": stats.get("total_calls", 0),
            "avg_duration_ms": stats.get("avg_duration_ms", 0),
        }
    except Exception:
        return {"total_calls": 0, "avg_duration_ms": 0}


def get_dashboard_stats(days=7):
    """Aggregated dashboard stats with 5-minute cache."""
    cache_key = f"dashboard_{days}"
    now = time.time()
    if cache_key in _cache:
        data, ts = _cache[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    records = _read_token_logs(days)
    agent_stats = _read_agent_stats(days)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_tokens = 0
    month_tokens = 0
    today_cost = 0.0
    month_cost = 0.0
    by_model = {}

    for r in records:
        prompt = r.get("prompt_tokens", 0)
        completion = r.get("completion_tokens", 0)
        total = prompt + completion
        cost = r.get("cost_usd", 0)
        provider = r.get("provider", "unknown")

        # Try to parse date from ts field
        ts_str = r.get("ts", "")
        date_str = ts_str[:10] if ts_str else "unknown"

        if date_str == today_str:
            today_tokens += total
            today_cost += cost

        month_tokens += total
        month_cost += cost

        key = f"{r.get('model', 'unknown')} ({provider})"
        if key not in by_model:
            by_model[key] = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0}
        by_model[key]["input_tokens"] += prompt
        by_model[key]["output_tokens"] += completion
        by_model[key]["cost_usd"] += cost

    stats = {
        "today_tokens": today_tokens,
        "month_tokens": month_tokens,
        "month_cost_usd": round(month_cost, 4) if month_cost > 0 else None,
        "today_cost_usd": round(today_cost, 4) if today_cost > 0 else None,
        "by_model": [{"model": k, **v} for k, v in by_model.items()],
        "agent_calls": agent_stats["total_calls"],
        "agent_avg_duration_ms": agent_stats["avg_duration_ms"],
    }

    _cache[cache_key] = (stats, now)
    return stats


def invalidate_cache():
    _cache.clear()


def get_stats_by_task_type(days: int = 7) -> list[dict]:
    records = _read_token_logs(days)
    by_type = {}
    for r in records:
        task = r.get("task_type", "") or "uncategorized"
        if task not in by_type:
            by_type[task] = {"task_type": task, "calls": 0, "total_tokens": 0, "cost_usd": 0}
        by_type[task]["calls"] += 1
        by_type[task]["total_tokens"] += r.get("prompt_tokens", 0) + r.get("completion_tokens", 0)
        by_type[task]["cost_usd"] += r.get("cost_usd", 0)
    result = sorted(by_type.values(), key=lambda x: -x["total_tokens"])
    for item in result:
        item["cost_usd"] = round(item["cost_usd"], 6)
    return result
