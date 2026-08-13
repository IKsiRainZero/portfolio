"""SkillHealthCheck — CI 可用的 SKILL schema 校验。

验证每个 SKILL 模块是否正确实现了 Skill 协议五要素：
input_schema / output_schema / trigger_rules / dependencies / execute

不依赖 LLM Judge、Meta Evaluator、Golden Dataset。
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from skills.protocol import Skill, SkillInput, SkillOutput


@dataclass
class HealthIssue:
    severity: str  # "error" | "warning"
    skill_name: str
    field: str
    message: str


@dataclass
class HealthReport:
    skill_name: str
    passed: bool = True
    issues: List[HealthIssue] = field(default_factory=list)
    checks_run: List[str] = field(default_factory=list)

    def add(self, severity: str, field: str, message: str) -> None:
        self.issues.append(HealthIssue(severity, self.skill_name, field, message))


class SkillHealthCheck:
    """校验单个 SKILL 模块的协议合规性。"""

    def __init__(self, skill: Skill):
        self.skill = skill
        self.report = HealthReport(skill_name=getattr(skill, "name", type(skill).__name__))

    async def run(self) -> HealthReport:
        self._check_protocol()
        self._check_schemas()
        self._check_triggers()
        self._check_dependencies()
        await self._check_execute()
        self.report.passed = not any(i.severity == "error" for i in self.report.issues)
        return self.report

    def _check_protocol(self) -> None:
        self.report.checks_run.append("protocol")
        name = self.report.skill_name

        if not hasattr(self.skill, "input_schema"):
            self.report.add("error", "input_schema", f"{name}: 缺少 input_schema 属性")
        elif not isinstance(self.skill.input_schema, SkillInput):
            self.report.add("error", "input_schema", f"{name}: input_schema 类型不是 SkillInput")

        if not hasattr(self.skill, "output_schema"):
            self.report.add("error", "output_schema", f"{name}: 缺少 output_schema 属性")
        elif not isinstance(self.skill.output_schema, SkillOutput):
            self.report.add("error", "output_schema", f"{name}: output_schema 类型不是 SkillOutput")

        if not hasattr(self.skill, "trigger_rules"):
            self.report.add("error", "trigger_rules", f"{name}: 缺少 trigger_rules 属性")

        if not hasattr(self.skill, "dependencies"):
            self.report.add("error", "dependencies", f"{name}: 缺少 dependencies 属性")

        if not hasattr(self.skill, "execute"):
            self.report.add("error", "execute", f"{name}: 缺少 execute 方法")

    def _check_schemas(self) -> None:
        self.report.checks_run.append("schemas")
        name = self.report.skill_name

        try:
            inp = self.skill.input_schema
            if inp.required:
                for field_name in inp.required:
                    if field_name not in inp.schema:
                        self.report.add(
                            "warning", "input_schema",
                            f"{name}: required 字段 '{field_name}' 未在 schema 中声明类型",
                        )
        except Exception as exc:
            self.report.add("error", "input_schema", f"{name}: 解析 input_schema 失败: {exc}")

        try:
            out = self.skill.output_schema
            if out.produces:
                for field_name in out.produces:
                    if field_name not in out.schema:
                        self.report.add(
                            "warning", "output_schema",
                            f"{name}: produces 字段 '{field_name}' 未在 schema 中声明类型",
                        )
        except Exception as exc:
            self.report.add("error", "output_schema", f"{name}: 解析 output_schema 失败: {exc}")

        # 检查 name 是否有效
        if not name or not isinstance(name, str):
            self.report.add("error", "name", f"SKILL name 无效: {name!r}")

    def _check_triggers(self) -> None:
        self.report.checks_run.append("triggers")
        try:
            triggers = self.skill.trigger_rules
            if not isinstance(triggers, list):
                self.report.add("error", "trigger_rules", "trigger_rules 必须是 list[str]")
            else:
                for t in triggers:
                    if not isinstance(t, str):
                        self.report.add("error", "trigger_rules", f"trigger_rule 元素必须是 str，得到 {type(t)}")
        except Exception as exc:
            self.report.add("error", "trigger_rules", f"读取 trigger_rules 失败: {exc}")

    def _check_dependencies(self) -> None:
        self.report.checks_run.append("dependencies")
        try:
            deps = self.skill.dependencies
            if not isinstance(deps, list):
                self.report.add("error", "dependencies", "dependencies 必须是 list[str]")
            else:
                for d in deps:
                    if not isinstance(d, str):
                        self.report.add("error", "dependencies", f"dependency 元素必须是 str，得到 {type(d)}")
        except Exception as exc:
            self.report.add("error", "dependencies", f"读取 dependencies 失败: {exc}")

    async def _check_execute(self) -> None:
        self.report.checks_run.append("execute")
        name = self.report.skill_name
        try:
            out_schema = self.skill.output_schema
            inp_schema = self.skill.input_schema

            minimal_ctx: Dict[str, Any] = {}
            for req in inp_schema.required:
                schema_type = inp_schema.schema.get(req, str)
                if schema_type is str:
                    minimal_ctx[req] = "test"
                elif schema_type is list:
                    minimal_ctx[req] = []
                elif schema_type is int:
                    minimal_ctx[req] = 0
                elif schema_type is bool:
                    minimal_ctx[req] = False
                elif schema_type is dict:
                    minimal_ctx[req] = {}
                else:
                    minimal_ctx[req] = None

            result = await self.skill.execute(minimal_ctx)

            if not isinstance(result, dict):
                self.report.add("error", "execute", f"{name}: execute() 必须返回 dict，得到 {type(result)}")
                return

            for field_name in out_schema.produces:
                if field_name not in result:
                    self.report.add(
                        "error", "execute",
                        f"{name}: 声明 produces '{field_name}' 但 execute() 未返回",
                    )

        except Exception as exc:
            self.report.add("error", "execute", f"{name}: execute() 异常: {exc}")


def discover_skills(package_path: str = "skills") -> List[Skill]:
    """在 skills/ 包下扫描所有 SKILL 模块，返回 Skill 实例列表。"""
    skills: List[Skill] = []
    try:
        package = importlib.import_module(package_path)
        for _, mod_name, is_pkg in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
            if mod_name.endswith(".__init__"):
                continue
            try:
                module = importlib.import_module(mod_name)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and attr.__name__.endswith("Skill")
                        and isinstance(attr, Skill)
                        and attr is not Skill
                    ):
                        skills.append(attr())
                    elif (
                        not isinstance(attr, type)
                        and isinstance(attr, Skill)
                        and not isinstance(attr, type)
                    ):
                        skills.append(attr)
            except Exception:
                continue
    except ModuleNotFoundError:
        pass
    return skills


async def run_skill_diagnostics() -> Dict[str, HealthReport]:
    """扫描所有 SKILL 并运行健康检查。CI 入口。"""
    skills = discover_skills()
    reports: Dict[str, HealthReport] = {}
    for skill in skills:
        checker = SkillHealthCheck(skill)
        report = await checker.run()
        report.passed = not any(i.severity == "error" for i in report.issues)
        reports[report.skill_name] = report
    return reports
