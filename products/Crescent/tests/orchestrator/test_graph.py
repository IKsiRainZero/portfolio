"""图编排引擎集成测试 — 模拟 Workbench 5 阶段流程的正向、跳步、回溯。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest

from orchestrator.context import SkillContext
from orchestrator.graph import Graph
from skills.protocol import Skill, SkillInput, SkillOutput


# ── Mock SKILL 实现 ──


@dataclass
class BaseSkill:
    """每个 mock 器官 = 读取指定字段，产出新字段。"""

    name: str
    required_inputs: List[str] = field(default_factory=list)
    produces: Dict[str, Any] = field(default_factory=dict)

    @property
    def input_schema(self) -> SkillInput:
        return SkillInput(required=self.required_inputs)

    @property
    def output_schema(self) -> SkillOutput:
        return SkillOutput(produces=list(self.produces.keys()))

    @property
    def trigger_rules(self) -> List[str]:
        return ["always"]

    @property
    def dependencies(self) -> List[str]:
        return []

    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self.produces)


# ── Fixtures ──


@pytest.fixture
def workbench_graph():
    """构建标准 Workbench 图：
    profile → direction → gap → path → action
    带一条回溯边：gap → direction (needs_reprofile=true)
    带一条跳步边：profile → action (skip_all=true)
    """
    g = Graph()
    g.add_node("profile", BaseSkill("profile", produces={"profile": {"skills": ["Python", "React"]}}))
    g.add_node("direction", BaseSkill("direction", required_inputs=["profile"],
                                      produces={"direction": {"match": "Full-Stack"}}))
    g.add_node("gap", BaseSkill("gap", required_inputs=["profile", "direction"],
                                produces={"gap": {"missing": ["Rust"]}}))
    g.add_node("path", BaseSkill("path", required_inputs=["gap"],
                                 produces={"path": {"phases": ["Learn Rust", "Build project"]}}))
    g.add_node("action", BaseSkill("action", required_inputs=["path"],
                                   produces={"action": {"tasks": ["Do project"]}}))

    g.add_edge("profile", "direction")
    g.add_edge("direction", "gap")
    g.add_edge("gap", "path")
    g.add_edge("path", "action")
    # 回溯边
    g.add_edge("gap", "direction", condition=lambda ctx: ctx.get("needs_reprofile", False))
    # 跳步边
    g.add_edge("profile", "action", condition=lambda ctx: ctx.get("skip_all", False))

    return g


# ── 测试 ──


@pytest.mark.asyncio
async def test_forward_pass(workbench_graph):
    """正向 5 步：profile → direction → gap → path → action。"""
    ctx = SkillContext()
    result = await workbench_graph.execute(ctx, entry="profile")

    assert result.completed
    assert result.path == ["profile", "direction", "gap", "path", "action"]
    assert ctx.get("profile") == {"skills": ["Python", "React"]}
    assert ctx.get("direction") == {"match": "Full-Stack"}
    assert ctx.get("gap") == {"missing": ["Rust"]}
    assert ctx.get("action") == {"tasks": ["Do project"]}


@pytest.mark.asyncio
async def test_skip_with_condition():
    """条件跳步：skip_all=true → profile 直接到 action，中间节点被跳过。"""
    g = Graph()
    g.add_node("profile", BaseSkill("profile", produces={"profile": "v1"}))
    g.add_node("direction", BaseSkill("direction", required_inputs=["profile"],
                                      produces={"direction": "Full-Stack"}))
    g.add_node("gap", BaseSkill("gap", required_inputs=["profile", "direction"],
                                produces={"gap": "ok"}))
    g.add_node("path", BaseSkill("path", required_inputs=["gap"],
                                 produces={"path": "done"}))
    g.add_node("action", BaseSkill("action", produces={"action": "done"}))

    # 正向边：仅在未跳步时生效
    g.add_edge("profile", "direction", condition=lambda ctx: not ctx.get("skip_all", False))
    # 跳步边：直接到 action
    g.add_edge("profile", "action", condition=lambda ctx: ctx.get("skip_all", False))
    g.add_edge("direction", "gap")
    g.add_edge("gap", "path")
    g.add_edge("path", "action")

    ctx = SkillContext()
    ctx.data["skip_all"] = True
    result = await g.execute(ctx, entry="profile")

    assert result.completed
    assert "direction" not in result.path
    assert "gap" not in result.path
    assert "path" not in result.path
    assert "action" in result.path


@pytest.mark.asyncio
async def test_backtrack():
    """回溯：gap 完成后 needs_reprofile=true → 回到 direction 重新匹配。"""
    g = Graph()

    # direction 计数器：第二次执行时产出不同结果
    dir_count = [0]

    class DirectionSkill(BaseSkill):
        async def execute(self, ctx):
            dir_count[0] += 1
            return {"direction": f"match_v{dir_count[0]}"}

    g.add_node("profile", BaseSkill("profile", produces={"profile": "v1"}))
    g.add_node("direction", DirectionSkill("direction", required_inputs=["profile"]))
    # gap 第一次产出 needs_reprofile=True，第二次（回溯后）清除标志
    gap_count = [0]

    class GapSkill(BaseSkill):
        async def execute(self, ctx):
            gap_count[0] += 1
            if gap_count[0] == 1:
                return {"gap": "ok", "needs_reprofile": True}
            return {"gap": "done", "needs_reprofile": False}

    g.add_node("gap", GapSkill("gap", required_inputs=["profile", "direction"]))
    g.add_node("path", BaseSkill("path", required_inputs=["gap"],
                                 produces={"path": "done"}))
    g.add_node("action", BaseSkill("action", required_inputs=["path"],
                                   produces={"action": "done"}))

    g.add_edge("profile", "direction")
    g.add_edge("direction", "gap")
    g.add_edge("gap", "path")
    g.add_edge("path", "action")
    g.add_edge("gap", "direction", condition=lambda ctx: ctx.get("needs_reprofile", False))

    ctx = SkillContext()
    result = await g.execute(ctx, entry="profile")

    assert "direction" in result.path
    # direction 应出现两次（第一次从 profile 来，第二次从 gap 回溯）
    assert result.path.count("direction") == 2
    assert ctx.get("gap") == "done"  # 最终是第二次执行的结果


@pytest.mark.asyncio
async def test_missing_input_skips():
    """输入不满足时节点被跳过。"""
    g = Graph()
    g.add_node("step1", BaseSkill("step1", produces={"a": 1}))
    g.add_node("step2", BaseSkill("step2", required_inputs=["missing_field"],
                                  produces={"b": 2}))
    g.add_node("step3", BaseSkill("step3", produces={"c": 3}))

    g.add_edge("step1", "step2")
    g.add_edge("step2", "step3")
    g.add_edge("step1", "step3")  # 跳步路径

    ctx = SkillContext()
    result = await g.execute(ctx, entry="step1")

    assert "step2" not in result.path  # 输入不满足，被跳过
    assert "step3" in result.path  # 通过跳步路径到达


@pytest.mark.asyncio
async def test_invalid_entry():
    """入口节点不存在时返回错误。"""
    g = Graph()
    ctx = SkillContext()
    result = await g.execute(ctx, entry="no_such_node")

    assert not result.completed
    assert "未注册" in result.error


@pytest.mark.asyncio
async def test_trace_history(workbench_graph):
    """执行后 history 记录每个节点的 trace。"""
    ctx = SkillContext()
    await workbench_graph.execute(ctx, entry="profile")

    assert len(ctx.history) == 5
    assert ctx.history[0].node == "profile"
    assert ctx.history[0].duration_ms >= 0
    assert "profile" in ctx.history[0].output_keys
