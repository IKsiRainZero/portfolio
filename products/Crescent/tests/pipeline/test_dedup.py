from __future__ import annotations
from services.pipeline.dedup import deduplicate
from services.pipeline.types import IngestedDocument


def _doc(id: str, text: str, url: str = "") -> IngestedDocument:
    return IngestedDocument(id=id, text=text, source_url=url or f"http://{id}.com", source_type="webpage", tags=[])


def test_deduplicate_removes_near_duplicates():
    docs = [
        _doc("1", "The transformer architecture uses self-attention mechanisms to process tokens in parallel."),
        _doc("2", "The transformer architecture uses self-attention mechanisms to process tokens in parallel."),  # near identical
        _doc("3", "Python is a high-level programming language for general-purpose programming."),
    ]
    result = deduplicate(docs)
    assert len(result) <= 2  # doc1 和 doc2 应合并为 1


def test_deduplicate_empty():
    assert deduplicate([]) == []
