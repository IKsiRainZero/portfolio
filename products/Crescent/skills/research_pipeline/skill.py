"""研究管道 SKILL — 包装 pipeline 的端到端调研流程。

委托给 services.pipeline.e2e.ResearchOrchestrator，不做内部重构。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from skills.protocol import SkillInput, SkillOutput


@dataclass
class ResearchPipelineSkill:
    """执行一次完整的研究管道：意图解析 → 搜索 → 抓取 → 可信度 → 方案生成。

    execute(ctx) → {"status": str, "outputs": dict, "trace": list}
    """

    name: str = "research_pipeline"

    @property
    def input_schema(self) -> SkillInput:
        return SkillInput(
            required=["query"],
            optional=["max_results"],
            schema={"query": str, "max_results": int},
        )

    @property
    def output_schema(self) -> SkillOutput:
        return SkillOutput(
            produces=["status", "outputs", "trace"],
            schema={"status": str, "outputs": dict, "trace": list},
        )

    @property
    def trigger_rules(self) -> List[str]:
        return ["on_research_request"]

    @property
    def dependencies(self) -> List[str]:
        return []

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        from services.pipeline.e2e import ResearchOrchestrator

        query = ctx["query"]
        max_results = ctx.get("max_results", 10)
        orch = ResearchOrchestrator()
        result = orch.run(query=query, max_results=max_results)
        return result
