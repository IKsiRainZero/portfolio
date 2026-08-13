"""审查记录存取 + 文件快照 + 触发状态管理"""
from __future__ import annotations
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from config import USER_DATA_DIR

REVIEWS_FILE = USER_DATA_DIR / "reviews.json"
SNAPSHOTS_DIR = USER_DATA_DIR / "review_snapshots"
STATE_FILE = USER_DATA_DIR / "review_state.json"


# ── 审查记录 ──

def load():
    if not REVIEWS_FILE.exists():
        return {"meta": {}, "reviews": []}
    try:
        return json.loads(REVIEWS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"meta": {}, "reviews": []}


def _save(data):
    """原子写入：先写临时文件，再 os.replace 保证完整性。
    如果进程崩溃，只剩 .tmp 文件不会破坏主数据。
    """
    REVIEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = REVIEWS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, REVIEWS_FILE)


def add_review(review: dict) -> str:
    data = load()
    now = datetime.now(timezone.utc).isoformat()
    review_id = f"review_{now[:10]}_{len(data['reviews']) + 1:03d}"
    record = {
        "review_id": review_id,
        "created_at": now,
        "summary": review.get("summary", ""),
        "findings": review.get("findings", []),
        "suggestions": review.get("suggestions", []),
        "token_usage": review.get("token_usage", {}),
        "self_check": review.get("self_check", {}),
        "memory_state": review.get("memory_state", {}),
    }
    data["reviews"].append(record)
    data["meta"] = {"last_updated": now, "total_reviews": len(data["reviews"])}
    _save(data)
    return review_id


def list_reviews(limit: int = 20) -> list:
    reviews = load().get("reviews", [])
    return sorted(reviews, key=lambda r: r.get("created_at", ""), reverse=True)[:limit]


def get_review(review_id: str) -> dict | None:
    for r in load().get("reviews", []):
        if r.get("review_id") == review_id:
            return r
    return None


def update_suggestion_status(review_id: str, suggestion_index: int, status: str):
    data = load()
    for r in data["reviews"]:
        if r.get("review_id") == review_id:
            suggestions = r.get("suggestions", [])
            if 0 <= suggestion_index < len(suggestions):
                suggestions[suggestion_index]["status"] = status
                suggestions[suggestion_index]["status_updated_at"] = datetime.now(timezone.utc).isoformat()
            break
    _save(data)


def get_stats() -> dict:
    data = load()
    reviews = data.get("reviews", [])
    total_suggestions = sum(len(r.get("suggestions", [])) for r in reviews)
    applied = sum(1 for r in reviews for s in r.get("suggestions", []) if s.get("status") == "applied")
    rolled_back = sum(1 for r in reviews for s in r.get("suggestions", []) if s.get("status") == "rolled_back")
    rejected = sum(1 for r in reviews for s in r.get("suggestions", []) if s.get("status") == "rejected")
    return {
        "total_reviews": len(reviews),
        "total_suggestions": total_suggestions,
        "applied": applied,
        "rolled_back": rolled_back,
        "rejected": rejected,
        "pending": total_suggestions - applied - rolled_back - rejected,
        "effectiveness": round((applied - rolled_back) / max(total_suggestions, 1), 2),
    }


# ── 文件快照 ──

def save_snapshot(filepath: str) -> str:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(filepath)
    if not src.exists():
        return ""
    snapshot_id = f"{src.name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    dest = SNAPSHOTS_DIR / snapshot_id
    shutil.copy2(src, dest)
    return snapshot_id


def restore_snapshot(snapshot_id: str, target_path: str) -> bool:
    src = SNAPSHOTS_DIR / snapshot_id
    if not src.exists():
        return False
    shutil.copy2(src, target_path)
    return True


def list_snapshots() -> list:
    if not SNAPSHOTS_DIR.exists():
        return []
    return sorted(
        [{"id": f.name, "created": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()}
         for f in SNAPSHOTS_DIR.iterdir() if f.is_file()],
        key=lambda x: x["created"], reverse=True
    )


# ── 触发状态 (会话计数器) ──

def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {"session_count": 0, "last_review_at": "", "last_auto_trigger_at": ""}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"session_count": 0, "last_review_at": "", "last_auto_trigger_at": ""}


def _save_state(state: dict):
    """原子写入，与 _save() 保持一致"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def increment_session_count() -> int:
    state = _load_state()
    state["session_count"] = state.get("session_count", 0) + 1
    _save_state(state)
    return state["session_count"]


def get_session_count() -> int:
    return _load_state().get("session_count", 0)


def reset_session_count():
    state = _load_state()
    state["session_count"] = 0
    state["last_review_at"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)


def should_auto_review(max_sessions: int = 10, max_days: int = 7) -> bool:
    """检查是否应该自动触发审查"""
    state = _load_state()
    count = state.get("session_count", 0)
    if count >= max_sessions:
        return True
    last_review = state.get("last_review_at", "")
    if last_review:
        try:
            last_dt = datetime.fromisoformat(last_review)
            days_since = (datetime.now(timezone.utc) - last_dt).days
            if days_since >= max_days and count > 0:
                return True
        except (ValueError, TypeError):
            pass
    return False


def mark_review_triggered():
    state = _load_state()
    state["session_count"] = 0
    now = datetime.now(timezone.utc).isoformat()
    state["last_review_at"] = now
    state["last_auto_trigger_at"] = now
    _save_state(state)
