"""差距分析 SKILL — 包装 gap_analyzer 的技能差距评估。

委托给 services.workbench.gap_analyzer。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from skills.protocol import SkillInput, SkillOutput


@dataclass
class GapAnalyzerSkill:
    """分析用户技能与目标方向的差距。

    execute(ctx) → {"gaps": list, "gap_count": int, "must_count": int, "rec_count": int}
    """

    name: str = "gap_analyzer"

    @property
    def input_schema(self) -> SkillInput:
        return SkillInput(
            required=["user_id", "direction"],
            optional=["overlap_skills", "gap_skills"],
            schema={"user_id": str, "direction": str, "overlap_skills": list, "gap_skills": list},
        )

    @property
    def output_schema(self) -> SkillOutput:
        return SkillOutput(
            produces=["gaps", "gap_count", "must_count", "rec_count", "opt_count"],
            schema={"gaps": list, "gap_count": int, "must_count": int, "rec_count": int, "opt_count": int},
        )

    @property
    def trigger_rules(self) -> List[str]:
        return ["on_direction_confirmed"]

    @property
    def dependencies(self) -> List[str]:
        return ["profile_engine"]

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        from services.workbench.profile_store import ProfileStore
        from services.workbench.gap_analyzer import GapAnalyzer
        from services.workbench.skill_matcher import MatchResult
        from config import USER_DATA_DIR
        import os
        from pathlib import Path

        user_id = ctx["user_id"]
        direction_name = ctx["direction"]
        overlap_names = ctx.get("overlap_skills", [])
        gap_names = ctx.get("gap_skills", [])

        data_dir = Path(os.environ.get("CRESCENT_TEST_DATA", str(USER_DATA_DIR)))
        wb_pw = os.environ.get("WB_PASSWORD", "crescent-wb")
        store = ProfileStore(data_dir=data_dir, password=wb_pw)
        profile = store.load()

        dummy_match = MatchResult(
            direction=direction_name,
            score=ctx.get("score", 0),
            skill_overlap=overlap_names,
            skill_gap=gap_names,
            transferability=0.5,
            rationale="",
        )

        analyzer = GapAnalyzer()
        report = analyzer.analyze(profile, dummy_match)

        gaps_out = [{"skill": g.skill_name, "required": g.required_level,
                      "current": g.current_level, "priority": g.priority,
                      "rationale": g.rationale}
                     for g in report.gaps]

        return {
            "gaps": gaps_out,
            "gap_count": len(report.gaps),
            "must_count": sum(1 for g in report.gaps if g.priority == "must"),
            "rec_count": sum(1 for g in report.gaps if g.priority == "recommended"),
            "opt_count": sum(1 for g in report.gaps if g.priority == "optional"),
        }
