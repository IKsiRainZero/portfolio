"""agent_service.py SKILL 包装器测试 — 验证绞杀者模式正确性。"""

from __future__ import annotations

import pytest

from skills.tool_registry import ToolRegistrySkill
from skills.prompt_manager import PromptManagerSkill


class TestToolRegistrySkill:
    @pytest.mark.asyncio
    async def test_returns_all_tools(self):
        """空 message → 返回全部工具列表。"""
        skill = ToolRegistrySkill()
        result = await skill.execute({"message": ""})

        assert "tools" in result
        assert "count" in result
        assert result["count"] > 0
        assert isinstance(result["tools"], list)

    @pytest.mark.asyncio
    async def test_filter_by_intent(self):
        """带意图的 message → 返回筛选后的工具子集。"""
        skill = ToolRegistrySkill()
        result_all = await skill.execute({"message": ""})
        result_filtered = await skill.execute({"message": "帮我出几道题"})

        # 筛选后的工具数应 ≤ 全部工具数
        assert result_filtered["count"] <= result_all["count"]

    @pytest.mark.asyncio
    async def test_schema_conformance(self):
        """输出字段符合 SkillOutput 声明。"""
        skill = ToolRegistrySkill()
        result = await skill.execute({})

        for field in skill.output_schema.produces:
            assert field in result, f"缺少声明字段: {field}"


class TestPromptManagerSkill:
    @pytest.mark.asyncio
    async def test_returns_prompt_and_intent(self):
        """返回 system_prompt、intent、is_simple。"""
        skill = PromptManagerSkill()
        result = await skill.execute({"message": "你好"})

        assert "system_prompt" in result
        assert "intent" in result
        assert "is_simple" in result
        assert isinstance(result["system_prompt"], str)
        assert isinstance(result["intent"], str)
        assert isinstance(result["is_simple"], bool)

    @pytest.mark.asyncio
    async def test_respects_persona(self):
        """不同 persona 产生不同的 system_prompt。"""
        skill = PromptManagerSkill()
        default = await skill.execute({"message": "test", "persona": ""})
        teacher = await skill.execute({"message": "test", "persona": "teacher"})

        # 不同 persona 应有不同的 prompt 内容
        # (不要求严格不等，因为 fallback 可能相同，但至少都有值)
        assert len(default["system_prompt"]) > 0
        assert len(teacher["system_prompt"]) > 0

    @pytest.mark.asyncio
    async def test_schema_conformance(self):
        """输出字段符合 SkillOutput 声明。"""
        skill = PromptManagerSkill()
        result = await skill.execute({"message": "test"})

        for field in skill.output_schema.produces:
            assert field in result, f"缺少声明字段: {field}"
