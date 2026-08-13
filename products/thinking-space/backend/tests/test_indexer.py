import tempfile
from pathlib import Path
from app.services.indexer import TextExtractor, EntryMapper
from app.models import Layer

def test_extract_title_from_markdown():
    extractor = TextExtractor()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# 我的设计决策\n\n一些内容。")
        f.flush()
        result = extractor.extract(Path(f.name))
    assert result["title"] == "我的设计决策"
    assert "一些内容" in result["content"]

def test_extract_fallback_to_filename():
    extractor = TextExtractor()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("没有标题\n只是内容。")
        f.flush()
        result = extractor.extract(Path(f.name))
    assert result["title"] != ""

def test_entry_mapper_finds_social_layer():
    mapper = EntryMapper()
    layers = [Layer(id="l1", name="社会", level=5), Layer(id="l2", name="人", level=4)]
    layer_id, conf = mapper.map_to_layer("关于社会和文化的分析", layers)
    assert layer_id == "l1"
    assert conf == 30

def test_entry_mapper_returns_none_for_no_match():
    mapper = EntryMapper()
    layers = [Layer(id="l1", name="细胞", level=0)]
    layer_id, conf = mapper.map_to_layer("xyzzy nothing matches", layers)
    assert layer_id is None
    assert conf == 0
