"""可观测性基础设施 — 横切关注点，独立于任何业务模块。

轻量级：请求ID、耗时、Token 消耗、错误率。不替代 eval 系统，
只提供开发/运维所需的基础可观测性数据。
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Span:
    """单次 SKILL 执行跨度。"""

    node: str
    started_at: float = field(default_factory=time.perf_counter)
    ended_at: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.ended_at:
            return (self.ended_at - self.started_at) * 1000
        return 0.0

    def finish(self, tokens_in: int = 0, tokens_out: int = 0,
               error: str | None = None, **meta) -> None:
        self.ended_at = time.perf_counter()
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.error = error
        self.metadata.update(meta)


@dataclass
class Trace:
    """一次完整的图执行追踪。"""

    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: float = field(default_factory=time.perf_counter)
    ended_at: float = 0.0
    spans: List[Span] = field(default_factory=list)
    error: str | None = None

    @property
    def duration_ms(self) -> float:
        if self.ended_at:
            return (self.ended_at - self.started_at) * 1000
        return 0.0

    @property
    def total_tokens(self) -> int:
        return sum(s.tokens_in + s.tokens_out for s in self.spans)

    @property
    def has_error(self) -> bool:
        return self.error is not None or any(s.error for s in self.spans)

    def start_span(self, node: str) -> Span:
        span = Span(node=node)
        self.spans.append(span)
        return span

    def finish(self, error: str | None = None) -> None:
        self.ended_at = time.perf_counter()
        self.error = error


class Metrics:
    """内存中的指标聚合器。"""

    def __init__(self):
        self.total_requests = 0
        self.total_errors = 0
        self.total_tokens = 0
        self.durations_ms: List[float] = []
        self.per_node: Dict[str, List[float]] = defaultdict(list)

    def record(self, trace: Trace) -> None:
        self.total_requests += 1
        if trace.has_error:
            self.total_errors += 1
        self.total_tokens += trace.total_tokens
        self.durations_ms.append(trace.duration_ms)
        for span in trace.spans:
            self.per_node[span.node].append(span.duration_ms)

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_errors / self.total_requests

    @property
    def avg_duration_ms(self) -> float:
        if not self.durations_ms:
            return 0.0
        return sum(self.durations_ms) / len(self.durations_ms)

    @property
    def p95_duration_ms(self) -> float:
        if not self.durations_ms:
            return 0.0
        sorted_d = sorted(self.durations_ms)
        idx = int(len(sorted_d) * 0.95)
        return sorted_d[min(idx, len(sorted_d) - 1)]

    def summary(self) -> Dict[str, Any]:
        return {
            "requests": self.total_requests,
            "errors": self.total_errors,
            "error_rate": round(self.error_rate, 4),
            "total_tokens": self.total_tokens,
            "avg_ms": round(self.avg_duration_ms, 1),
            "p95_ms": round(self.p95_duration_ms, 1),
            "nodes": {n: round(sum(ds) / len(ds), 1) for n, ds in self.per_node.items()},
        }
