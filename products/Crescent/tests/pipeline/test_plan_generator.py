from __future__ import annotations
from unittest.mock import patch
from services.pipeline.plan_generator import (
    PlanGeneratorStep,
    _build_plan_prompt,
    _parse_plan_response,
)
from services.pipeline.types import StepInput, IngestedDocument


def _make_doc(
    id: str, text: str, url: str = "", credibility_label: str = "高可信"
) -> IngestedDocument:
    return IngestedDocument(
        id=id,
        text=text,
        source_url=url or f"http://{id}.com",
        source_type="webpage",
        tags=[],
        credibility_score=0.8,
        structured={"credibility_label": credibility_label},
    )


# ── _build_plan_prompt ──


def test_build_plan_prompt():
    docs = [_make_doc("1", "Transformer excels at parallel processing.", "http://a.com")]
    prompt = _build_plan_prompt("transformer优势", docs)
    assert "transformer" in prompt.lower()
    assert "http://a.com" in prompt
    assert "高可信" in prompt


def test_build_plan_prompt_empty_docs():
    prompt = _build_plan_prompt("any query", [])
    assert "any query" in prompt or '"any query"' in prompt


def test_build_plan_prompt_multiple_docs():
    docs = [
        _make_doc("1", "Doc one content.", "http://a.com", "高可信"),
        _make_doc("2", "Doc two content.", "http://b.com", "存疑"),
    ]
    prompt = _build_plan_prompt("test query", docs)
    assert "http://a.com" in prompt
    assert "http://b.com" in prompt
    assert "高可信" in prompt
    assert "存疑" in prompt


# ── _parse_plan_response ──


def test_parse_plan_response_valid():
    import json

    resp = json.dumps({
        "minimal_action": {"what": "学习Transformer", "why": "核心架构", "steps": ["读论文", "写代码"]},
        "development_plan": {"phases": [{"name": "基础", "tasks": ["task1"]}]},
        "sources": [{"doc_id": "1", "key_claim": "...", "credibility": "高可信"}],
    })
    result = _parse_plan_response(resp)
    assert result is not None
    assert result["minimal_action"]["what"] == "学习Transformer"


def test_parse_plan_response_markdown_fence():
    import json

    inner = json.dumps({"minimal_action": {"what": "X", "why": "Y", "steps": []}, "development_plan": {"phases": []}, "sources": []})
    resp = f"```json\n{inner}\n```"
    result = _parse_plan_response(resp)
    assert result is not None
    assert result["minimal_action"]["what"] == "X"


def test_parse_plan_response_invalid():
    assert _parse_plan_response("not json") is None


def test_parse_plan_response_empty():
    assert _parse_plan_response("") is None


# ── PlanGeneratorStep ──


@patch("services.pipeline.plan_generator.chat")
def test_plan_generator_step(mock_chat):
    import json

    resp = json.dumps({
        "minimal_action": {"what": "X", "why": "Y", "steps": ["Z"]},
        "development_plan": {"phases": []},
        "sources": [],
    })
    mock_chat.return_value = (resp, {"total_tokens": 200})

    docs = [_make_doc("d1", "useful info", "http://s.com")]
    step = PlanGeneratorStep(name="S5")
    input_ = StepInput(
        query="test query",
        previous_outputs={
            "S4": {"documents": docs},
        },
    )
    output = step.run(input_)
    assert output.status == "ok"
    assert "plan" in output.data
    assert "sources" in output.data["plan"]
    assert output.confidence > 0


@patch("services.pipeline.plan_generator.chat")
def test_plan_generator_step_fallback_to_s3(mock_chat):
    """Fallback to S3_fetch when S4 not available."""
    import json

    resp = json.dumps({
        "minimal_action": {"what": "X", "why": "Y", "steps": []},
        "development_plan": {"phases": []},
        "sources": [],
    })
    mock_chat.return_value = (resp, {"total_tokens": 200})

    docs = [_make_doc("d1", "fallback info", "http://f.com")]
    step = PlanGeneratorStep(name="S5")
    input_ = StepInput(
        query="test query",
        previous_outputs={
            "S3_fetch": {"documents": docs},
        },
    )
    output = step.run(input_)
    assert output.status == "ok"
    assert "plan" in output.data


@patch("services.pipeline.plan_generator.chat")
def test_plan_generator_step_llm_failure(mock_chat):
    mock_chat.side_effect = Exception("API timeout")
    step = PlanGeneratorStep(name="S5")
    input_ = StepInput(
        query="query",
        previous_outputs={
            "S4": {"documents": [_make_doc("1", "info")]},
        },
    )
    output = step.run(input_)
    assert output.status == "error"
    assert "error" in output.data


@patch("services.pipeline.plan_generator.chat")
def test_plan_generator_step_parse_failure(mock_chat):
    mock_chat.return_value = ("not valid json at all", {"total_tokens": 50})
    step = PlanGeneratorStep(name="S5")
    input_ = StepInput(
        query="query",
        previous_outputs={
            "S4": {"documents": [_make_doc("1", "info")]},
        },
    )
    output = step.run(input_)
    assert output.status == "error"
    assert "parse" in output.data.get("error", "").lower()


def test_plan_generator_step_can_skip():
    step = PlanGeneratorStep(name="S5")
    input_ = StepInput(query="q", previous_outputs={})
    assert step.can_skip(input_) is False


@patch("services.pipeline.plan_generator.chat")
def test_plan_generator_step_empty_docs(mock_chat):
    import json

    resp = json.dumps({
        "minimal_action": {"what": "X", "why": "Y", "steps": [], "estimated_time": "N/A"},
        "development_plan": {"phases": []},
        "sources": [],
        "confidence": 0.5,
        "caveats": [],
    })
    mock_chat.return_value = (resp, {"total_tokens": 50})
    step = PlanGeneratorStep(name="S5")
    input_ = StepInput(query="q", previous_outputs={"S4": {"documents": []}})
    output = step.run(input_)
    # Empty docs should still generate a plan (just with no sources)
    assert output.status == "ok"
    assert output.data["plan"]["minimal_action"]["what"] == "X"
