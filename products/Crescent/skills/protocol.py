"""SKILL 接口协议 — 每个器官模块的契约。

参考 2026 SKILL 架构五要素：输入校验、核心逻辑、输出校验、触发规则、依赖声明。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, runtime_checkable


@dataclass
class SkillInput:
    """输入校验：定义和验证输入参数的类型、格式、必填项。

    每个 SKILL 声明它需要什么字段、什么类型、是否必填。
    图编排引擎在执行前据此校验 Context 是否满足前置条件。
    """

    required: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)
    schema: Dict[str, type] = field(default_factory=dict)

    def validate(self, ctx: Dict[str, Any]) -> List[str]:
        """校验 ctx 是否满足输入要求，返回缺失字段列表。"""
        missing = [k for k in self.required if k not in ctx]
        return missing


@dataclass
class SkillOutput:
    """输出校验：声明输出字段及其类型。

    每个 SKILL 声明它会产出什么字段，图编排引擎据此更新 Context，
    下游节点据此判断自己的输入是否满足。
    """

    produces: List[str] = field(default_factory=list)
    schema: Dict[str, type] = field(default_factory=dict)


@runtime_checkable
class Skill(Protocol):
    """SKILL 单元协议。

    每个 SKILL 单元 = 输入校验 + 核心逻辑 + 输出校验 + 触发规则 + 依赖声明。
    器官之间不互相 import，只通过图编排层调度。
    """

    @property
    def input_schema(self) -> SkillInput:
        ...

    @property
    def output_schema(self) -> SkillOutput:
        ...

    @property
    def trigger_rules(self) -> List[str]:
        """触发条件列表，如 ['on_direction_confirmed', 'always']。"""
        ...

    @property
    def dependencies(self) -> List[str]:
        """声明依赖的其他 SKILL 名称（仅声明，不 import）。"""
        ...

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """核心逻辑：读 ctx，返回新字段（不就地修改 ctx）。

        返回的 dict 会被合并到共享 Context 中。如果返回空 dict，
        表示该节点未产生新信息（如条件不满足跳过）。
        """
        ...
