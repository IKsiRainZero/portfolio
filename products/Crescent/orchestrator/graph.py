"""图编排引擎 — DAG-based workflow orchestration。

将硬编码管道（Profile → Direction → Gap → Path → Action）替换为可自由编排的图。
节点 = SKILL 单元，边 = 数据流 + 路由条件。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from orchestrator.context import SkillContext, TraceEntry
from observability.tracer import Trace
from skills.protocol import Skill


@dataclass
class Edge:
    """图中的边：from_node → to_node，可选条件路由。"""

    source: str
    target: str
    condition: Callable[[SkillContext], bool] | None = None

    def can_traverse(self, ctx: SkillContext) -> bool:
        if self.condition is None:
            return True
        try:
            return self.condition(ctx)
        except Exception:
            return False


@dataclass
class ExecutionResult:
    """图执行结果。"""

    ctx: SkillContext
    path: List[str]
    completed: bool
    error: str | None = None


class Graph:
    """基于 DAG 的编排引擎。

    ```python
    wf = Graph()
    wf.add_node("profile", ProfileStoreSkill())
    wf.add_node("direction", SkillMatcherSkill())
    wf.add_edge("profile", "direction")
    wf.add_edge("direction", "profile", condition=lambda ctx: ctx.get("needs_reprofile", False))

    result = await wf.execute(ctx, entry="profile")
    ```
    """

    def __init__(self, max_iterations: int = 20, flags=None):
        self._nodes: Dict[str, Skill] = {}
        self._node_flags: Dict[str, str] = {}  # node_name → flag_name
        self._edges: Dict[str, List[Edge]] = {}  # adjacency: source → [edges]
        self._reverse: Dict[str, List[str]] = {}  # reverse adjacency: target → [sources]
        self.max_iterations = max_iterations
        self._flags = flags  # FeatureFlags instance (optional)

    # ── 构建 ──

    def add_node(self, name: str, skill: Skill, flag: str | None = None) -> None:
        """注册节点。若提供 flag 名称，执行时仅在对应开关启用时运行。"""
        if name in self._nodes:
            raise ValueError(f"节点 '{name}' 已存在")
        self._nodes[name] = skill
        if flag:
            self._node_flags[name] = flag
        self._edges.setdefault(name, [])
        self._reverse.setdefault(name, [])

    def add_edge(
        self,
        source: str,
        target: str,
        condition: Callable[[SkillContext], bool] | None = None,
    ) -> None:
        if source not in self._nodes:
            raise ValueError(f"源节点 '{source}' 未注册")
        if target not in self._nodes:
            raise ValueError(f"目标节点 '{target}' 未注册")
        edge = Edge(source=source, target=target, condition=condition)
        self._edges[source].append(edge)
        self._reverse[target].append(source)

    # ── 执行 ──

    async def execute(self, ctx: SkillContext, entry: str,
                      trace: Trace | None = None) -> ExecutionResult:
        """从 entry 节点开始执行图。

        使用 BFS 遍历：当前层所有就绪节点执行完毕后，收集下一层候选，
        按条件边过滤，继续执行。支持回边（回到上游节点）但有迭代上限。

        若传入 Trace，自动为每个节点创建 Span 并记录耗时。
        """
        if entry not in self._nodes:
            return ExecutionResult(ctx=ctx, path=[], completed=False,
                                   error=f"入口节点 '{entry}' 未注册")

        if trace is None:
            trace = Trace()

        path: List[str] = []
        visited_count: Dict[str, int] = {entry: 0}
        queue: deque[str] = deque([entry])

        while queue and len(path) < self.max_iterations:
            node_name = queue.popleft()
            skill = self._nodes[node_name]

            # 校验功能开关
            flag_name = self._node_flags.get(node_name)
            if flag_name and self._flags and not self._flags.is_enabled(flag_name):
                continue

            # 校验输入
            missing = skill.input_schema.validate(ctx.data)
            if missing:
                continue

            # 执行（带 span）
            span = trace.start_span(node_name)
            try:
                outputs = await skill.execute(ctx.snapshot())
            except Exception as exc:
                span.finish(error=str(exc))
                trace.finish(error=f"节点 '{node_name}' 执行失败: {exc}")
                return ExecutionResult(
                    ctx=ctx, path=path, completed=False,
                    error=f"节点 '{node_name}' 执行失败: {exc}",
                )
            span.finish()

            # 合并输出
            ctx.update(node_name, outputs)
            path.append(node_name)

            # 记录 trace
            ctx.history.append(TraceEntry(
                node=node_name,
                input_keys=skill.input_schema.required + skill.input_schema.optional,
                output_keys=list(outputs.keys()),
                duration_ms=round(span.duration_ms, 2),
            ))

            # 收集下一层候选
            for edge in self._edges.get(node_name, []):
                if edge.can_traverse(ctx):
                    target = edge.target
                    count = visited_count.get(target, 0)
                    if count < 3:
                        visited_count[target] = count + 1
                        if target not in queue:
                            queue.append(target)

        trace.finish()

        return ExecutionResult(
            ctx=ctx, path=path,
            completed=len(path) < self.max_iterations or not queue,
        )

    # ── 查询 ──

    @property
    def nodes(self) -> List[str]:
        return list(self._nodes.keys())

    def edges_from(self, node: str) -> List[Edge]:
        return list(self._edges.get(node, []))
