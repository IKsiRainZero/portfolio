from __future__ import annotations
import tempfile
import os
from pathlib import Path
from services.docindex.store import L1Entry, L2Entry, L1Store, L2Store, _parse_frontmatter, _serialize_frontmatter


SAMPLE_L1_CONTENT = """---
doc: docs/checkpoints/2026-06-29-v4-pipeline-status.md
depth: 2
covers:
  - v4管道完成了什么
  - v4管道还剩什么没做
  - SerpAPI怎么接入
tags: [pipeline, v4, checkpoint]
---

# v4 管道实现状态 & 剩余工作
摘要：11 commits, 69 tests pass, 6/7 steps done。
剩余：SerpAPI切换(已完成)、真实E2E测试(已完成)、前端UI(未开始)、S6/S7(未开始)。
"""

SAMPLE_L2_CONTENT = """---
doc: docs/checkpoints/2026-06-29-v4-pipeline-status.md
updated: 2026-06-29
---

## 已完成模块清单
| 模块 | 文件 | 测试 |
|------|------|------|
| Foundation | protocols.py | ✅ |

## 剩余工作
### 高
- [x] 搜索API切换
- [ ] 前端UI

## 已知问题
- S1生成了PipelineSpec但orchestrator没消费它
"""


# ── Frontmatter parsing ──

def test_parse_frontmatter_extracts_yaml():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_L1_CONTENT)
        f.flush()
        meta, body = _parse_frontmatter(f.name)
    os.unlink(f.name)

    assert meta["doc"] == "docs/checkpoints/2026-06-29-v4-pipeline-status.md"
    assert meta["depth"] == 2
    assert meta["covers"] == ["v4管道完成了什么", "v4管道还剩什么没做", "SerpAPI怎么接入"]
    assert meta["tags"] == ["pipeline", "v4", "checkpoint"]
    assert "v4 管道实现状态" in body
    assert "---" not in body  # frontmatter delimiter stripped


def test_parse_frontmatter_no_yaml_returns_empty_meta():
    content = "# Just a heading\nSome body text."
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(content)
        f.flush()
        meta, body = _parse_frontmatter(f.name)
    os.unlink(f.name)

    assert meta == {}
    assert "Some body text" in body


def test_serialize_frontmatter_roundtrip():
    meta = {
        "doc": "docs/foo.md",
        "depth": 1,
        "covers": ["问题A", "问题B"],
        "tags": ["a", "b"],
    }
    body = "# Title\nSummary here."
    output = _serialize_frontmatter(meta, body)
    # Parsing the output should recover the same data
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(output)
        f.flush()
        meta2, body2 = _parse_frontmatter(f.name)
    os.unlink(f.name)

    assert meta2["doc"] == "docs/foo.md"
    assert meta2["depth"] == 1
    assert meta2["covers"] == ["问题A", "问题B"]
    assert "Summary here" in body2


# ── L1Store ──

def test_l1_read_parses_entry():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_L1_CONTENT)
        f.flush()
        entry = L1Store.read(f.name)
    os.unlink(f.name)

    assert isinstance(entry, L1Entry)
    assert entry.doc == "docs/checkpoints/2026-06-29-v4-pipeline-status.md"
    assert entry.depth == 2
    assert len(entry.covers) == 3
    assert entry.tags == ["pipeline", "v4", "checkpoint"]
    assert "11 commits" in entry.summary


def test_l1_read_missing_file_returns_none():
    entry = L1Store.read("/nonexistent/path.md")
    assert entry is None


def test_l1_write_and_read_roundtrip(tmp_path):
    entry = L1Entry(
        doc="docs/test.md",
        depth=1,
        covers=["测试问题"],
        tags=["test"],
        summary="这是一个测试文档的摘要。",
    )
    L1Store.write(entry, str(tmp_path))
    # L1Store.write creates <dir>/<slug>.md
    files = list(Path(tmp_path).glob("*.md"))
    assert len(files) == 1

    loaded = L1Store.read(str(files[0]))
    assert loaded.doc == entry.doc
    assert loaded.depth == entry.depth
    assert loaded.covers == entry.covers
    assert loaded.summary == entry.summary


# ── L2Store ──

def test_l2_read_parses_entry():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_L2_CONTENT)
        f.flush()
        entry = L2Store.read(f.name)
    os.unlink(f.name)

    assert isinstance(entry, L2Entry)
    assert entry.doc == "docs/checkpoints/2026-06-29-v4-pipeline-status.md"
    assert entry.updated == "2026-06-29"
    assert "已完成模块清单" in entry.summary
    assert "已知问题" in entry.summary


def test_l2_read_missing_file_returns_none():
    entry = L2Store.read("/nonexistent/path.md")
    assert entry is None


def test_l2_write_and_read_roundtrip(tmp_path):
    entry = L2Entry(
        doc="docs/test.md",
        updated="2026-06-29",
        summary="## 已完成\n- 项目A 完成\n\n## 已知问题\n- Bug X 待修复",
    )
    L2Store.write(entry, str(tmp_path))
    files = list(Path(tmp_path).glob("*.md"))
    assert len(files) == 1

    loaded = L2Store.read(str(files[0]))
    assert loaded.doc == entry.doc
    assert loaded.updated == entry.updated
    assert "Bug X 待修复" in loaded.summary


# ── Slug generation ──

def test_doc_path_to_slug():
    from services.docindex.store import _doc_path_to_slug
    assert _doc_path_to_slug("docs/checkpoints/2026-06-29-v4-pipeline-status.md") \
        == "checkpoints_2026-06-29-v4-pipeline-status.md"
    assert _doc_path_to_slug("docs/superpowers/specs/foo.md") \
        == "superpowers_specs_foo.md"
    assert _doc_path_to_slug("docs/README.md") == "README.md"
