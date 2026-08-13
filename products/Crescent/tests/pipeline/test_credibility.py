from __future__ import annotations
from unittest.mock import patch
from services.pipeline.credibility import (
    SourceRelationClassifier,
    SetLevelSufficiency,
    CredibilityFuserStep,
    classify_relation,
    assess_sufficiency,
    _build_relation_prompt,
    _build_sufficiency_prompt,
    CREDIBILITY_LABELS,
)
from services.pipeline.types import IngestedDocument, StepInput


def _make_doc(id: str, text: str, url: str = "", score: float = 0.5) -> IngestedDocument:
    return IngestedDocument(
        id=id,
        text=text,
        source_url=url or f"http://{id}.com",
        source_type="webpage",
        credibility_score=score,
        tags=[],
    )


# ── 单元测试：prompt 构建 ──

def test_build_relation_prompt_includes_docs():
    docs = [
        _make_doc("a", "Transformer uses self-attention."),
        _make_doc("b", "Transformer uses cross-attention."),
    ]
    prompt = _build_relation_prompt(docs)
    assert "self-attention" in prompt
    assert "cross-attention" in prompt
    assert "一致" in prompt


def test_build_sufficiency_prompt():
    docs = [_make_doc("a", "Fact A about X."), _make_doc("b", "Fact B about Y.")]
    prompt = _build_sufficiency_prompt(docs, "What is X?")
    assert "What is X" in prompt
    assert "充分" in prompt


# ── 集成测试：分类器 ──

@patch("services.pipeline.credibility.chat")
def test_classify_relation_consistent(mock_chat):
    mock_chat.return_value = (
        '{"label": "一致", "confidence": 0.9, "rationale": "Same claim"}',
        {"total_tokens": 50},
    )
    docs = [_make_doc("a", "X"), _make_doc("b", "X")]
    result = classify_relation(docs[0], docs[1])
    assert result["label"] == "一致"


@patch("services.pipeline.credibility.chat")
def test_classify_relation_contradicts(mock_chat):
    mock_chat.return_value = (
        '{"label": "矛盾", "confidence": 0.85, "rationale": "Opposite"}',
        {"total_tokens": 50},
    )
    result = classify_relation(_make_doc("a", "A"), _make_doc("b", "B"))
    assert result["label"] == "矛盾"


# ── 充分性判据 ──

@patch("services.pipeline.credibility.chat")
def test_assess_sufficiency(mock_chat):
    mock_chat.return_value = (
        '{"sufficient": false, "missing_dimensions": ["性能对比"], "confidence": 0.6, "rationale": "缺少实验数据"}',
        {"total_tokens": 60},
    )
    docs = [_make_doc("a", "Transformer is a neural architecture.")]
    result = assess_sufficiency(docs, "Transformer性能如何")
    assert result["sufficient"] is False
    assert "性能对比" in result["missing_dimensions"]


# ── Step 测试 ──

@patch("services.pipeline.credibility.chat")
def test_fuser_step(mock_chat):
    # 第一次调用是 classify_relation，第二次是 assess_sufficiency
    mock_chat.side_effect = [
        ('{"label": "一致", "confidence": 0.9, "rationale": "ok"}', {"total_tokens": 50}),
        ('{"sufficient": true, "missing_dimensions": [], "confidence": 0.8, "rationale": "covers topic"}', {"total_tokens": 60}),
    ]
    docs = [
        _make_doc("1", "The Transformer uses self-attention.", "http://a.com"),
        _make_doc("2", "Self-attention is key to Transformers.", "http://b.com"),
    ]
    step = CredibilityFuserStep(name="S4")
    input = StepInput(
        query="transformer attention",
        previous_outputs={"S3_fetch": {"documents": [d for d in docs]}},
        config={"operators": ["relation", "sufficiency"]},
    )
    output = step.run(input)
    assert output.status == "ok"
    assert "documents" in output.data
    # 可信度分数应该被更新了
    for d in output.data["documents"]:
        assert d.credibility_score != 0.5  # 不再是默认值


# ── 边缘情况：LLM 故障不崩溃 ──

@patch("services.pipeline.credibility.chat")
def test_classify_relation_llm_failure_returns_sane_default(mock_chat):
    mock_chat.side_effect = Exception("API timeout")
    result = classify_relation(_make_doc("a", "A"), _make_doc("b", "B"))
    assert result["label"] == "缺失"
    assert result["confidence"] == 0.0


@patch("services.pipeline.credibility.chat")
def test_classify_relation_invalid_json_returns_sane_default(mock_chat):
    mock_chat.return_value = ("not valid json at all", {"total_tokens": 10})
    result = classify_relation(_make_doc("a", "A"), _make_doc("b", "B"))
    assert result["label"] == "缺失"
    assert result["confidence"] == 0.0


@patch("services.pipeline.credibility.chat")
def test_assess_sufficiency_llm_failure_returns_sane_default(mock_chat):
    mock_chat.side_effect = Exception("API timeout")
    result = assess_sufficiency([_make_doc("a", "X")], "query")
    assert result["sufficient"] is False
    assert result["confidence"] == 0.0


def test_assess_sufficiency_empty_docs():
    result = assess_sufficiency([], "any query")
    assert result["sufficient"] is False
    assert "无任何文档" in result["missing_dimensions"]


# ── 单文档关系分类 ──

def test_source_relation_classifier_single_doc():
    classifier = SourceRelationClassifier()
    results = classifier.apply([_make_doc("a", "sole doc")])
    assert results == []


@patch("services.pipeline.credibility.chat")
def test_credibility_label_written_to_structured(mock_chat):
    mock_chat.return_value = (
        '{"label": "一致", "confidence": 0.9, "rationale": "ok"}',
        {"total_tokens": 50},
    )
    docs = [
        _make_doc("1", "X uses Y.", "http://a.com"),
        _make_doc("2", "Y is key to X.", "http://b.com"),
    ]
    step = CredibilityFuserStep(name="S4")
    input = StepInput(
        query="X and Y",
        previous_outputs={"S3_fetch": {"documents": docs}},
        config={"operators": ["relation"]},
    )
    output = step.run(input)
    for d in output.data["documents"]:
        assert d.structured is not None
        assert "credibility_label" in d.structured
        assert d.structured["credibility_label"] in CREDIBILITY_LABELS


# ── can_skip 测试 ──

def test_can_skip_empty_docs():
    step = CredibilityFuserStep(name="S4")
    input = StepInput(query="q", previous_outputs={})
    assert step.can_skip(input) is True


def test_can_skip_has_docs():
    step = CredibilityFuserStep(name="S4")
    input = StepInput(
        query="q",
        previous_outputs={"S3_fetch": {"documents": [_make_doc("1", "text")]}},
    )
    assert step.can_skip(input) is False


# ── CREDIBILITY_LABELS 常量 ──

def test_credibility_labels():
    assert "高可信" in CREDIBILITY_LABELS
    assert "存疑" in CREDIBILITY_LABELS
    assert "需人工核实" in CREDIBILITY_LABELS
    assert "孤立无佐证" in CREDIBILITY_LABELS
    assert len(CREDIBILITY_LABELS) == 4
