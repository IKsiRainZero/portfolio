"""共享过滤: 敏感词、去重、schema 校验、drift detection。全部硬编码。"""
import re

# 基础敏感词列表 — 新闻标题/摘要中出现这些词则过滤
_SENSITIVE_PATTERNS = [
    r"裸[体聊]",
    r"赌博",
    r"色情",
    r"\b(?:porn|xxx|sex)\b",
]

_SENSITIVE_RE = re.compile("|".join(_SENSITIVE_PATTERNS), re.IGNORECASE)


def filter_sensitive(items: list[dict], text_fields: tuple = ("title", "summary")) -> list[dict]:
    """过滤包含敏感词的条目。返回通过过滤的条目列表。"""
    clean = []
    for item in items:
        hit = False
        for field in text_fields:
            text = str(item.get(field, ""))
            if _SENSITIVE_RE.search(text):
                hit = True
                break
        if not hit:
            clean.append(item)
    return clean


def deduplicate(items: list[dict], key_field: str = "title") -> list[dict]:
    """按 key_field 去重，保留首次出现。"""
    seen = set()
    result = []
    for item in items:
        key = str(item.get(key_field, "")).strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def validate_schema(data: list[dict], required_fields: tuple) -> tuple:
    """校验每条数据的必填字段。返回 (通过列表, 错误列表)。"""
    passed = []
    errors = []
    for i, item in enumerate(data):
        missing = [f for f in required_fields if not item.get(f)]
        if missing:
            errors.append(f"item[{i}] missing: {missing}")
        else:
            passed.append(item)
    return passed, errors


def detect_drift(data: list[dict], cached_hash: str) -> bool:
    """对比当前数据 schema hash 与缓存是否一致。返回 True=漂移。"""
    if not cached_hash:
        return False
    import hashlib, json
    if not data:
        return False
    keys = sorted(data[0].keys())
    current_hash = hashlib.sha256(json.dumps(keys).encode()).hexdigest()[:16]
    return current_hash != cached_hash
