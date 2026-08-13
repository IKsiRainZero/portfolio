import json
import uuid
import time
import functools
import inspect
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from ..config import config


@dataclass
class Trace:
    id: str
    timestamp: str
    source: str
    session_id: str
    operation: str
    target: str
    input_summary: str
    output_summary: str
    duration_ms: int
    status: str
    parent_trace_id: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "source": self.source,
            "session_id": self.session_id,
            "operation": self.operation,
            "target": self.target,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "parent_trace_id": self.parent_trace_id,
            "metadata": self.metadata,
        }


class Tracer:
    def __init__(self, traces_dir: Path = config.TRACES_DIR):
        self.traces_dir = traces_dir
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = str(uuid.uuid4())

    def _daily_file(self) -> Path:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.traces_dir / f"{today}.jsonl"

    def write(self, trace: Trace) -> None:
        trace.session_id = self.session_id
        with open(self._daily_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps(trace.to_dict(), ensure_ascii=False) + "\n")

    def trace(
        self, operation: str, target: str, input_summary: str = "",
        parent_trace_id: str | None = None, metadata: dict | None = None
    ) -> Trace:
        t = Trace(
            id=f"trace-{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            source="console",
            session_id=self.session_id,
            operation=operation,
            target=target,
            input_summary=input_summary,
            output_summary="",
            duration_ms=0,
            status="ok",
            parent_trace_id=parent_trace_id,
            metadata=metadata or {},
        )
        return t


_tracer = Tracer()


def traced(operation: str):
    """Decorator: automatically trace function execution."""
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                target = kwargs.get("project_name", "") or (args[0] if args else "")
                if not isinstance(target, str):
                    target = func.__name__
                trace = _tracer.trace(operation=operation, target=target)
                start = time.time()
                try:
                    result = await func(*args, **kwargs)
                    trace.output_summary = str(result)[:200]
                    trace.status = "ok"
                    return result
                except Exception as e:
                    trace.output_summary = str(e)[:200]
                    trace.status = "error"
                    raise
                finally:
                    trace.duration_ms = int((time.time() - start) * 1000)
                    _tracer.write(trace)
            return wrapper
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            target = kwargs.get("project_name", "") or (args[0] if args else "")
            if not isinstance(target, str):
                target = func.__name__
            trace = _tracer.trace(operation=operation, target=target)
            start = time.time()
            try:
                result = func(*args, **kwargs)
                trace.output_summary = str(result)[:200]
                trace.status = "ok"
                return result
            except Exception as e:
                trace.output_summary = str(e)[:200]
                trace.status = "error"
                raise
            finally:
                trace.duration_ms = int((time.time() - start) * 1000)
                _tracer.write(trace)
        return wrapper
    return decorator


def get_tracer() -> Tracer:
    return _tracer
