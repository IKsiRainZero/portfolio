"""pipeline + workbench SKILL 包装器测试 — 验证绞杀者模式正确性。"""

from __future__ import annotations

import pytest

from skills.research_pipeline import ResearchPipelineSkill
from skills.profile_engine import ProfileEngineSkill
from skills.gap_analyzer import GapAnalyzerSkill
from skills.path_engine import PathEngineSkill
from skills.workbench_engine import WorkbenchEngineSkill


ALL_SKILLS = [
    ResearchPipelineSkill(),
    ProfileEngineSkill(),
    GapAnalyzerSkill(),
    PathEngineSkill(),
    WorkbenchEngineSkill(),
]


class TestResearchPipelineSkill:
    @pytest.mark.asyncio
    async def test_schema_conformance(self):
        skill = ResearchPipelineSkill()
        for field in skill.output_schema.produces:
            assert field in skill.output_schema.schema, f"缺少 schema 类型: {field}"

    def test_input_requires_query(self):
        skill = ResearchPipelineSkill()
        missing = skill.input_schema.validate({})
        assert "query" in missing

    def test_dependencies_empty(self):
        skill = ResearchPipelineSkill()
        assert skill.dependencies == []


class TestProfileEngineSkill:
    @pytest.mark.asyncio
    async def test_schema_conformance(self):
        skill = ProfileEngineSkill()
        for field in skill.output_schema.produces:
            assert field in skill.output_schema.schema, f"缺少 schema 类型: {field}"

    def test_input_requires_user_id(self):
        skill = ProfileEngineSkill()
        missing = skill.input_schema.validate({})
        assert "user_id" in missing


class TestGapAnalyzerSkill:
    @pytest.mark.asyncio
    async def test_schema_conformance(self):
        skill = GapAnalyzerSkill()
        for field in skill.output_schema.produces:
            assert field in skill.output_schema.schema, f"缺少 schema 类型: {field}"

    def test_input_requires_user_id_and_direction(self):
        skill = GapAnalyzerSkill()
        missing = skill.input_schema.validate({})
        assert "user_id" in missing
        assert "direction" in missing

    def test_depends_on_profile_engine(self):
        skill = GapAnalyzerSkill()
        assert "profile_engine" in skill.dependencies


class TestPathEngineSkill:
    @pytest.mark.asyncio
    async def test_schema_conformance(self):
        skill = PathEngineSkill()
        for field in skill.output_schema.produces:
            assert field in skill.output_schema.schema, f"缺少 schema 类型: {field}"

    def test_input_requires_user_id_and_gaps(self):
        skill = PathEngineSkill()
        missing = skill.input_schema.validate({})
        assert "user_id" in missing
        assert "gaps" in missing

    def test_depends_on_gap_analyzer(self):
        skill = PathEngineSkill()
        assert "gap_analyzer" in skill.dependencies


class TestWorkbenchEngineSkill:
    @pytest.mark.asyncio
    async def test_schema_conformance(self):
        skill = WorkbenchEngineSkill()
        for field in skill.output_schema.produces:
            assert field in skill.output_schema.schema, f"缺少 schema 类型: {field}"

    def test_input_requires_user_id_and_message(self):
        skill = WorkbenchEngineSkill()
        missing = skill.input_schema.validate({})
        assert "user_id" in missing
        assert "message" in missing

    def test_depends_on_prompt_manager(self):
        skill = WorkbenchEngineSkill()
        assert "prompt_manager" in skill.dependencies


class TestAllSkillsProtocolCompliance:
    @pytest.mark.asyncio
    async def test_all_have_required_protocol_attrs(self):
        for skill in ALL_SKILLS:
            assert hasattr(skill, "name"), f"{type(skill).__name__}: 缺少 name"
            assert isinstance(skill.name, str), f"{type(skill).__name__}: name 不是 str"
            assert hasattr(skill, "input_schema"), f"{type(skill).__name__}: 缺少 input_schema"
            assert hasattr(skill, "output_schema"), f"{type(skill).__name__}: 缺少 output_schema"
            assert hasattr(skill, "trigger_rules"), f"{type(skill).__name__}: 缺少 trigger_rules"
            assert hasattr(skill, "dependencies"), f"{type(skill).__name__}: 缺少 dependencies"
            assert hasattr(skill, "execute"), f"{type(skill).__name__}: 缺少 execute"
            assert callable(skill.execute), f"{type(skill).__name__}: execute 不可调用"

    def test_all_output_schemas_produce_nonempty(self):
        for skill in ALL_SKILLS:
            produces = skill.output_schema.produces
            assert len(produces) > 0, f"{skill.name}: produces 不应为空"
            assert all(isinstance(p, str) for p in produces), f"{skill.name}: produces 元素必须是 str"
