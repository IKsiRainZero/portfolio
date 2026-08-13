from __future__ import annotations
from services.pipeline.protocols import Step
from services.pipeline.types import StepInput, StepOutput, StepSpec, PipelineSpec
from services.pipeline.orchestrator import Orchestrator
from services.pipeline.trace_logger import TraceLogger


class _MockStep:
    """模拟一个总是返回 ok 的 Step"""
    name = "mock"

    def run(self, input: StepInput) -> StepOutput:
        return StepOutput(step_name=self.name, status="ok", data={"ran": True}, confidence=1.0)

    def can_skip(self, input: StepInput) -> bool:
        return False


class _MockFailingStep:
    name = "bad"

    def run(self, input: StepInput) -> StepOutput:
        return StepOutput(step_name=self.name, status="error", data={"error": "fail"}, confidence=0.0)

    def can_skip(self, input: StepInput) -> bool:
        return False


def test_orchestrator_runs_steps_in_order():
    trace = TraceLogger()
    orch = Orchestrator(steps=[_MockStep()], trace_logger=trace)
    spec = PipelineSpec(steps=[StepSpec(step_name="mock", enabled=True)])
    result = orch.run(query="test", spec=spec)
    assert result["status"] == "ok"
    assert result["outputs"]["mock"]["ran"] is True
    assert len(trace.events) >= 2  # step_start + step_end


def test_orchestrator_skips_disabled_steps():
    trace = TraceLogger()
    orch = Orchestrator(steps=[_MockStep()], trace_logger=trace)
    spec = PipelineSpec(steps=[StepSpec(step_name="mock", enabled=False)])
    result = orch.run(query="test", spec=spec)
    assert result["status"] == "ok"
    assert "mock" not in result["outputs"]


class _MockHumanStep:
    name = "human"

    def run(self, input: StepInput) -> StepOutput:
        return StepOutput(step_name="human", status="needs_human", data={}, human_question="are you sure?", confidence=0.5)

    def can_skip(self, input: StepInput) -> bool:
        return False


def test_orchestrator_stops_on_needs_human():
    trace = TraceLogger()
    orch = Orchestrator(steps=[_MockHumanStep()], trace_logger=trace)
    spec = PipelineSpec(steps=[StepSpec(step_name="human", enabled=True)])
    result = orch.run(query="test", spec=spec)
    assert result["status"] == "needs_human"
    assert result["question"] == "are you sure?"


def test_orchestrator_stops_on_unregistered_step():
    trace = TraceLogger()
    orch = Orchestrator(steps=[], trace_logger=trace)
    spec = PipelineSpec(steps=[StepSpec(step_name="nonexistent", enabled=True)])
    result = orch.run(query="test", spec=spec)
    assert result["status"] == "error"


def test_orchestrator_stops_on_error():
    trace = TraceLogger()
    orch = Orchestrator(steps=[_MockFailingStep(), _MockStep()], trace_logger=trace)
    spec = PipelineSpec(steps=[
        StepSpec(step_name="bad", enabled=True),
        StepSpec(step_name="mock", enabled=True),
    ])
    result = orch.run(query="test", spec=spec)
    assert result["status"] == "error"
    assert "mock" not in result["outputs"]  # never reached
# ── T1: S1→Orchestrator 集成 ──

class MockS1Step:
    """模拟 S1：返回一个自定义 PipelineSpec。"""
    name = "S1"

    def can_skip(self, input):
        return False

    def run(self, input):
        new_spec = PipelineSpec(steps=[
            StepSpec(step_name="S1", enabled=True),
            StepSpec(step_name="S2", enabled=False),
            StepSpec(step_name="S3_search", enabled=True, config={"max_results": 3}),
        ])
        return StepOutput(
            step_name="S1", status="ok",
            data={"pipeline_spec": new_spec, "token_usage": {}},
            confidence=0.85,
        )


class MockS2Step:
    name = "S2"

    def can_skip(self, input):
        return False

    def run(self, input):
        return StepOutput(step_name="S2", status="ok", data={"scanned": True})


class MockS3SearchStep:
    name = "S3_search"

    def can_skip(self, input):
        return False

    def run(self, input):
        return StepOutput(
            step_name="S3_search", status="ok",
            data={"results": [{"url": "https://x.com", "title": "X", "snippet": "..."}], "count": 1},
        )


def test_orchestrator_consumes_s1_pipeline_spec():
    orch = Orchestrator(
        steps=[MockS1Step(), MockS2Step(), MockS3SearchStep()],
        trace_logger=TraceLogger(),
    )
    spec = PipelineSpec(steps=[
        StepSpec(step_name="S1", enabled=True),
        StepSpec(step_name="S2", enabled=True),
        StepSpec(step_name="S3_search", enabled=True),
    ])
    result = orch.run(query="test", spec=spec)
    assert result["status"] == "ok"
    outputs = result["outputs"]
    assert "S1" in outputs
    assert "S2" not in outputs
    assert "S3_search" in outputs
    assert outputs["S3_search"]["count"] == 1
    spec_changed_events = [
        t for t in result["trace"]
        if t.get("event_type") == "spec_changed"
    ]
    assert len(spec_changed_events) >= 1


def test_orchestrator_spec_not_changed_when_s1_no_pipeline_spec():
    class MockS1NoSpec:
        name = "S1"
        def can_skip(self, input):
            return False
        def run(self, input):
            return StepOutput(step_name="S1", status="ok", data={})

    orch = Orchestrator(
        steps=[MockS1NoSpec(), MockS2Step()],
        trace_logger=TraceLogger(),
    )
    spec = PipelineSpec(steps=[
        StepSpec(step_name="S1", enabled=True),
        StepSpec(step_name="S2", enabled=True),
    ])
    result = orch.run(query="test", spec=spec)
    assert result["status"] == "ok"
    assert "S2" in result["outputs"]
