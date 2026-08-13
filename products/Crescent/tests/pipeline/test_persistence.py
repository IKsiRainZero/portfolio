from __future__ import annotations
import json
import os
import tempfile
from services.pipeline.persistence import PersistenceStep
from services.pipeline.types import StepInput, StepOutput, PipelineSpec, StepSpec, IngestedDocument


def test_persistence_step_writes_trace_and_decision():
    step = PersistenceStep()
    docs = [
        IngestedDocument(
            id="d1", text="Attention is all you need",
            source_url="https://arxiv.org/abs/1706.03762",
            source_type="arxiv", credibility_score=0.85,
            tags=["transformer"], fetched_at="2026-06-29T00:00:00Z",
        )
    ]
    plan = {"minimal_action": {"what": "读论文", "why": "理解基础", "steps": [], "refs": []}}

    with tempfile.TemporaryDirectory() as tmpdir:
        step._output_dir = tmpdir
        output = step.run(StepInput(
            query="transformer是什么",
            previous_outputs={
                "S3_fetch": {"status": "ok", "documents": docs},
                "S4": {"status": "ok", "documents": docs, "conflicts": []},
                "S5": {"status": "ok", "plan": plan, "sources": []},
            },
            pipeline_spec=PipelineSpec(steps=[StepSpec(step_name="S7", enabled=True)]),
        ))

        assert output.status == "ok"
        data = output.data
        assert "trace_path" in data
        assert "decision_path" in data
        assert os.path.exists(data["trace_path"])
        assert os.path.exists(data["decision_path"])

        with open(data["trace_path"], encoding="utf-8") as f:
            trace = json.load(f)
        assert "pipeline" in trace
        assert trace["pipeline"]["query"] == "transformer是什么"

        with open(data["decision_path"], encoding="utf-8") as f:
            decision = json.load(f)
        assert "plan" in decision
        assert decision["plan"]["minimal_action"]["what"] == "读论文"


def test_persistence_step_can_skip():
    step = PersistenceStep()
    assert step.can_skip(StepInput(query="test")) is False
