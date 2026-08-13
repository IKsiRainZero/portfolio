"""功能开关系统测试。"""

from __future__ import annotations

import pytest

from feature_flags.store import FeatureFlags, Flag


class TestFeatureFlags:
    def test_register_and_check(self):
        ff = FeatureFlags()
        ff.register("new_matcher", enabled=False, description="test flag")

        assert not ff.is_enabled("new_matcher")
        assert ff.is_enabled("nonexistent") is False

    def test_enable_disable(self):
        ff = FeatureFlags()
        ff.register("dark_mode")
        assert not ff.is_enabled("dark_mode")

        ff.enable("dark_mode")
        assert ff.is_enabled("dark_mode")

        ff.disable("dark_mode")
        assert not ff.is_enabled("dark_mode")

    def test_toggle(self):
        ff = FeatureFlags()
        ff.register("beta")

        assert ff.toggle("beta") is True
        assert ff.is_enabled("beta")

        assert ff.toggle("beta") is False
        assert not ff.is_enabled("beta")

    def test_pick(self):
        ff = FeatureFlags()
        ff.register("use_v2", enabled=True)

        result = ff.pick("use_v2", when_enabled="V2_IMPL", when_disabled="V1_IMPL")
        assert result == "V2_IMPL"

        ff.disable("use_v2")
        result = ff.pick("use_v2", when_enabled="V2_IMPL", when_disabled="V1_IMPL")
        assert result == "V1_IMPL"

    def test_list_enabled(self):
        ff = FeatureFlags()
        ff.register("a", enabled=True)
        ff.register("b", enabled=False)
        ff.register("c", enabled=True)

        assert sorted(ff.list_enabled()) == ["a", "c"]

    def test_list_all(self):
        ff = FeatureFlags()
        ff.register("x", enabled=True)
        ff.register("y", enabled=False)

        assert ff.list_all() == {"x": True, "y": False}

    def test_duplicate_register_raises(self):
        ff = FeatureFlags()
        ff.register("f1")
        with pytest.raises(ValueError, match="已存在"):
            ff.register("f1")

    def test_toggle_nonexistent_raises(self):
        ff = FeatureFlags()
        with pytest.raises(KeyError):
            ff.toggle("ghost")


@pytest.mark.asyncio
async def test_graph_flag_guard():
    """被禁用 flag 保护的节点在图中被跳过。"""
    from feature_flags.store import FeatureFlags
    from orchestrator.context import SkillContext
    from orchestrator.graph import Graph
    from tests.orchestrator.test_graph import BaseSkill

    flags = FeatureFlags()
    flags.register("new_gap_analyzer", enabled=False)

    g = Graph(flags=flags)
    g.add_node("profile", BaseSkill("profile", produces={"profile": "v1"}))
    g.add_node("direction", BaseSkill("direction", required_inputs=["profile"],
                                      produces={"direction": "match"}))
    # 新 gap 分析器 — 被 flag 禁用
    g.add_node("gap", BaseSkill("gap", required_inputs=["profile", "direction"],
                                produces={"gap": "analyzed"}), flag="new_gap_analyzer")
    g.add_node("path", BaseSkill("path", required_inputs=["gap"],
                                 produces={"path": "done"}))
    g.add_node("action", BaseSkill("action", required_inputs=["path"],
                                   produces={"action": "done"}))

    g.add_edge("profile", "direction")
    g.add_edge("direction", "gap")
    g.add_edge("gap", "path")
    g.add_edge("path", "action")

    ctx = SkillContext()
    result = await g.execute(ctx, entry="profile")

    # gap 被跳过，path 和 action 也因缺少输入而被跳过
    assert "gap" not in result.path
    assert "path" not in result.path
    assert "action" not in result.path

    # 启用 flag 后重新执行
    flags.enable("new_gap_analyzer")
    ctx2 = SkillContext()
    result2 = await g.execute(ctx2, entry="profile")

    assert "gap" in result2.path
    assert "action" in result2.path
