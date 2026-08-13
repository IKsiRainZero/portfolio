"""
golden_dataset — 动态 Golden Dataset: 手工标注的 Trace 作为评估基准

Phase 4 Step 2. Golden Dataset 是 LLM Judge 的第三方参照：
  - Judge vs Golden 对比评估 Judge 质量
  - Golden 自身可演进 (Judge 重新判定 → Golden 可能过时需要更新)
  - 从 Dashboard Trace 详情页手动添加
"""
import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "eval"
DATASET_FILE = DATA_DIR / "golden_dataset.json"

DEFAULT_DATASET = {
    "version": 1,
    "created_at": datetime.now().isoformat(),
    "samples": [],
}


def _read_dataset():
    """读取 Golden Dataset 文件。不存在时返回默认空数据集。"""
    if not DATASET_FILE.exists():
        return dict(DEFAULT_DATASET)
    try:
        with open(DATASET_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return dict(DEFAULT_DATASET)


def _write_dataset(data):
    """写入 Golden Dataset 文件。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATASET_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_dataset():
    """加载 Golden Dataset 中的所有样本。"""
    return _read_dataset().get("samples", [])


def add_sample(*, trace_id, trace_name, trace_type, expected_completeness,
               expected_tool_accuracy=None, annotated_by="human", notes=""):
    """
    添加一个手工标注样本到 Golden Dataset。

    参数:
      - trace_id: 关联的 Trace ID
      - trace_name: Trace 名称 (如 /api/agent/chat)
      - trace_type: Trace 类型 (agent_chat / rag_query / ...)
      - expected_completeness: 人工判断是否数据完整 (bool)
      - expected_tool_accuracy: 人工判断工具准确度 (0.0-1.0, 可选)
      - annotated_by: 标注者 ("human" / "judge")
      - notes: 标注备注
    """
    dataset = _read_dataset()
    samples = dataset.get("samples", [])

    # 幂等: 同一 trace_id 覆盖
    existing = [s for s in samples if s.get("trace_id") == trace_id]
    for s in existing:
        samples.remove(s)

    sample = {
        "sample_id": f"golden_{len(samples) + 1:03d}",
        "trace_id": trace_id,
        "trace_name": trace_name,
        "trace_type": trace_type,
        "expected_completeness": expected_completeness,
        "expected_tool_accuracy": expected_tool_accuracy,
        "annotated_by": annotated_by,
        "annotated_at": datetime.now().isoformat(),
        "notes": notes,
    }
    samples.append(sample)
    dataset["samples"] = samples
    dataset["version"] = dataset.get("version", 1) + 1
    _write_dataset(dataset)
    return sample


def evaluate_against(judge_results):
    """
    对比 LLM Judge 判定 vs Golden Dataset 预期。

    参数:
      judge_results: [{"trace_id": ..., "judgment": "complete"|"incomplete", ...}, ...]

    返回:
      {"accuracy": float, "matched": int, "total": int, "mismatches": [...]}
    """
    golden_samples = {s["trace_id"]: s for s in load_dataset()}
    if not golden_samples:
        return {"accuracy": None, "matched": 0, "total": 0, "mismatches": [], "note": "Golden Dataset is empty"}

    matched = 0
    total = 0
    mismatches = []

    for jr in judge_results:
        tid = jr.get("trace_id")
        if tid not in golden_samples:
            continue
        total += 1
        expected = golden_samples[tid]["expected_completeness"]
        judged = jr.get("judgment") == "complete"
        if expected == judged:
            matched += 1
        else:
            mismatches.append({
                "trace_id": tid,
                "expected": expected,
                "judged": judged,
                "judge_confidence": jr.get("confidence"),
            })

    accuracy = matched / total if total > 0 else None
    return {
        "accuracy": round(accuracy, 4) if accuracy is not None else None,
        "matched": matched,
        "total": total,
        "mismatches": mismatches,
    }


# 首次 import 时自动初始化空数据集
if not DATASET_FILE.exists():
    _write_dataset(DEFAULT_DATASET)
