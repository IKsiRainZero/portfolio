"""工具注册表 SKILL — 包装 agent_service 的工具管理函数。

遵循绞杀者模式：当前委托给 agent_service 的现有实现，
后续可逐步将工具定义、缓存逻辑内迁到本模块。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from skills.protocol import Skill, SkillInput, SkillOutput


@dataclass
class ToolRegistrySkill:
    """管理 Agent 可用工具的注册、筛选和缓存。

    execute(ctx) → {"tools": [...], "count": N}
    """

    name: str = "tool_registry"

    @property
    def input_schema(self) -> SkillInput:
        return SkillInput(
            optional=["message"],
            schema={"message": str},
        )

    @property
    def output_schema(self) -> SkillOutput:
        return SkillOutput(
            produces=["tools", "count"],
            schema={"tools": list, "count": int},
        )

    @property
    def trigger_rules(self) -> List[str]:
        return ["on_chat_start", "on_tool_request"]

    @property
    def dependencies(self) -> List[str]:
        return []

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        from services.agent_service import get_tools

        message = ctx.get("message", "")
        tools = get_tools(message)
        return {"tools": tools, "count": len(tools)}
