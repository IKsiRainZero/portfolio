"""方法论卡片存储 — insights.json 统一读写"""
import json
from datetime import datetime
from config import DATA_DIR

INSIGHTS_FILE = DATA_DIR / "knowledge" / "insights.json"


def load():
    if not INSIGHTS_FILE.exists():
        return {"meta": {}, "cards": []}
    try:
        return json.loads(INSIGHTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"meta": {}, "cards": []}


def _save(data):
    INSIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    INSIGHTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_cards(cards, source_info=None):
    """批量新增方法论卡片，自动去重。返回 (added_count, total_count)"""
    data = load()
    existing_titles = {c.get("title", "").strip().lower() for c in data.get("cards", [])}
    now = datetime.now().isoformat()
    added = 0

    for c in cards:
        title = c.get("title", "").strip()
        if not title or title.lower() in existing_titles:
            continue
        card_id = f"insight_{now[:10]}_{len(data.get('cards', [])) + added + 1:03d}"
        card = {
            "id": card_id,
            "type": "methodology",
            "title": title,
            "source": c.get("source", source_info or {}),
            "what": c.get("what", ""),
            "applicable_to": c.get("applicable_to", []),
            "excluded_approaches": c.get("excluded_approaches", []),
            "confidence": c.get("confidence", 0.7),
            "quality_score": int(c.get("confidence", 0.7) * 10),
            "created_at": now,
            "last_used": None,
            "use_count": 0,
            "tags": c.get("tags", []),
        }
        data.setdefault("cards", []).append(card)
        existing_titles.add(title.lower())
        added += 1

    data["meta"] = {
        "domain": "insights",
        "display_name": "方法论卡片",
        "description": "从论文和实践中提取的系统设计方法论",
        "last_updated": now,
    }

    _save(data)
    return added, len(data.get("cards", []))
