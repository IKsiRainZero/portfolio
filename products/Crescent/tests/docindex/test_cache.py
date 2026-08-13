from __future__ import annotations
import json
import time
import os
from services.docindex.cache import CacheManager


def test_cache_put_and_get_hit():
    cm = CacheManager(max_size=20, ttl_days=7, cache_path=None)
    cm.put("v4管道进度", {"level": "L1", "doc": "docs/checkpoints/foo.md", "summary": "11 commits"})
    result = cm.get("v4管道进度")
    assert result is not None
    assert result["doc"] == "docs/checkpoints/foo.md"
    assert result["level"] == "L1"


def test_cache_miss_returns_none():
    cm = CacheManager(max_size=20, ttl_days=7, cache_path=None)
    assert cm.get("never queried") is None


def test_cache_lru_eviction():
    cm = CacheManager(max_size=3, ttl_days=7, cache_path=None)
    for i in range(5):
        cm.put(f"query_{i}", {"result": i})
    # 前两个 (query_0, query_1) 应被淘汰
    assert cm.get("query_0") is None
    assert cm.get("query_1") is None
    assert cm.get("query_2") is not None
    assert cm.get("query_4") is not None
    assert len(cm._cache) == 3


def test_cache_lru_updates_on_get():
    cm = CacheManager(max_size=3, ttl_days=7, cache_path=None)
    cm.put("a", {"v": 1})
    cm.put("b", {"v": 2})
    cm.put("c", {"v": 3})
    # 访问 "a" 把它推到最近使用
    cm.get("a")
    # 插入新条目，应淘汰最久未使用的 "b"
    cm.put("d", {"v": 4})
    assert cm.get("a") is not None
    assert cm.get("b") is None
    assert cm.get("c") is not None
    assert cm.get("d") is not None


def test_cache_ttl_expiry():
    cm = CacheManager(max_size=20, ttl_days=0.0, cache_path=None)  # 立即过期
    cm.put("ephemeral", {"data": "x"})
    time.sleep(0.01)
    assert cm.get("ephemeral") is None


def test_cache_mark_dirty():
    cm = CacheManager(max_size=20, ttl_days=7, cache_path=None)
    cm.put("v4进度", {"doc": "docs/checkpoints/foo.md", "level": "L1"})
    cm.mark_dirty("docs/checkpoints/foo.md")
    # 涉及该文档的缓存条目应失效
    assert cm.get("v4进度") is None


def test_cache_mark_dirty_only_matching_doc():
    cm = CacheManager(max_size=20, ttl_days=7, cache_path=None)
    cm.put("q1", {"doc": "docs/a.md"})
    cm.put("q2", {"doc": "docs/b.md"})
    cm.mark_dirty("docs/a.md")
    assert cm.get("q1") is None
    assert cm.get("q2") is not None


def test_cache_persist_and_load(tmp_path):
    cache_file = str(tmp_path / "cache.json")
    cm = CacheManager(max_size=20, ttl_days=7, cache_path=cache_file)
    cm.put("q1", {"doc": "docs/a.md", "summary": "A"})
    cm.put("q2", {"doc": "docs/b.md", "summary": "B"})
    cm.save()

    # 确认文件存在且内容正确
    assert os.path.exists(cache_file)
    with open(cache_file, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 2

    # 新实例加载
    cm2 = CacheManager(max_size=20, ttl_days=7, cache_path=cache_file)
    cm2.load()
    result = cm2.get("q1")
    assert result is not None
    assert result["summary"] == "A"


def test_cache_load_missing_file_no_error(tmp_path):
    cache_file = str(tmp_path / "nonexistent.json")
    cm = CacheManager(max_size=20, ttl_days=7, cache_path=cache_file)
    cm.load()  # 不抛异常
    assert len(cm._cache) == 0


def test_cache_ttl_applied_on_load(tmp_path):
    # 写入一个过期条目
    cache_file = str(tmp_path / "cache.json")
    stale_data = {
        "old_query": {
            "result": {"doc": "x"},
            "created_at": time.time() - 999999,  # 很久以前
        }
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(stale_data, f)

    cm = CacheManager(max_size=20, ttl_days=7, cache_path=cache_file)
    cm.load()
    assert cm.get("old_query") is None  # TTL 过期
