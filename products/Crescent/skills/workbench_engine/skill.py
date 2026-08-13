"""工作台编排器 SKILL — 包装完整的 WorkbenchEngine 对话回合。

委托给 services.workbench.engine，构造方式与 api_workbench._get_engine() 一致。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from skills.protocol import SkillInput, SkillOutput


@dataclass
class WorkbenchEngineSkill:
    """编排一次工作台对话回合（handle_input + confirm_panel + revoke_panel）。

    execute(ctx) → {"events": list, "event_count": int, "panels": dict}
    """

    name: str = "workbench_engine"

    @property
    def input_schema(self) -> SkillInput:
        return SkillInput(
            required=["user_id", "message"],
            optional=["panel_action", "panel_id"],
            schema={"user_id": str, "message": str, "panel_action": str, "panel_id": str},
        )

    @property
    def output_schema(self) -> SkillOutput:
        return SkillOutput(
            produces=["events", "event_count", "panels"],
            schema={"events": list, "event_count": int, "panels": dict},
        )

    @property
    def trigger_rules(self) -> List[str]:
        return ["on_user_message", "on_panel_action"]

    @property
    def dependencies(self) -> List[str]:
        return ["prompt_manager"]

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        from services.workbench.profile_store import ProfileStore
        from services.workbench.industry_scanner import IndustryScanner
        from services.workbench.skill_matcher import SkillMatcher
        from services.workbench.gap_analyzer import GapAnalyzer
        from services.workbench.learning_path import LearningPathGenerator
        from services.workbench.next_action import NextActionGenerator
        from services.workbench.engine import WorkbenchEngine
        from config import USER_DATA_DIR
        import os
        from pathlib import Path

        user_id = ctx["user_id"]
        message = ctx["message"]
        panel_action = ctx.get("panel_action", "")
        panel_id = ctx.get("panel_id", "")

        data_dir = Path(os.environ.get("CRESCENT_TEST_DATA", str(USER_DATA_DIR)))
        wb_pw = os.environ.get("WB_PASSWORD", "crescent-wb")
        store = ProfileStore(data_dir=data_dir, password=wb_pw)
        engine = WorkbenchEngine(
            profile_store=store,
            scanner=IndustryScanner(),
            matcher=SkillMatcher(),
            analyzer=GapAnalyzer(),
            path_gen=LearningPathGenerator(),
            action_gen=NextActionGenerator(),
        )

        if panel_action == "confirm" and panel_id:
            events = engine.confirm_panel(user_id, panel_id)
        elif panel_action == "revoke" and panel_id:
            events = engine.revoke_panel(user_id, panel_id)
        else:
            events = engine.handle_input(user_id, message)

        serialized = [{"type": e.event_type, "panel_id": e.panel_id, "payload": e.payload, "timestamp": e.timestamp}
                      for e in events]

        return {
            "events": serialized,
            "event_count": len(events),
            "panels": {e.panel_id: e.event_type for e in events if e.panel_id},
        }
