"""diagnostics 工具测试 — CI schema 校验。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import pytest

from skills.protocol import SkillInput, SkillOutput
from tools.diagnostics.skill_health import SkillHealthCheck, HealthIssue, HealthReport


@dataclass
class ValidSkill:
    """合规 SKILL — 所有检查应通过。"""
    name: str = "valid_skill"

    @property
    def input_schema(self) -> SkillInput:
        return SkillInput(
            required=["message"],
            optional=["persona"],
            schema={"message": str, "persona": str},
        )

    @property
    def output_schema(self) -> SkillOutput:
        return SkillOutput(
            produces=["reply", "sources"],
            schema={"reply": str, "sources": list},
        )

    @property
    def trigger_rules(self) -> List[str]:
        return ["on_user_message"]

    @property
    def dependencies(self) -> List[str]:
        return ["tool_registry"]

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {"reply": "hello", "sources": ["a", "b"]}


class MissingProtocolSkill:
    """缺少整个协议实现的 SKILL — 每个字段都会报 error。"""
    pass


@dataclass
class PartialSkill:
    """部分实现 — 缺少 output schema。"""
    name: str = "partial_skill"

    @property
    def input_schema(self) -> SkillInput:
        return SkillInput(required=["message"], optional=[], schema={"message": str})

    @property
    def output_schema(self):
        return None  # type: ignore — 故意错误

    @property
    def trigger_rules(self) -> List[str]:
        return []

    @property
    def dependencies(self) -> List[str]:
        return []

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {}


@dataclass
class MismatchedOutputSkill:
    """声明 produces 但实际 execute 不返回对应字段。"""
    name: str = "mismatched_skill"

    @property
    def input_schema(self) -> SkillInput:
        return SkillInput(required=[], optional=[], schema={})

    @property
    def output_schema(self) -> SkillOutput:
        return SkillOutput(
            produces=["missing_field"],
            schema={"missing_field": str},
        )

    @property
    def trigger_rules(self) -> List[str]:
        return []

    @property
    def dependencies(self) -> List[str]:
        return []

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {}


class TestSkillHealthCheck:

    @pytest.mark.asyncio
    async def test_valid_skill_passes(self):
        checker = SkillHealthCheck(ValidSkill())
        report = await checker.run()

        assert report.passed is True
        assert len(report.issues) == 0
        assert "protocol" in report.checks_run
        assert "schemas" in report.checks_run
        assert "execute" in report.checks_run

    @pytest.mark.asyncio
    async def test_missing_protocol_reports_errors(self):
        checker = SkillHealthCheck(MissingProtocolSkill())
        report = await checker.run()

        assert report.passed is False
        errors = [i for i in report.issues if i.severity == "error"]
        assert len(errors) >= 5  # 至少 5 个 error（五要素全缺 + execute 异常）

    @pytest.mark.asyncio
    async def test_invalid_output_schema(self):
        checker = SkillHealthCheck(PartialSkill())
        report = await checker.run()

        assert report.passed is False
        has_schema_error = any(
            "output_schema" == i.field for i in report.issues if i.severity == "error"
        )
        assert has_schema_error

    @pytest.mark.asyncio
    async def test_mismatched_produces(self):
        checker = SkillHealthCheck(MismatchedOutputSkill())
        report = await checker.run()

        assert not report.passed
        has_missing = any(
            "missing_field" in i.message for i in report.issues
        )
        assert has_missing


class TestHealthReport:
    def test_report_defaults(self):
        report = HealthReport(skill_name="test")
        assert report.passed is True
        assert report.issues == []
        assert report.checks_run == []

    def test_add_issue(self):
        report = HealthReport(skill_name="s1")
        report.add("error", "execute", "boom")
        assert len(report.issues) == 1
        assert report.issues[0].severity == "error"
        assert report.issues[0].skill_name == "s1"
        assert report.issues[0].message == "boom"
