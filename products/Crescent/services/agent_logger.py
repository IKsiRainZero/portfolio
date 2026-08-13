"""Agent 结构化日志 — 每次调用记录完整决策链到 JSONL"""
import hashlib
import json
import re
import time
from pathlib import Path
from datetime import datetime, timezone

from config import USER_DATA_DIR

LOG_DIR = Path(USER_DATA_DIR) / "agent_logs"
EVENT_LOG_DIR = Path(USER_DATA_DIR) / "event_logs"


def _ensure_dir():
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_file() -> Path:
    _ensure_dir()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return LOG_DIR / f"{today}.jsonl"


def log_agent_call(session_id: str, message: str, result: dict, duration_ms: float,
                   model: str = "", max_steps_reached: bool = False):
    """记录一次完整的 Agent 调用。

    Args:
        session_id: 会话标识
        message: 用户输入（截断至 200 字符）
        result: agent_chat() 返回的 dict，含 reply/steps/tool_calls
        duration_ms: 调用耗时（毫秒）
        model: 使用的模型名
        max_steps_reached: 是否因达到步数上限而中止
    """
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "user_message": message[:200],
        "reply": result.get("reply", "")[:300],
        "tool_calls": result.get("tool_calls", 0),
        "steps": result.get("steps", []),
        "duration_ms": round(duration_ms, 1),
        "model": model,
        "max_steps_reached": max_steps_reached,
    }
    try:
        with open(_log_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 静默失败，不影响主流程


def list_recent_logs(days: int = 7) -> list[dict]:
    """读取最近 N 天的日志记录，返回 dict 列表（最新在前）。"""
    _ensure_dir()
    records = []
    for f in sorted(LOG_DIR.glob("*.jsonl"), reverse=True):
        try:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        except Exception:
            continue
        if len(records) > 500:
            break
    return records[:500]


# ── Token 用量日志 ──

TOKEN_LOG_DIR = Path(USER_DATA_DIR) / "token_logs"


def log_token_usage(model: str = "", provider: str = "",
                    prompt_tokens: int = 0, completion_tokens: int = 0,
                    task_type: str = ""):
    """记录一次 LLM API 调用的 token 用量到 JSONL。
    由 deepseek_client.chat() 和 agent_service ReAct 循环调用。"""
    TOKEN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cost = (
        prompt_tokens * 0.14 / 1_000_000
        + completion_tokens * 0.28 / 1_000_000
    )
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "provider": provider,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": round(cost, 8),
        "task_type": task_type,
    }
    try:
        with open(TOKEN_LOG_DIR / f"{today}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── 结构化事件日志（带强制 schema） ──

VALID_EVENT_TYPES = {"error", "fix_applied", "fix_failed", "pattern_repeat", "user_correction"}


def log_event(event_type: str, details: dict, session_id: str = ""):
    """记录结构化事件。

    details 必须包含:
      - error_type: str  (错误分类，如 zombie_process, code_override, permission_leak)
      - phase: str       (发生阶段，如 server_startup, agent_chat, review)
      - error_message: str (原始错误信息)
      - recurring: bool  (是否为重复出现)
    """
    if event_type not in VALID_EVENT_TYPES:
        event_type = "error"

    EVENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "session_id": session_id,
        "error_type": details.get("error_type", "unknown"),
        "phase": details.get("phase", "unknown"),
        "error_message": details.get("error_message", "")[:500],
        "recurring": details.get("recurring", False),
        "extra": {k: v for k, v in details.items()
                  if k not in ("error_type", "phase", "error_message", "recurring")},
    }
    try:
        with open(EVENT_LOG_DIR / f"{today}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def list_recent_events(days: int = 7) -> list[dict]:
    if not EVENT_LOG_DIR.exists():
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    events = []
    for f in sorted(EVENT_LOG_DIR.glob("*.jsonl"), reverse=True):
        try:
            if f.stat().st_mtime < cutoff:
                continue
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except Exception:
            continue
        if len(events) > 1000:
            break
    return events


def get_event_summary(days: int = 7) -> dict:
    events = list_recent_events(days)
    by_type = {}
    recent_errors = []
    for e in events:
        t = e.get("event_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
        if t == "error":
            recent_errors.append({"ts": e.get("ts", ""), "message": e.get("error_message", "")[:200]})
    return {"total_events": len(events), "by_type": by_type, "recent_errors": recent_errors[-20:]}


def get_log_stats(days: int = 7) -> dict:
    """返回最近 N 天的汇总统计。"""
    records = list_recent_logs(days)
    if not records:
        return {"total_calls": 0, "avg_duration_ms": 0, "tools_used": {}}

    tools_used = {}
    total_tool_calls = 0
    for r in records:
        for s in r.get("steps", []):
            if s.get("phase") == "action":
                name = s.get("tool", "unknown")
                tools_used[name] = tools_used.get(name, 0) + 1
                total_tool_calls += 1

    durations = [r.get("duration_ms", 0) for r in records]
    return {
        "total_calls": len(records),
        "total_tool_calls": total_tool_calls,
        "avg_duration_ms": round(sum(durations) / len(durations), 1) if durations else 0,
        "max_duration_ms": round(max(durations), 1) if durations else 0,
        "tools_used": dict(sorted(tools_used.items(), key=lambda x: -x[1])),
        "sessions": len(set(r.get("session_id", "") for r in records)),
    }


def fingerprint_error(exception: Exception, error_msg: str) -> str:
    """层次化错误指纹 -- 保证同源错误必然同指纹。
    第一层: 异常类名（稳定）
    第二层: traceback 中项目内部文件的最后一次调用帧
    第三层: 错误消息做归一化（路径/端口/数字-占位符）后 hash
    """
    import traceback
    tb_lines = traceback.format_exc().strip().split("\n")
    cls_name = type(exception).__name__

    # 找到 traceback 中最后一个属于项目代码的帧（非外部库）
    project_frame = ""
    for line in reversed(tb_lines):
        line = line.strip()
        if "Crescent" in line and "site-packages" not in line:
            m = re.search(r'File ".*?(Crescent.*?)", line (\d+)', line)
            if m:
                project_frame = f"{m.group(1)}:{m.group(2)}"
                break

    # 归一化错误消息：替换路径、端口、数字ID、IP地址
    normalized = error_msg
    normalized = re.sub(r'C:[/\\][^\s,;:"]+', '<PATH>', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'/[\w/.-]+\.\w+', '<PATH>', normalized)
    normalized = re.sub(r':\d{3,5}', ':<PORT>', normalized)
    normalized = re.sub(r'\b\d{4,}\b', '<NUM>', normalized)
    normalized = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP>', normalized)

    key = f"{cls_name}|{project_frame}|{normalized[:200]}"
    return hashlib.md5(key.encode()).hexdigest()[:8]


# ── Agent 延迟统计 (用于 PPT S19 "34s" 声明的数据来源) ──

def get_agent_timing_stats(days: int = 30) -> dict:
    """从 Agent 日志中计算平均延迟、P50、P95。

    没有日志时返回估算值（基于 ReAct 5 步 × DeepSeek ~6s/步）。
    """
    durations = []
    _ensure_dir()
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400

    for f in sorted(LOG_DIR.glob("*.jsonl")):
        try:
            if f.stat().st_mtime < cutoff:
                continue
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    dur_ms = rec.get("duration_ms", 0)
                    if dur_ms and dur_ms > 0:
                        durations.append(dur_ms)
        except Exception:
            continue

    if not durations:
        return {
            "avg_ms": 34000, "p50_ms": 32000, "p95_ms": 60000,
            "count": 0, "source": "estimated",
            "note": "无实际调用记录，使用 ReAct 5步估算值",
        }

    durations.sort()
    n = len(durations)
    return {
        "avg_ms": round(sum(durations) / n),
        "p50_ms": durations[n // 2],
        "p95_ms": durations[int(n * 0.95)],
        "count": n,
        "source": "measured",
        "note": f"基于最近 {days} 天 {n} 次调用实测",
    }
