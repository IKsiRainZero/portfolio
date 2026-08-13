"""四层记忆引擎 — Hot/Warm/Cold/Archive 压缩、结晶、归档、RAG唤醒"""
import json
from datetime import datetime, timezone
from pathlib import Path
from config import USER_DATA_DIR, CHROMA_PATH, CHROMA_COLLECTION

MEMORY_DIR = USER_DATA_DIR / "memory"
HOT_DIR = MEMORY_DIR / "hot"
WARM_DIR = MEMORY_DIR / "warm"
COLD_DIR = MEMORY_DIR / "cold"

for d in [HOT_DIR, WARM_DIR, COLD_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ── Hot 层：最近 N 次会话的原始摘要 ──

def save_hot_session(session_id: str, summary: dict):
    """保存一次会话的摘要到 Hot 层"""
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "session_id": session_id,
        "saved_at": now,
        "error_count": summary.get("error_count", 0),
        "tool_calls": summary.get("tool_calls", 0),
        "duration_ms": summary.get("duration_ms", 0),
        "token_usage": summary.get("token_usage", {}),
        "harness_issues": summary.get("harness_issues", []),
        "errors": summary.get("errors", []),
    }
    fname = f"{now[:19].replace(':', '-')}_{session_id[:12]}.json"
    (HOT_DIR / fname).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def list_hot_sessions(limit: int = 20) -> list[dict]:
    """列出 Hot 层会话，最新在前"""
    files = sorted(HOT_DIR.glob("*.json"), reverse=True)[:limit]
    sessions = []
    for f in files:
        try:
            sessions.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, IOError):
            pass
    return sessions


def hot_count() -> int:
    return len(list(HOT_DIR.glob("*.json")))


# ── Warm 层：周摘要 ──

def should_generate_warm() -> bool:
    """Hot > 10 条时触发"""
    return hot_count() > 10


def get_oldest_hot_sessions(n: int = 5) -> list[dict]:
    """获取最旧的 N 条 Hot 会话（用于压缩）"""
    files = sorted(HOT_DIR.glob("*.json"))[:n]
    sessions = []
    for f in files:
        try:
            sessions.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, IOError):
            pass
    return sessions


def save_warm_summary(week_label: str, summary: dict):
    """保存周摘要到 Warm 层。先写 Warm 文件成功 → 再按 manifest 删 Hot。"""
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "week": week_label,
        "created_at": now,
        "sessions_compressed": summary.get("sessions_compressed", 0),
        "error_patterns": summary.get("error_patterns", []),
        "key_metrics": summary.get("key_metrics", {}),
        "improvements_tried": summary.get("improvements_tried", []),
        "raw_text": summary.get("raw_text", ""),
    }
    # 1. 先把要删除的 Hot 文件列表写入 manifest
    n = summary.get("sessions_compressed", 0)
    files_to_remove = sorted(HOT_DIR.glob("*.json"))[:n]
    manifest = {"files": [str(f) for f in files_to_remove], "target_week": week_label, "created": now}
    manifest_path = WARM_DIR / f"{week_label}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # 2. 写 Warm 摘要文件
    (WARM_DIR / f"{week_label}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    # 3. Warm 写入成功后，按 manifest 删除 Hot 文件
    for f in files_to_remove:
        f.unlink(missing_ok=True)
    # 4. 删除 manifest
    manifest_path.unlink(missing_ok=True)

    # 清理孤儿 manifest（上次崩溃遗留）
    for mf in WARM_DIR.glob("*.manifest.json"):
        try:
            mdata = json.loads(mf.read_text(encoding="utf-8"))
            target = WARM_DIR / f"{mdata.get('target_week', '')}.json"
            if target.exists():
                for fpath in mdata.get("files", []):
                    Path(fpath).unlink(missing_ok=True)
            mf.unlink(missing_ok=True)
        except (json.JSONDecodeError, IOError):
            mf.unlink(missing_ok=True)


def list_warm_summaries(limit: int = 10) -> list[dict]:
    files = sorted(WARM_DIR.glob("*.json"), reverse=True)[:limit]
    summaries = []
    for f in files:
        try:
            summaries.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, IOError):
            pass
    return summaries


def warm_count() -> int:
    return len(list(WARM_DIR.glob("*.json")))


# ── Cold 层：月结晶 ──

def should_generate_cold() -> bool:
    """Warm > 4 周时触发"""
    return warm_count() > 4


