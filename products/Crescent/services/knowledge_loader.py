"""知识库数据加载与搜索"""
import json
from pathlib import Path
from config import DATA_DIR

KNOWLEDGE_DIR = DATA_DIR / "knowledge"


def list_sets():
    """返回所有可用知识库列表"""
    sets = []
    if KNOWLEDGE_DIR.exists():
        for f in sorted(KNOWLEDGE_DIR.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                meta = data.get("meta", {})
                sets.append({
                    "id": f.stem,
                    "display_name": meta.get("display_name", f.stem),
                    "description": meta.get("description", ""),
                    "item_count": sum(len(s.get("items", [])) for s in data.get("sections", [])),
                })
            except (json.JSONDecodeError, KeyError):
                continue
    return sets


def load_set(set_id):
    """加载指定知识库的完整内容，返回扁平化的 item 列表"""
    file_path = KNOWLEDGE_DIR / f"{set_id}.json"
    if not file_path.exists():
        return None

    data = json.loads(file_path.read_text(encoding="utf-8"))
    items = []
    for section in data.get("sections", []):
        section_title = section.get("title", "")
        for item in section.get("items", []):
            item["section"] = section_title
            items.append(item)

    return {
        "meta": data.get("meta", {}),
        "items": items,
    }


def search(query):
    """跨所有知识库搜索"""
    results = []
    query_lower = query.lower()
    for set_info in list_sets():
        set_data = load_set(set_info["id"])
        if not set_data:
            continue
        for item in set_data["items"]:
            # 搜索标题、问题、答案、内容
            searchable = " ".join([
                item.get("title", ""),
                item.get("question", ""),
                item.get("answer", ""),
                item.get("content", ""),
                item.get("explanation", ""),
            ]).lower()
            if query_lower in searchable:
                item["_set_id"] = set_info["id"]
                item["_set_name"] = set_info["display_name"]
                results.append(item)
    return results
