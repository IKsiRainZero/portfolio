"""Prompt 管理器 SKILL — 包装 agent_service 的 prompt/意图分类函数。

负责：system prompt 组装（含跨 Agent 上下文注入）、意图分类、计划格式化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from skills.protocol import Skill, SkillInput, SkillOutput


@dataclass
class PromptManagerSkill:
    """管理 System Prompt 和用户意图分类。

    execute(ctx) → {"system_prompt": str, "intent": str, "is_simple": bool}
    """

    name: str = "prompt_manager"

    @property
    def input_schema(self) -> SkillInput:
        return SkillInput(
            required=["message"],
            optional=["persona", "history"],
            schema={"message": str, "persona": str, "history": list},
        )

    @property
    def output_schema(self) -> SkillOutput:
        return SkillOutput(
            produces=["system_prompt", "intent", "is_simple"],
            schema={"system_prompt": str, "intent": str, "is_simple": bool},
        )

    @property
    def trigger_rules(self) -> List[str]:
        return ["on_chat_message"]

    @property
    def dependencies(self) -> List[str]:
        return []

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        from services.agent_service import _get_system_prompt, _classify_intent, _is_simple_query

        message = ctx.get("message", "")
        persona = ctx.get("persona", "")
        system_prompt = _get_system_prompt(persona)
        intent = _classify_intent(message)
        is_simple = _is_simple_query(message)

        return {
            "system_prompt": system_prompt,
            "intent": intent,
            "is_simple": is_simple,
        }
