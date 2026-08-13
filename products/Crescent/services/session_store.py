"""Session 持久化 — 对话历史存盘，跨页面/跨 agent 共享上下文
+ Context Bubbles — 结构化跨 Agent 记忆共享

文件: data/user_data/sessions/<session_id>.json
Bubbles: data/user_data/context_bubbles.jsonl
每个 session 存储: persona, messages, created, last_accessed
每个 bubble 存储: session_id, persona, timestamp, topic, question, insight, key_terms
"""

import json
import time
from pathlib import Path
from config import DATA_DIR

SESSION_DIR = DATA_DIR / "user_data" / "sessions"
BUBBLE_FILE = DATA_DIR / "user_data" / "context_bubbles.jsonl"
MAX_BUBBLES = 200  # keep file bounded, rotate old entries


def _ensure_dir():
    SESSION_DIR.mkdir(parents=True, exist_ok=True)


def save(session_id: str, persona: str, messages: list):
    """保存 session 历史到磁盘（messages 为可序列化的 dict 列表）"""
    _ensure_dir()
    filepath = SESSION_DIR / f"{session_id}.json"
    existing = {}
    if filepath.exists():
        try:
            existing = json.loads(filepath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    data = {
        "session_id": session_id,
        "persona": persona or existing.get("persona", ""),
        "created": existing.get("created", time.time()),
        "last_accessed": time.time(),
        "messages": messages,
    }
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load(session_id: str):
    """从磁盘加载 session，返回 dict 或 None"""
    _ensure_dir()
    filepath = SESSION_DIR / f"{session_id}.json"
    if not filepath.exists():
        return None
    try:
        return json.loads(filepath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def get_recent_context(persona: str = "", limit: int = 1):
    """获取最近的对话上下文摘要，用于跨 agent 通信。

    为避免 token 爆炸，仅返回简短的话题摘要（≤150 字），不传完整消息。
    """
    _ensure_dir()
    sessions = []
    for f in sorted(SESSION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        # 仅取其他 persona 的会话
        if data.get("persona", "") == persona:
            continue
        sessions.append(data)
        if len(sessions) >= limit:
            break

    now = time.time()
    recent = [s for s in sessions if now - s.get("last_accessed", 0) < 1800][:limit]
    if not recent:
        return ""

    topics = []
    for s in recent:
        msgs = s.get("messages", [])
        # 只取最后 2 条用户消息，提取关键话题
        user_msgs = [m.get("content", "") for m in msgs if m.get("role") == "user"][-2:]
        for content in user_msgs:
            if content:
                short = content[:80].replace("\n", " ")
                topics.append(short)

    if not topics:
        return ""

    summary = "；".join(topics[:2])
    if len(summary) > 150:
        summary = summary[:150] + "…"
    return f"最近话题: {summary}"


def list_sessions(limit: int = 50):
    """列出所有 session 摘要列表（按最近访问时间排序），供 UI 选择"""
    _ensure_dir()
    result = []
    for f in sorted(SESSION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            msgs = data.get("messages", [])
            snippet = ""
            for m in msgs:
                if m.get("role") == "user":
                    snippet = m.get("content", "")[:60]
                    break
            result.append({
                "session_id": data.get("session_id", f.stem),
                "persona": data.get("persona", ""),
                "created": data.get("created", 0),
                "last_accessed": data.get("last_accessed", 0),
                "message_count": len(msgs),
                "snippet": snippet,
            })
        except (json.JSONDecodeError, OSError):
            continue
        if len(result) >= limit:
            break
    return result


# ══════════════════════════════════════════════════════════════
# Context Bubbles — 结构化跨 Agent 记忆共享
# ==============================================================
# Bubble 结构:
#   { session_id, persona, timestamp, topic, question, insight,
#     key_terms[], status: "active"|"stale" }
# 每个 bubble 代表一次有意义的问答交互，供其他 Agent 角色引用。
# ══════════════════════════════════════════════════════════════

def save_bubble(session_id: str, persona: str, topic: str,
                question: str, insight: str, key_terms: list = None):
    """将一次有意义的问答提取为上下文气泡，供其他 Agent 角色引用。"""
    _ensure_dir()
    bubble = {
        "session_id": session_id,
        "persona": persona,
        "timestamp": time.time(),
        "topic": topic[:80],
        "question": question[:120],
        "insight": insight[:200],
        "key_terms": (key_terms or [])[:5],
        "status": "active",
    }
    # 追加到 JSONL，rotate 旧条目
    existing = []
    if BUBBLE_FILE.exists():
        try:
            for line in BUBBLE_FILE.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    existing.append(json.loads(line))
        except (json.JSONDecodeError, OSError):
            existing = []
    existing.append(bubble)
    # 只保留最近 MAX_BUBBLES 条
    if len(existing) > MAX_BUBBLES:
        existing = existing[-MAX_BUBBLES:]
    BUBBLE_FILE.write_text(
        "\n".join(json.dumps(b, ensure_ascii=False) for b in existing) + "\n",
        encoding="utf-8"
    )


def get_bubbles(exclude_persona: str = "", limit: int = 5,
                max_age_seconds: int = 7200) -> list:
    """获取最近的有意义上下文气泡，按新鲜度分层返回。

    exclude_persona: 排除当前角色（避免"我听同桌说…同桌自己"的循环）
    返回按 recency 排序的 bubble 列表，过期气泡标记为 stale。
    """
    if not BUBBLE_FILE.exists():
        return []
    bubbles = []
    now = time.time()
    try:
        for line in BUBBLE_FILE.read_text(encoding="utf-8").strip().split("\n"):
            if not line.strip():
                continue
            b = json.loads(line)
            if b.get("persona", "") == exclude_persona:
                continue
            age = now - b.get("timestamp", 0)
            if age > max_age_seconds:
                continue
            # 新鲜度分层
            if age < 1800:       # < 30 min → hot
                b["_recency"] = "hot"
            elif age < 7200:     # < 2 hr → warm
                b["_recency"] = "warm"
            else:
                b["_recency"] = "cold"
            bubbles.append(b)
    except (json.JSONDecodeError, OSError):
        return []
    bubbles.sort(key=lambda b: b.get("timestamp", 0), reverse=True)
    return bubbles[:limit]


def get_bubble_context(exclude_persona: str = "", limit: int = 3) -> str:
    """生成跨 Agent 上下文注入文本，供 system prompt 使用。

    与旧的 get_recent_context() 不同，返回结构化信息而非原始消息截断。
    """
    bubbles = get_bubbles(exclude_persona=exclude_persona, limit=limit)
    if not bubbles:
        return ""

    parts = []
    for b in bubbles:
        p_label = {"deskmate": "同桌", "teacher": "老师", "interviewer": "面试官"}.get(
            b.get("persona", ""), b.get("persona", "")
        )
        recency_label = {"hot": "刚刚", "warm": "不久前", "cold": "之前"}.get(
            b.get("_recency", ""), ""
        )
        # 结构化信息
        entry = (
            f"[{recency_label}与{p_label}聊过] "
            f"话题：{b.get('topic', '')}。"
            f"用户问：{b.get('question', '')}。"
            f"{p_label}答：{b.get('insight', '')}"
        )
        parts.append(entry)

    return "\n".join(parts)


def delete_session(session_id: str):
    """删除指定 session 文件"""
    _ensure_dir()
    filepath = SESSION_DIR / f"{session_id}.json"
    if filepath.exists():
        filepath.unlink()
        return True
    return False
