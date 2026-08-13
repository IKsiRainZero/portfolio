"""临时题库存储 — temp_exercises.json 统一读写"""
import json
from datetime import datetime
from pathlib import Path
from config import USER_DATA_DIR, DATA_DIR

TEMP_FILE = USER_DATA_DIR / "temp_exercises.json"
_TYPES = ("mcq", "coding", "flashcards")


def _empty():
    return {t: [] for t in _TYPES}


def load():
    if not TEMP_FILE.exists():
        return _empty()
    try:
        data = json.loads(TEMP_FILE.read_text(encoding="utf-8"))
        return {t: data.get(t, []) for t in _TYPES}
    except (json.JSONDecodeError, IOError):
        return _empty()


def _save(data):
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add(item):
    """添加单道题，自动分配 id"""
    ex_type = item["type"]
    if ex_type not in _TYPES:
        raise ValueError(f"type 必须是 mcq/coding/flashcards 之一，收到 '{ex_type}'")

    data = load()
    idx = len(data[ex_type])
    item["id"] = f"temp_{ex_type}_{datetime.now().strftime('%H%M%S')}_{idx}"
    item["_source"] = item.get("_source", "agent_saved")
    item["_created"] = datetime.now().isoformat()
    data[ex_type].append(item)
    _save(data)
    return item


def merge(exercises_by_type):
    """批量合并题目（import_knowledge 用）"""
    data = load()
    for ex_type in _TYPES:
        items = exercises_by_type.get(ex_type, [])
        for item in items:
            item.setdefault("id", f"temp_{ex_type}_{datetime.now().strftime('%H%M%S')}_{len(data[ex_type])}")
            item.setdefault("_source", "ai_generated")
            item.setdefault("_created", datetime.now().isoformat())
        data[ex_type].extend(items)
    _save(data)
    return sum(len(v) for v in data.values())


def dump():
    return load()


def clear():
    TEMP_FILE.unlink(missing_ok=True)


def classify(keep_ids):
    """将指定题目从临时库迁移到正式题库，返回 moved 计数"""
    data = load()
    moved = {}
    for ex_type in _TYPES:
        items = data.get(ex_type, [])
        if not items:
            moved[ex_type] = 0
            continue
        keep = keep_ids.get(ex_type, [])
        to_keep = [items[i] for i in keep] if keep else items[:]
        if not to_keep:
            moved[ex_type] = 0
            continue

        for item in to_keep:
            item.pop("_source", None)
            item.pop("_created", None)

        target_file = DATA_DIR / "exercises" / f"{ex_type}.json"
        existing = []
        if target_file.exists():
            try:
                existing = json.loads(target_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                pass

        max_id = max([e.get("id", 0) for e in existing], default=0)
        for idx, item in enumerate(to_keep):
            item["id"] = max_id + idx + 1

        existing.extend(to_keep)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        moved[ex_type] = len(to_keep)

    clear()
    return moved
