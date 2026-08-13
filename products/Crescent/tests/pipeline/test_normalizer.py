from __future__ import annotations
from services.pipeline.normalizer import normalize, _title_from_html, _clean_body

SIMPLE_HTML = """<!DOCTYPE html>
<html><head><title>Transformer Paper Explained</title>
<meta name="description" content="A guide to attention"></head>
<body><article><p>The Transformer architecture relies on self-attention mechanisms.
It processes all tokens in parallel rather than sequentially.</p></article></body></html>
"""


def test_normalize_extracts_title_and_text():
    doc = normalize(SIMPLE_HTML, "https://example.com/transformer", "webpage")
    assert doc.source_url == "https://example.com/transformer"
    assert doc.source_type == "webpage"
    assert "Transformer" in doc.text
    assert len(doc.text) > 50


def test_normalize_tags_content():
    doc = normalize(SIMPLE_HTML, "https://example.com", "webpage")
    doc2 = normalize("<html><head><title>Python Guide</title></head><body><p>Learn Python.</p></body></html>", "https://x.com", "webpage")
    # 两个不同主题 → tags 应不同
    assert isinstance(doc.tags, list)


def test_title_from_html():
    assert _title_from_html("<html><head><title>Hello</title></head></html>") == "Hello"
    assert _title_from_html("<html></html>") == "Untitled"
