"""E2E 调研管道集成 — 搜索 → 抓取 → 可信度融合 → 方案生成。"""

from __future__ import annotations

from services.pipeline.orchestrator import Orchestrator
from services.pipeline.trace_logger import TraceLogger
from services.pipeline.intent_parser import IntentParserStep
from services.pipeline.resource_scanner import ResourceScannerStep
from services.pipeline.search import SearchStep
from services.pipeline.fetcher import FetchStep
from services.pipeline.credibility import CredibilityFuserStep
from services.pipeline.plan_generator import PlanGeneratorStep
from services.pipeline.persistence import PersistenceStep
from services.pipeline.types import PipelineSpec, StepSpec


def build_research_pipeline() -> Orchestrator:
    """构建完整的调研管道。搜索 → 抓取 → 可信度 → 方案生成 → 持久化。"""
    steps = [
        IntentParserStep(),
        ResourceScannerStep(),
        SearchStep(),
        FetchStep(),
        CredibilityFuserStep(),
        PlanGeneratorStep(),
        PersistenceStep(),
    ]
    return Orchestrator(steps=steps, trace_logger=TraceLogger())


class ResearchOrchestrator:
    """调研管道的便捷封装。"""

    def __init__(self):
        self._orch = build_research_pipeline()

    def run(self, query: str, max_results: int = 10) -> dict:
        spec = PipelineSpec(steps=[
            StepSpec(step_name="S1", enabled=True),
            StepSpec(step_name="S2", enabled=True),
            StepSpec(step_name="S3_search", enabled=True, config={"max_results": max_results}),
            StepSpec(step_name="S3_fetch", enabled=True),
            StepSpec(step_name="S4", enabled=True, config={"operators": ["relation", "sufficiency"]}),
            StepSpec(step_name="S5", enabled=True),
            StepSpec(step_name="S7", enabled=True),
        ])
        return self._orch.run(query=query, spec=spec)
