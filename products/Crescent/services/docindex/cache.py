from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field
from collections import OrderedDict


@dataclass
class CacheEntry:
    query: str
    result: dict
    created_at: float = field(default_factory=time.time)


class CacheManager:
    """LRU + TTL 查询缓存。容量满时淘汰最久未用条目，超过 ttl_days 自动过期。"""

    def __init__(self, max_size: int = 20, ttl_days: float = 7.0, cache_path: str | None = None):
        self._max_size = max_size
        self._ttl_seconds = ttl_days * 86400.0
        self._cache_path = cache_path
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

    def get(self, query: str) -> dict | None:
        query = query.strip().lower()
        entry = self._cache.get(query)
        if entry is None:
            return None
        # TTL 过期检查 (ttl_seconds == 0 表示立即过期)
        if self._ttl_seconds == 0 or (time.time() - entry.created_at) > self._ttl_seconds:
            del self._cache[query]
            return None
        # LRU: 移到末尾 (最近使用)
        self._cache.move_to_end(query)
        return dict(entry.result)  # 返回副本

    def put(self, query: str, result: dict):
        query = query.strip().lower()
        if query in self._cache:
            del self._cache[query]
        elif len(self._cache) >= self._max_size:
            # 淘汰最久未用 (OrderedDict 第一个)
            self._cache.popitem(last=False)
        self._cache[query] = CacheEntry(query=query, result=result)

    def mark_dirty(self, doc_path: str):
        """标记某文档相关的所有缓存条目为失效。"""
        doc_path = doc_path.replace("\\", "/")
        to_remove = []
        for query, entry in self._cache.items():
            result_doc = entry.result.get("doc", "")
            if result_doc.replace("\\", "/") == doc_path:
                to_remove.append(query)
        for q in to_remove:
            del self._cache[q]

    def save(self):
        """持久化到 JSON 文件。"""
        if not self._cache_path:
            return
        os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
        data = {}
        for query, entry in self._cache.items():
            data[query] = {
                "result": entry.result,
                "created_at": entry.created_at,
            }
        with open(self._cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self):
        """从 JSON 文件加载缓存。过期条目自动跳过。"""
        if not self._cache_path or not os.path.exists(self._cache_path):
            return
        try:
            with open(self._cache_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        now = time.time()
        loaded = 0
        for query, entry_data in data.items():
            created = entry_data.get("created_at", 0)
            if self._ttl_seconds == 0 or (now - created) > self._ttl_seconds:
                continue
            self._cache[query] = CacheEntry(
                query=query,
                result=entry_data.get("result", {}),
                created_at=created,
            )
            loaded += 1
            if loaded >= self._max_size:
                break
