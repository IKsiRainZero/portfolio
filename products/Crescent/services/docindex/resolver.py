from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from services.docindex.store import L1Store, L2Store, L1Entry, L2Entry
from services.docindex.cache import CacheManager
from pathlib import Path

# 仓库根目录 (resolver.py → docindex → services → Crescent → repo_root)
_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_DEFAULT_INDEX = str(_REPO_ROOT / "docs" / ".index")


@dataclass
class SearchResult:
    doc: str
    l1_summary: str
    depth: int
    covers: list[str]
    tags: list[str]
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "doc": self.doc,
            "l1_summary": self.l1_summary,
            "depth": self.depth,
            "covers": self.covers,
            "tags": self.tags,
            "score": self.score,
        }


class Resolver:
    """渐进式查询引擎：search → L1 → L2 → original。"""

    def __init__(self, index_root: str = _DEFAULT_INDEX, cache_path: str | None = None):
        self._index_root = index_root
        self._l1_dir = os.path.join(index_root, "L1")
        self._l2_dir = os.path.join(index_root, "L2")
        self._cache_path = cache_path or os.path.join(index_root, "cache.json")
        self._cache = CacheManager(max_size=20, ttl_days=7, cache_path=self._cache_path)
        self._cache.load()
        self._dirty_docs: set[str] = set()

    def search(self, query: str) -> list[SearchResult]:
        """按关键词搜索 L1 索引，返回匹配的文档列表（按相关度排序）。"""
        q = query.strip().lower()

        # 检查缓存
        cached = self._cache.get(q)
        if cached is not None:
            # 缓存命中但需过滤已标记为 dirty 的文档
            items = cached.get("items", [])
            results = [_dict_to_search_result(item) for item in items]
            if self._dirty_docs:
                results = [r for r in results if r.doc not in self._dirty_docs]
            return results

        results = self._search_l1(q)
        # 缓存结果
        self._cache.put(q, {"items": [r.to_dict() for r in results]})
        return results

    def _search_l1(self, query_lower: str) -> list[SearchResult]:
        """扫描所有 L1 文件，匹配 covers + tags + summary 字段。"""
        if not os.path.isdir(self._l1_dir):
            return []

        results = []
        query_words = _tokenize(query_lower)

        for fname in os.listdir(self._l1_dir):
            if not fname.endswith(".md"):
                continue
            filepath = os.path.join(self._l1_dir, fname)
            entry = L1Store.read(filepath)
            if entry is None:
                continue
            # 跳过已标记为 dirty 的文档
            if entry.doc in self._dirty_docs:
                continue

            score = _score_match(query_lower, query_words, entry)
            if score > 0:
                results.append(SearchResult(
                    doc=entry.doc,
                    l1_summary=entry.summary,
                    depth=entry.depth,
                    covers=entry.covers,
                    tags=entry.tags,
                    score=score,
                ))

        return sorted(results, key=lambda r: r.score, reverse=True)

    def get_l2(self, doc_path: str) -> L2Entry | None:
        """获取某文档的 L2 详细摘要。"""
        from services.docindex.store import _doc_path_to_slug
        slug = _doc_path_to_slug(doc_path)
        filepath = os.path.join(self._l2_dir, slug)
        return L2Store.read(filepath)

    def get_original_path(self, doc_path: str) -> str:
        """返回原文档的路径。"""
        return doc_path

    def mark_dirty(self, doc_path: str):
        """标记某文档已更新，清除相关缓存并从搜索结果中排除。"""
        normalized = doc_path.replace("\\", "/")
        self._dirty_docs.add(normalized)
        self._cache.mark_dirty(doc_path)

    def save_cache(self):
        """持久化缓存到磁盘。"""
        self._cache.save()


def _tokenize(text: str) -> list[str]:
    """简单中文+英文分词。"""
    # 提取中文字符序列 + 英文单词
    tokens = []
    # 英文词
    en_words = re.findall(r"[a-zA-Z0-9]+", text)
    tokens.extend(w.lower() for w in en_words)
    # 中文双字+三元组
    chinese = re.findall(r"[一-鿿]+", text)
    for segment in chinese:
        # 单字也保留
        tokens.append(segment)
        # 双字组合
        for i in range(len(segment) - 1):
            tokens.append(segment[i:i+2])
    return tokens


def _score_match(query_lower: str, query_words: list[str], entry: L1Entry) -> float:
    """计算查询与 L1 条目的匹配得分。"""
    score = 0.0

    # covers 精确匹配权重最高
    for cover in entry.covers:
        cover_lower = cover.lower()
        # 完整查询匹配 cover
        if query_lower in cover_lower or cover_lower in query_lower:
            score += 3.0
        else:
            # 部分词匹配
            for word in query_words:
                if word in cover_lower:
                    score += 1.0

    # tags 匹配
    for tag in entry.tags:
        tag_lower = tag.lower()
        if tag_lower in query_lower or query_lower in tag_lower:
            score += 2.5
        for word in query_words:
            if word in tag_lower:
                score += 0.8

    # summary 匹配
    summary_lower = entry.summary.lower()
    if query_lower in summary_lower:
        score += 1.0
    for word in query_words:
        if word in summary_lower:
            score += 0.3

    return score


def _dict_to_search_result(d: dict) -> SearchResult:
    return SearchResult(
        doc=d.get("doc", ""),
        l1_summary=d.get("l1_summary", ""),
        depth=d.get("depth", 1),
        covers=d.get("covers", []),
        tags=d.get("tags", []),
        score=d.get("score", 0.0),
    )
