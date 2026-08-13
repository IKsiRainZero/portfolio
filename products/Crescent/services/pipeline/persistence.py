from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from services.pipeline.protocols import Step
from services.pipeline.types import StepInput, StepOutput


class PersistenceStep:
    """S7: 将管道全量输出持久化到磁盘。"""

    def __init__(self, name: str = "S7", output_dir: str | None = None):
        self.name = name
        self._output_dir = output_dir or str(
            Path(__file__).parent.parent.parent / "data" / "pipeline_runs"
        )

    def can_skip(self, input: StepInput) -> bool:
        return False

    def run(self, input: StepInput) -> StepOutput:
        os.makedirs(self._output_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        query_slug = input.query[:30].replace(" ", "_").replace("/", "_")
        run_id = f"{ts}-{query_slug}"

        # ── Trace log ──
        trace_path = os.path.join(self._output_dir, f"{run_id}-trace.json")
        trace_data = {
            "run_id": run_id,
            "pipeline": {
                "query": input.query,
                "spec_version": input.pipeline_spec.version if input.pipeline_spec else 1,
            },
            "outputs": _serialize_for_json(input.previous_outputs),
        }
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, ensure_ascii=False, indent=2, default=str)

        # ── Decision record ──
        decision_path = os.path.join(self._output_dir, f"{run_id}-decision.json")
        s5 = input.previous_outputs.get("S5", {})
        s4 = input.previous_outputs.get("S4", {})
        decision_data = {
            "run_id": run_id,
            "query": input.query,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "plan": s5.get("plan", {}),
            "sources": _serialize_for_json(s5.get("sources", [])),
            "credibility_summary": {
                "total_docs": len(s4.get("documents", [])),
                "conflicts": len(s4.get("conflicts", [])),
            },
        }
        with open(decision_path, "w", encoding="utf-8") as f:
            json.dump(decision_data, f, ensure_ascii=False, indent=2, default=str)

        # ── KG updates (增量) ──
        kg_updates = _extract_kg_updates(input.previous_outputs)

        return StepOutput(
            step_name=self.name,
            status="ok",
            data={
                "trace_path": trace_path,
                "decision_path": decision_path,
                "kg_updates": kg_updates,
                "run_id": run_id,
            },
            confidence=1.0,
        )


def _serialize_for_json(obj):
    """递归转换 dataclass/复杂对象为 JSON 安全类型。"""
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(obj)
    if isinstance(obj, dict):
        return {str(k): _serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item) for item in obj]
    return obj


def _extract_kg_updates(previous_outputs: dict) -> dict:
    """从管道输出中提取知识图谱增量更新。"""
    entities = set()
    relations = []

    s4 = previous_outputs.get("S4", {})
    for doc in s4.get("documents", []):
        tags = doc.tags if hasattr(doc, "tags") else doc.get("tags", [])
        for tag in tags:
            entities.add(tag)

    s5 = previous_outputs.get("S5", {})
    plan = s5.get("plan", {})
    if isinstance(plan, dict):
        action = plan.get("minimal_action", {})
        if action and action.get("what"):
            entities.add(action["what"][:60])

    return {"entities": list(entities)[:20], "relations": relations}
