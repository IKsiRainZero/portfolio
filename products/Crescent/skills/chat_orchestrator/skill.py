"""对话编排器 SKILL — 包装 agent_service 的对话循环。

封装 ReAct 循环、会话生命周期、历史管理。当前委托给 agent_service，
后续可逐步将编排逻辑内迁。非流式模式：收集所有 SSE 事件后返回最终结果。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List

from skills.protocol import Skill, SkillInput, SkillOutput


@dataclass
class ChatOrchestratorSkill:
    """编排一次 Agent 对话回合。

    execute(ctx) → {"reply": str, "steps": [...], "tool_calls": int, "sources": [...]}
    """

    name: str = "chat_orchestrator"

    @property
    def input_schema(self) -> SkillInput:
        return SkillInput(
            required=["message"],
            optional=["session_id", "persona"],
            schema={"message": str, "session_id": str, "persona": str},
        )

    @property
    def output_schema(self) -> SkillOutput:
        return SkillOutput(
            produces=["reply", "steps", "tool_calls", "sources"],
            schema={"reply": str, "steps": list, "tool_calls": int, "sources": list},
        )

    @property
    def trigger_rules(self) -> List[str]:
        return ["on_user_message"]

    @property
    def dependencies(self) -> List[str]:
        return ["tool_registry", "prompt_manager"]

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        from services.agent_service import _agent_queues

        message = ctx["message"]
        session_id = ctx.get("session_id", "default")
        persona = ctx.get("persona", "")

        # 启动 agent_chat 生成器（它通过 _agent_queues 推送事件）
        from services.agent_service import agent_chat
        gen = agent_chat(message, session_id=session_id, persona=persona)

        # 消费生成器直到完成，收集 SSE 事件
        steps = []
        reply = ""
        sources = []
        tool_calls = 0

        try:
            for event in gen:
                if event.get("type") == "step":
                    steps.append(event)
                    if event.get("phase") == "action":
                        tool_calls += 1
                elif event.get("type") == "chunk":
                    reply += event.get("content", "")
                elif event.get("type") == "done":
                    reply = event.get("reply", reply)
                    steps = event.get("steps", steps)
                    sources = event.get("sources", [])
                    tool_calls = event.get("tool_calls", tool_calls)
                elif event.get("type") == "cancelled":
                    return {"reply": "[已取消]", "steps": steps, "tool_calls": tool_calls, "sources": sources}
        except Exception as exc:
            return {"reply": f"[错误] {exc}", "steps": steps, "tool_calls": tool_calls, "sources": sources}

        return {
            "reply": reply,
            "steps": steps,
            "tool_calls": tool_calls,
            "sources": sources,
        }
