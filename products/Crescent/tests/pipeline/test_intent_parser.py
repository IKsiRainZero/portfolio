from __future__ import annotations
from unittest.mock import patch, MagicMock
from services.pipeline.intent_parser import IntentParserStep, _parse_llm_response, build_intent_prompt
from services.pipeline.types import StepInput, PipelineSpec

SAMPLE_LLM_RESPONSE = """```json
{
  "steps": [
    {"step_name": "S1", "enabled": true, "config": {}},
    {"step_name": "S2", "enabled": true, "config": {"scan_depth": "full"}},
    {"step_name": "S3", "enabled": true, "config": {"max_results": 10}},
    {"step_name": "S4", "enabled": true, "config": {"operators": ["relation", "sufficiency"]}},
    {"step_name": "S5", "enabled": true, "config": {}},
    {"step_name": "S6", "enabled": false, "config": {}},
    {"step_name": "S7", "enabled": true, "config": {}}
  ]
}
```"""


def test_parse_llm_response():
    spec = _parse_llm_response(SAMPLE_LLM_RESPONSE, "test query")
    assert spec is not None
    assert len(spec.steps) == 7
    assert spec.steps[2].step_name == "S3"  # S3 enabled
    assert spec.steps[5].enabled is False   # S6 disabled


def test_parse_llm_response_invalid_json():
    assert _parse_llm_response("not json", "query") is None


def test_build_intent_prompt():
    prompt = build_intent_prompt("帮我调研Transformer注意力机制的最新进展")
    assert "Transformer" in prompt
    assert "PipelineSpec" in prompt


@patch("services.pipeline.intent_parser.chat")
def test_intent_parser_step(mock_chat):
    mock_chat.return_value = (SAMPLE_LLM_RESPONSE, {"total_tokens": 100})
    step = IntentParserStep(name="S1")
    output = step.run(StepInput(query="test"))
    assert output.status == "ok"
    assert "pipeline_spec" in output.data
