from __future__ import annotations
from services.pipeline.protocols import Step
from services.pipeline.types import StepInput, PipelineSpec, StepSpec
from services.pipeline.trace_logger import TraceLogger


class Orchestrator:
    def __init__(self, steps: list[Step], trace_logger: TraceLogger | None = None):
        for s in steps:
            assert isinstance(s, Step), f"{type(s).__name__} does not implement Step protocol"
        self._step_map: dict[str, Step] = {s.name: s for s in steps}
        self.trace = trace_logger or TraceLogger()

    def run(self, query: str, spec: PipelineSpec) -> dict:
        outputs: dict[str, dict] = {}
        active_spec = spec
        i = 0

        while i < len(active_spec.steps):
            step_spec = active_spec.steps[i]

            if not step_spec.enabled:
                i += 1
                continue

            step = self._step_map.get(step_spec.step_name)
            if step is None:
                self.trace.log("step_error", step_spec.step_name, {"reason": "step_not_found"})
                outputs[step_spec.step_name] = {"status": "error", "error": "step not registered"}
                return {"status": "error", "outputs": outputs, "trace": self.trace.to_list()}

            if step.can_skip(StepInput(query=query, previous_outputs=outputs, config=step_spec.config)):
                outputs[step_spec.step_name] = {"status": "skipped"}
                i += 1
                continue

            self.trace.log("step_start", step_spec.step_name)
            try:
                result = step.run(StepInput(
                    query=query,
                    previous_outputs=outputs,
                    pipeline_spec=active_spec,
                    config=step_spec.config,
                ))
            except Exception as exc:
                self.trace.log("step_error", step_spec.step_name, {"exception": str(exc)})
                outputs[step_spec.step_name] = {"status": "error", "error": str(exc)}
                return {"status": "error", "outputs": outputs, "trace": self.trace.to_list()}

            self.trace.log("step_end", step_spec.step_name,
                           {"status": result.status, "confidence": result.confidence})
            outputs[step_spec.step_name] = {"status": result.status, **result.data}

            # ── S1 集成：消费 S1 输出的 PipelineSpec ──
            if step_spec.step_name == "S1" and result.status == "ok":
                new_spec = result.data.get("pipeline_spec")
                if isinstance(new_spec, PipelineSpec):
                    merged_steps = _merge_specs(active_spec, new_spec)
                    active_spec = PipelineSpec(
                        steps=merged_steps,
                        version=active_spec.version + 1,
                        created_at=active_spec.created_at,
                        updated_at=new_spec.updated_at or new_spec.created_at,
                    )
                    self.trace.log("spec_changed", "S1",
                                   {"old_version": spec.version, "new_version": active_spec.version})

            if result.status == "error":
                return {"status": "error", "outputs": outputs, "trace": self.trace.to_list()}

            if result.status == "needs_human":
                return {
                    "status": "needs_human",
                    "question": result.human_question,
                    "outputs": outputs,
                    "trace": self.trace.to_list(),
                }

            i += 1

        return {"status": "ok", "outputs": outputs, "trace": self.trace.to_list()}


def _merge_specs(original: PipelineSpec, from_s1: PipelineSpec) -> list[StepSpec]:
    """合并两个 PipelineSpec：S1 的决定优先，S1 未提及的步骤保持原样。"""
    s1_map: dict[str, StepSpec] = {s.step_name: s for s in from_s1.steps}
    merged = []
    for s in original.steps:
        if s.step_name in s1_map:
            s1_step = s1_map[s.step_name]
            merged.append(StepSpec(
                step_name=s.step_name,
                enabled=s1_step.enabled,
                needs_human=s1_step.needs_human,
                config={**s.config, **s1_step.config},
                depends_on=s1_step.depends_on or s.depends_on,
            ))
        else:
            merged.append(s)
    # 添加 S1 新增的步骤（原始 spec 中没有的）
    original_names = {s.step_name for s in original.steps}
    for s in from_s1.steps:
        if s.step_name not in original_names:
            merged.append(s)
    return merged
