from __future__ import annotations
import os
import tempfile
from services.docindex.store import L1Store, L2Store, L1Entry, L2Entry
from services.docindex.resolver import Resolver, SearchResult


def _setup_index_dir(base_dir: str):
    """创建测试用的 L1/L2 索引文件。"""
    l1_dir = os.path.join(base_dir, "L1")
    l2_dir = os.path.join(base_dir, "L2")

    L1Store.write(L1Entry(
        doc="docs/checkpoints/pipeline-status.md",
        depth=2,
        covers=["v4管道完成了什么", "v4管道还剩什么没做", "SerpAPI怎么接入"],
        tags=["pipeline", "v4", "checkpoint"],
        summary="11 commits, 69 tests pass, 6/7 steps done。剩余：前端UI(未开始)、S6/S7(未开始)。",
    ), l1_dir)

    L1Store.write(L1Entry(
        doc="docs/superpowers/specs/docindex-design.md",
        depth=3,
        covers=["文档索引系统设计", "页表映射", "两级映射架构", "TLB cache"],
        tags=["docindex", "design", "architecture"],
        summary="仿OS页表两级映射(L1/L2)+TLB Cache，解决文档检索上下文污染问题。",
    ), l1_dir)

    L1Store.write(L1Entry(
        doc="docs/灵感/灵感-6.23.txt",
        depth=1,
        covers=["灵感记录"],
        tags=["灵感"],
        summary="日常灵感记录，不需要二级映射。",
    ), l1_dir)

    L2Store.write(L2Entry(
        doc="docs/checkpoints/pipeline-status.md",
        updated="2026-06-29",
        summary="## 已完成\n- Foundation ✅\n- S1 IntentParser ✅\n\n## 剩余\n- 前端UI 未开始\n- S6 未开始\n- S7 未开始",
    ), l2_dir)

    L2Store.write(L2Entry(
        doc="docs/superpowers/specs/docindex-design.md",
        updated="2026-06-29",
        summary="## 架构\nCache(LRU+TTL)→L1映射表→L2映射表→原文档\n\n## 文件格式\nL1: frontmatter + 一句话摘要\nL2: frontmatter + 结构化摘要",
    ), l2_dir)


def test_search_returns_matching_docs():
    with tempfile.TemporaryDirectory() as tmpdir:
        _setup_index_dir(tmpdir)
        resolver = Resolver(index_root=tmpdir)

        results = resolver.search("v4管道")
        assert len(results) >= 1
        assert any("pipeline" in r.doc for r in results)

        # 验证结果结构
        r = results[0]
        assert isinstance(r, SearchResult)
        assert r.depth in (1, 2, 3)
        assert len(r.covers) > 0
        assert len(r.l1_summary) > 0


def test_search_returns_empty_for_no_match():
    with tempfile.TemporaryDirectory() as tmpdir:
        _setup_index_dir(tmpdir)
        resolver = Resolver(index_root=tmpdir)
        results = resolver.search("zzz不存在的查询xyz")
        assert results == []


def test_search_matches_tags_and_covers():
    with tempfile.TemporaryDirectory() as tmpdir:
        _setup_index_dir(tmpdir)
        resolver = Resolver(index_root=tmpdir)

        # 按 tag 搜索
        results = resolver.search("docindex")
        assert len(results) >= 1
        assert any("docindex" in r.doc for r in results)

        # 按 covers 搜索
        results = resolver.search("两级映射")
        assert len(results) >= 1
        assert any("docindex" in r.doc for r in results)


def test_search_results_sorted_by_score():
    with tempfile.TemporaryDirectory() as tmpdir:
        _setup_index_dir(tmpdir)
        resolver = Resolver(index_root=tmpdir)

        results = resolver.search("v4管道还剩什么没做")
        # 精确匹配 covers 的应排在前面
        assert len(results) >= 1
        # pipeline-status 的 covers 包含 "v4管道还剩什么没做" → 应排第一
        assert "pipeline-status" in results[0].doc


def test_get_l2_returns_detail():
    with tempfile.TemporaryDirectory() as tmpdir:
        _setup_index_dir(tmpdir)
        resolver = Resolver(index_root=tmpdir)

        l2 = resolver.get_l2("docs/checkpoints/pipeline-status.md")
        assert l2 is not None
        assert l2.doc == "docs/checkpoints/pipeline-status.md"
        assert "已完成" in l2.summary


def test_get_l2_missing_returns_none():
    with tempfile.TemporaryDirectory() as tmpdir:
        _setup_index_dir(tmpdir)
        resolver = Resolver(index_root=tmpdir)

        l2 = resolver.get_l2("docs/nonexistent.md")
        assert l2 is None


def test_get_original_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        resolver = Resolver(index_root=tmpdir)
        path = resolver.get_original_path("docs/checkpoints/pipeline-status.md")
        assert path == "docs/checkpoints/pipeline-status.md"


def test_cache_integration():
    with tempfile.TemporaryDirectory() as tmpdir:
        _setup_index_dir(tmpdir)
        resolver = Resolver(index_root=tmpdir)

        # 第一次搜索 (cache miss)
        results1 = resolver.search("v4管道")
        assert len(results1) > 0

        # 第二次搜索 (cache hit) — 应返回相同结果
        results2 = resolver.search("v4管道")
        assert len(results2) == len(results1)

        # mark_dirty 后应 miss
        resolver.mark_dirty("docs/checkpoints/pipeline-status.md")
        results3 = resolver.search("v4管道")
        # 可能还有其他匹配，但 pipeline-status 不应在其中
        docs = [r.doc for r in results3]
        assert "docs/checkpoints/pipeline-status.md" not in docs


def test_cache_save_and_reload():
    with tempfile.TemporaryDirectory() as tmpdir:
        _setup_index_dir(tmpdir)
        cache_file = os.path.join(tmpdir, "cache.json")
        resolver = Resolver(index_root=tmpdir, cache_path=cache_file)

        results1 = resolver.search("v4管道")
        resolver.save_cache()

        # 新 resolver 加载缓存
        resolver2 = Resolver(index_root=tmpdir, cache_path=cache_file)
        # 先 load → 再 search，应从缓存命中
        results2 = resolver2.search("v4管道")
        assert len(results2) == len(results1)
