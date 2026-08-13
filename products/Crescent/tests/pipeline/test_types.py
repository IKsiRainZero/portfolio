from __future__ import annotations
from dataclasses import asdict
from services.pipeline.types import (
    StepInput, StepOutput, StepSpec, PipelineSpec, TraceEvent, IngestedDocument
)


def test_step_output_defaults():
    out = StepOutput(step_name="S1", status="ok", data={"x": 1}, confidence=0.9)
    assert out.human_question is None
    assert asdict(out)["step_name"] == "S1"


def test_pipeline_spec_version_bump():
    ps = PipelineSpec(steps=[StepSpec(step_name="S1", enabled=True)])
    assert ps.version == 1


def test_ingested_document_minimal():
    doc = IngestedDocument(
        id="abc", text="hello", source_url="http://x.com",
        source_type="webpage", tags=["test"]
    )
    assert doc.credibility_score == 0.5  # default
    assert doc.structured is None
    assert doc.embedding is None


def test_trace_event_serializable():
    import json
    ev = TraceEvent(
        event_id="ev1", timestamp="2026-06-28T12:00:00Z",
        event_type="step_start", step_name="S3", data={"url": "x"}
    )
    d = asdict(ev)
    assert json.dumps(d)  # no exception
