"""学习路径引擎 SKILL — 包装 learning_path + next_action 的路径生成。

委托给 services.workbench.learning_path + next_action。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from skills.protocol import SkillInput, SkillOutput


@dataclass
class PathEngineSkill:
    """从技能差距生成学习路径和下一步行动。

    execute(ctx) → {"phases": list, "actions": list, "phase_count": int}
    """

    name: str = "path_engine"

    @property
    def input_schema(self) -> SkillInput:
        return SkillInput(
            required=["user_id", "gaps"],
            optional=["current_phase"],
            schema={"user_id": str, "gaps": list, "current_phase": str},
        )

    @property
    def output_schema(self) -> SkillOutput:
        return SkillOutput(
            produces=["phases", "actions", "phase_count"],
            schema={"phases": list, "actions": list, "phase_count": int},
        )

    @property
    def trigger_rules(self) -> List[str]:
        return ["on_gap_confirmed"]

    @property
    def dependencies(self) -> List[str]:
        return ["gap_analyzer"]

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        from services.workbench.profile_store import ProfileStore
        from services.workbench.gap_analyzer import GapItem, GapReport
        from services.workbench.learning_path import LearningPathGenerator
        from services.workbench.next_action import NextActionGenerator
        from config import USER_DATA_DIR
        import os
        from pathlib import Path

        gaps_raw = ctx["gaps"]
        current_phase = ctx.get("current_phase", "")

        data_dir = Path(os.environ.get("CRESCENT_TEST_DATA", str(USER_DATA_DIR)))
        wb_pw = os.environ.get("WB_PASSWORD", "crescent-wb")
        store = ProfileStore(data_dir=data_dir, password=wb_pw)
        profile = store.load()

        gaps = [GapItem(skill_name=g["skill"], required_level=g.get("required", "beginner"),
                         current_level=g.get("current", "none"), priority=g.get("priority", "medium"),
                         rationale=g.get("rationale", ""))
                for g in gaps_raw]

        report = GapReport(gaps=gaps)
        path_gen = LearningPathGenerator()
        path = path_gen.generate(report, profile)

        action_gen = NextActionGenerator()
        phase_name = current_phase or (path.phases[0].name if path.phases else "")
        actions = action_gen.generate(path, phase_name) if path.phases else []

        return {
            "phases": [{"name": p.name, "duration": p.duration,
                         "difficulty": p.difficulty,
                         "modules": [{"title": m.title, "hours": m.estimated_hours,
                                       "type": m.resource_type} for m in p.modules]}
                        for p in path.phases],
            "actions": [{"title": a.title, "description": a.description,
                          "estimated_time": a.estimated_time,
                          "criteria": a.completion_criteria,
                          "resource_type": a.resource_type} for a in actions],
            "phase_count": len(path.phases),
        }
