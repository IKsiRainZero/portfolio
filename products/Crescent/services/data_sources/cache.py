"""JSON 文件缓存: TTL + stale-while-revalidate + schema_hash"""
from __future__ import annotations
import json
import time
from pathlib import Path

_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def set_cache_dir(path: Path) -> None:
    """重设缓存目录（测试用）。"""
    global _CACHE_DIR
    _CACHE_DIR = path
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(name: str) -> Path:
    safe = name.replace("/", "_").replace("\\", "_")
    return _CACHE_DIR / f"{safe}.json"


def load_cache(name: str) -> dict | None:
    """加载缓存。返回 None 如果文件不存在。调用方自行判断 TTL。"""
    p = _cache_path(name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_cache(name: str, data: list[dict], schema_hash: str, ttl: int) -> None:
    """写入缓存。"""
    p = _cache_path(name)
    payload = {
        "data": data,
        "fetched_at": time.time(),
        "ttl": ttl,
        "schema_hash": schema_hash,
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_stale_data(name: str) -> dict | None:
    """读取过期缓存（降级用）。忽略 TTL，有数据就返回。"""
    cached = load_cache(name)
    if cached and cached.get("data"):
        return cached
    return None
