"""用户画像引擎 SKILL — 包装 profile 加载 + 技能匹配。

委托给 services.workbench.profile_store + skill_matcher。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from skills.protocol import SkillInput, SkillOutput


@dataclass
class ProfileEngineSkill:
    """加载用户画像 + 匹配职业方向。

    execute(ctx) → {"profile": dict, "matches": list, "direction_count": int}
    """

    name: str = "profile_engine"

    @property
    def input_schema(self) -> SkillInput:
        return SkillInput(
            required=["user_id"],
            optional=["keywords"],
            schema={"user_id": str, "keywords": list},
        )

    @property
    def output_schema(self) -> SkillOutput:
        return SkillOutput(
            produces=["profile", "matches", "direction_count"],
            schema={"profile": dict, "matches": list, "direction_count": int},
        )

    @property
    def trigger_rules(self) -> List[str]:
        return ["on_profile_ready", "on_user_message"]

    @property
    def dependencies(self) -> List[str]:
        return []

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        from services.workbench.profile_store import ProfileStore
        from services.workbench.skill_matcher import SkillMatcher
        from services.workbench.industry_scanner import IndustryScanner
        from config import USER_DATA_DIR
        import os
        from pathlib import Path

        user_id = ctx["user_id"]
        data_dir = Path(os.environ.get("CRESCENT_TEST_DATA", str(USER_DATA_DIR)))
        wb_pw = os.environ.get("WB_PASSWORD", "crescent-wb")
        store = ProfileStore(data_dir=data_dir, password=wb_pw)
        profile = store.load()

        keywords = ctx.get("keywords", list(profile.skills.keys()) + profile.interests)
        if not keywords:
            keywords = ["技术", "开发"]

        scanner = IndustryScanner()
        try:
            trends = scanner.scan(keywords)
        except Exception:
            trends = []

        matcher = SkillMatcher()
        matches = matcher.match(profile, trends) if trends else []

        return {
            "profile": profile.to_dict(),
            "matches": [{"direction": m.direction, "score": m.score,
                         "overlap": m.skill_overlap, "gaps": m.skill_gap}
                        for m in matches],
            "direction_count": len(matches),
        }