def get_oldest_warm_summaries(n: int = 4) -> list[dict]:
    """获取最旧的 N 条 Warm 摘要"""
    files = sorted(WARM_DIR.glob("*.json"))[:n]
    summaries = []
    for f in files:
        try:
            summaries.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, IOError):
            pass
    return summaries


def save_cold_crystallization(month_label: str, crystallization: dict):
    """保存月结晶到 Cold 层，删除对应的 Warm 文件"""
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "month": month_label,
        "created_at": now,
        "rules": crystallization.get("rules", []),
        "methodologies": crystallization.get("methodologies", []),
        "weeks_merged": crystallization.get("weeks_merged", 0),
        "raw_text": crystallization.get("raw_text", ""),
    }
    (COLD_DIR / f"{month_label}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    # 删除已结晶的 Warm 文件
    files_to_remove = sorted(WARM_DIR.glob("*.json"))[:crystallization.get("weeks_merged", 0)]
    for f in files_to_remove:
        f.unlink(missing_ok=True)


def list_cold_rules() -> list[dict]:
    """列出 Cold 层的所有规则"""
    rules = []
    for f in sorted(COLD_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for rule in data.get("rules", []):
                rule["_source_month"] = data.get("month", "")
                rule["_created_at"] = data.get("created_at", "")
                rules.append(rule)
        except (json.JSONDecodeError, IOError):
            pass
    return rules


def cold_count() -> int:
    return len(list(COLD_DIR.glob("*.json")))


# ── Archive 层：ChromaDB 归档 ──

def archive_to_chromadb(rule: dict, status: str = "archived"):
    """将一条规则存入 ChromaDB（Archive 层）。status: archived | fix_failed"""
    try:
        import chromadb
        from services.rag_service import get_embedding
    except ImportError:
        print("[review_memory] ChromaDB not available, skipping archive")
        return False

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(name=CHROMA_COLLECTION)

    text = f"{rule.get('rule', '')}\n来源: {rule.get('_source_month', '')}\n状态: {status}"
    doc_id = f"archive_{rule.get('_source_month', 'unknown')}_{hash(text) % 100000}"
    embedding = get_embedding(text)

    collection.upsert(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[{
            "source_type": "review_archive",
            "status": status,
            "month": rule.get("_source_month", ""),
            "archived_at": datetime.now(timezone.utc).isoformat(),
        }],
    )
    return True


def search_archive(query: str, k: int = 5) -> list[dict]:
    """RAG 唤醒：从 ChromaDB Archive 中检索相关历史规则"""
    try:
        import chromadb
        from services.rag_service import get_embedding
    except ImportError:
        return []

    if not CHROMA_PATH.exists():
        return []

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        collection = client.get_collection(name=CHROMA_COLLECTION)
    except Exception:
        return []

    embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[embedding],
        n_results=k,
        where={"source_type": "review_archive"},
    )
    docs = []
    if results and results.get("documents"):
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            docs.append({"text": doc, "metadata": meta})
    return docs


# ── 规则生命周期跟踪 ──

def mark_rule_triggered(rule_text: str):
    """标记一条 Cold 规则被触发（用于判断是否该 Archive）"""
    for f in COLD_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            modified = False
            for rule in data.get("rules", []):
                if rule.get("rule", "")[:80] == rule_text[:80]:
                    rule["last_triggered"] = datetime.now(timezone.utc).isoformat()
                    rule["trigger_count"] = rule.get("trigger_count", 0) + 1
                    modified = True
            if modified:
                f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except (json.JSONDecodeError, IOError):
            pass


def find_stale_rules(weeks: int = 4) -> list[dict]:
    """找出连续 N 周未触发的规则（候选进入 Archive）"""
    cutoff = datetime.now(timezone.utc).timestamp() - weeks * 7 * 86400
    stale = []
    for rule in list_cold_rules():
        last = rule.get("last_triggered", rule.get("_created_at", ""))
        try:
            last_ts = datetime.fromisoformat(last).timestamp()
            if last_ts < cutoff:
                stale.append(rule)
        except (ValueError, TypeError, OSError):
            pass
    return stale


# ── 记忆层状态 ──

def get_memory_state() -> dict:
    return {
        "hot_sessions": hot_count(),
        "warm_summaries": warm_count(),
        "cold_crystallizations": cold_count(),
        "total_rules": len(list_cold_rules()),
        "state_at": datetime.now(timezone.utc).isoformat(),
    }
