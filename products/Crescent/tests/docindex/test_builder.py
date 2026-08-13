from __future__ import annotations
import os
import tempfile
from pathlib import Path
from services.docindex.builder import build_index


def _create_docs_tree(base: str):
    """创建模拟 docs/ 目录结构。"""
    # 已有文档
    os.makedirs(os.path.join(base, "checkpoints"), exist_ok=True)
    Path(os.path.join(base, "checkpoints", "2026-06-29-pipeline.md")).write_text(
        "# Pipeline Status\n11 commits, 69 tests pass.", encoding="utf-8"
    )
    os.makedirs(os.path.join(base, "superpowers", "specs"), exist_ok=True)
    Path(os.path.join(base, "superpowers", "specs", "docindex-design.md")).write_text(
        "# DocIndex Design\nTwo-level page table mapping.", encoding="utf-8"
    )
    Path(os.path.join(base, "README.md")).write_text(
        "# Docs\nThis is the docs folder.", encoding="utf-8"
    )


def test_build_index_creates_l1_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = os.path.join(tmpdir, "docs")
        index_dir = os.path.join(tmpdir, ".index")
        _create_docs_tree(docs_dir)

        result = build_index(docs_root=docs_dir, index_root=index_dir)

        assert result["created_l1"] == 3
        assert result["created_l2"] == 3
        assert result["skipped"] == 0

        # 验证 L1 文件被创建
        l1_dir = os.path.join(index_dir, "L1")
        assert os.path.isdir(l1_dir)
        l1_files = os.listdir(l1_dir)
        assert len(l1_files) == 3

        # 验证 L2 桩文件被创建
        l2_dir = os.path.join(index_dir, "L2")
        assert os.path.isdir(l2_dir)
        l2_files = os.listdir(l2_dir)
        assert len(l2_files) == 3


def test_build_index_skips_existing_l1():
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = os.path.join(tmpdir, "docs")
        index_dir = os.path.join(tmpdir, ".index")
        _create_docs_tree(docs_dir)

        # 第一次构建
        result1 = build_index(docs_root=docs_dir, index_root=index_dir)
        assert result1["created_l1"] == 3

        # 第二次构建 — 全部跳过
        result2 = build_index(docs_root=docs_dir, index_root=index_dir)
        assert result2["created_l1"] == 0
        assert result2["skipped"] == 3


def test_build_index_no_docs_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = build_index(
            docs_root=os.path.join(tmpdir, "nonexistent"),
            index_root=os.path.join(tmpdir, ".index"),
        )
        assert result["created_l1"] == 0
        assert "error" in result


def test_build_index_l1_entry_has_auto_covers():
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = os.path.join(tmpdir, "docs")
        index_dir = os.path.join(tmpdir, ".index")
        _create_docs_tree(docs_dir)

        build_index(docs_root=docs_dir, index_root=index_dir)

        # 读取生成的 L1 文件，验证内容
        from services.docindex.store import L1Store
        l1_dir = os.path.join(index_dir, "L1")
        for fname in os.listdir(l1_dir):
            entry = L1Store.read(os.path.join(l1_dir, fname))
            assert entry is not None
            assert len(entry.doc) > 0
            assert entry.depth in (1, 2, 3)
            assert len(entry.tags) > 0  # 至少从路径中提取了一个 tag
            assert len(entry.summary) > 0  # 摘要不为空
