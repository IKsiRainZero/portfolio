import json
import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from app.tracer import Trace, Tracer, traced


def test_trace_to_dict():
    t = Trace(
        id="trace-abc", timestamp="2026-07-21T00:00:00.000Z",
        source="console", session_id="sess-1",
        operation="test.run", target="Crescent",
        input_summary="", output_summary="ok", duration_ms=100,
        status="ok"
    )
    d = t.to_dict()
    assert d["id"] == "trace-abc"
    assert d["operation"] == "test.run"


def test_tracer_writes_jsonl():
    with tempfile.TemporaryDirectory() as tmp:
        tracer = Tracer(Path(tmp))
        t = tracer.trace("test.run", "Crescent")
        t.output_summary = "3 passed"
        t.duration_ms = 50
        tracer.write(t)

        files = list(Path(tmp).glob("*.jsonl"))
        assert len(files) == 1
        line = files[0].read_text(encoding="utf-8").strip()
        data = json.loads(line)
        assert data["operation"] == "test.run"
        assert data["target"] == "Crescent"
        assert data["status"] == "ok"


def test_tracer_corrupt_line_skipped():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / f"{today}.jsonl"
        f.write_text("not json\n", encoding="utf-8")
        tracer = Tracer(Path(tmp))
        t = tracer.trace("test.run", "C")
        t.output_summary = "ok"
        t.duration_ms = 1
        tracer.write(t)

        lines = f.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[1])["operation"] == "test.run"


def test_traced_async_writes_real_result(portfolio_root):
    @traced("test.async_op")
    async def async_op():
        await asyncio.sleep(0.01)
        return {"status": "done"}

    result = asyncio.run(async_op())
    assert result == {"status": "done"}

    traces_dir = portfolio_root / ".context" / "observability" / "traces"
    files = sorted(traces_dir.glob("*.jsonl"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert data["operation"] == "test.async_op"
    assert data["output_summary"] == "{'status': 'done'}"
    assert "coroutine" not in data["output_summary"]
    assert data["duration_ms"] > 0
    assert data["status"] == "ok"


def test_traced_sync_unchanged(portfolio_root):
    @traced("test.sync_op")
    def sync_op():
        return "sync-result"

    assert sync_op() == "sync-result"

    traces_dir = portfolio_root / ".context" / "observability" / "traces"
    files = sorted(traces_dir.glob("*.jsonl"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert data["operation"] == "test.sync_op"
    assert data["output_summary"] == "sync-result"
