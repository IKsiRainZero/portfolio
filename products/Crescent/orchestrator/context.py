"""共享上下文 — 贯穿所有 SKILL 节点的数据载体。

设计约束（参见 systems-review.md 5.8.1）：
- Context 为不可变快照 — 节点不就地修改，只返回新字段
- 每个节点只读取自己声明的依赖字段
- 合并由引擎负责，保证字段来源可追溯
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class TraceEntry:
    """单步执行记录。"""

    node: str
    input_keys: List[str]
    output_keys: List[str]
    duration_ms: float
    error: str | None = None


@dataclass
class SkillContext:
    """图编排的共享上下文。

    节点通过 execute(ctx) 只读访问，返回 Dict[str, Any] 表示新产出字段。
    引擎负责合并并记录来源。
    """

    data: Dict[str, Any] = field(default_factory=dict)
    history: List[TraceEntry] = field(default_factory=list)

    # 引擎内部控制字段
    _node_outputs: Dict[str, List[str]] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def update(self, node_name: str, outputs: Dict[str, Any]) -> None:
        """由引擎调用：合并节点输出到上下文，记录来源。"""
        self.data.update(outputs)
        self._node_outputs.setdefault(node_name, []).extend(outputs.keys())

    def produced_by(self, key: str) -> str | None:
        """查询某个字段由哪个节点产出。"""
        for node, keys in self._node_outputs.items():
            if key in keys:
                return node
        return None

    def snapshot(self) -> Dict[str, Any]:
        """返回当前数据的浅拷贝。"""
        return dict(self.data)
