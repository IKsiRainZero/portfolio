"""可观测性基础设施测试。"""

from __future__ import annotations

import pytest

from observability.tracer import Metrics, Span, Trace
from orchestrator.context import SkillContext
from orchestrator.graph import Graph
from tests.orchestrator.test_graph import BaseSkill


class TestSpan:
    def test_span_lifecycle(self):
        s = Span(node="test")
        assert s.node == "test"
        assert s.error is None
        assert s.duration_ms == 0.0

        s.finish(tokens_in=100, tokens_out=50)
        assert s.tokens_in == 100
        assert s.tokens_out == 50
        assert s.duration_ms > 0

    def test_span_error(self):
        s = Span(node="failing")
        s.finish(error="something broke")
        assert s.error == "something broke"


class TestTrace:
    def test_trace_creates_spans(self):
        t = Trace()
        span = t.start_span("profile")
        span.finish(tokens_in=10, tokens_out=5)
        t.finish()

        assert len(t.spans) == 1
        assert t.spans[0].node == "profile"
        assert t.total_tokens == 15
        assert t.duration_ms > 0

    def test_trace_has_error_with_failed_span(self):
        t = Trace()
        s = t.start_span("bad_node")
        s.finish(error="fail")
        t.finish()

        assert t.has_error


class TestMetrics:
    def test_empty_metrics(self):
        m = Metrics()
        s = m.summary()
        assert s["requests"] == 0
        assert s["error_rate"] == 0.0

    def test_record_and_summary(self):
        m = Metrics()
        t1 = Trace()
        s1 = t1.start_span("a")
        s1.finish()
        t1.finish()

        t2 = Trace()
        s2 = t2.start_span("b")
        s2.finish()
        t2.finish()

        m.record(t1)
        m.record(t2)

        s = m.summary()
        assert s["requests"] == 2
        assert s["errors"] == 0
        assert s["error_rate"] == 0.0
        assert "a" in s["nodes"]
        assert "b" in s["nodes"]

    def test_error_rate(self):
        m = Metrics()
        t1 = Trace()
        t1.start_span("x").finish()
        t1.finish()

        t2 = Trace()
        t2.start_span("y").finish(error="fail")
        t2.finish()

        m.record(t1)
        m.record(t2)

        assert m.error_rate == 0.5
        assert m.total_errors == 1


@pytest.mark.asyncio
async def test_graph_integration():
    """图执行时自动创建 Span 并记录到 Trace。"""
    g = Graph()
    g.add_node("step1", BaseSkill("step1", produces={"a": 1}))
    g.add_node("step2", BaseSkill("step2", required_inputs=["a"],
                                  produces={"b": 2}))
    g.add_edge("step1", "step2")

    trace = Trace()
    ctx = SkillContext()
    await g.execute(ctx, entry="step1", trace=trace)

    assert len(trace.spans) == 2
    assert trace.spans[0].node == "step1"
    assert trace.spans[1].node == "step2"
    assert trace.duration_ms > 0
    assert not trace.has_error
