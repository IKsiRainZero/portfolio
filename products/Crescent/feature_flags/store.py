"""功能开关系统 — 支持灰度发布、A/B 测试、快速回滚。

每个 Flag 有名称、启用状态和描述。开关不仅在路由层生效，
也集成到图编排引擎中：同一图节点位置可注册多个 SKILL 实现，
由开关决定使用哪个。

设计约束（参见 systems-review.md 5.8.2）：
- 开关需与图节点注册机制结合
- 支持全局开关和 per-skill 粒度
- 轻量级，不引入外部配置服务
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class Flag:
    """单个功能开关。"""

    name: str
    enabled: bool = False
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class FeatureFlags:
    """内存中的功能开关注册表。

    ```python
    flags = FeatureFlags()
    flags.register("new_skill_matcher", enabled=False, description="Use new matching algorithm")

    if flags.is_enabled("new_skill_matcher"):
        graph.add_node("direction", NewSkillMatcher())
    else:
        graph.add_node("direction", OldSkillMatcher())
    ```
    """

    def __init__(self):
        self._flags: Dict[str, Flag] = {}

    def register(self, name: str, enabled: bool = False,
                 description: str = "", **meta) -> Flag:
        if name in self._flags:
            raise ValueError(f"Flag '{name}' 已存在")
        flag = Flag(name=name, enabled=enabled, description=description, metadata=meta)
        self._flags[name] = flag
        return flag

    def is_enabled(self, name: str) -> bool:
        flag = self._flags.get(name)
        return flag.enabled if flag else False

    def enable(self, name: str) -> None:
        if name not in self._flags:
            raise KeyError(f"Flag '{name}' 未注册")
        self._flags[name].enabled = True

    def disable(self, name: str) -> None:
        if name not in self._flags:
            raise KeyError(f"Flag '{name}' 未注册")
        self._flags[name].enabled = False

    def toggle(self, name: str) -> bool:
        flag = self._flags.get(name)
        if not flag:
            raise KeyError(f"Flag '{name}' 未注册")
        flag.enabled = not flag.enabled
        return flag.enabled

    def pick(self, name: str, when_enabled: Any, when_disabled: Any) -> Any:
        """根据开关选择值，用于图节点注册时的 SKILL 二选一。"""
        return when_enabled if self.is_enabled(name) else when_disabled

    def list_enabled(self) -> List[str]:
        return [f.name for f in self._flags.values() if f.enabled]

    def list_all(self) -> Dict[str, bool]:
        return {name: f.enabled for name, f in self._flags.items()}
