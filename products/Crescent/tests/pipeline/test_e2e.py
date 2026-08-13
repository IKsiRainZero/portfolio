"""E2E integration tests for the research pipeline."""

from __future__ import annotations

from unittest.mock import patch

from services.pipeline.e2e import build_research_pipeline, ResearchOrchestrator
from services.pipeline.types import PipelineSpec, StepSpec


def test_build_research_pipeline_registers_all_steps():
    orch = build_research_pipeline()
    assert len(orch._step_map) >= 4  # S1, S3_search, S3_fetch, S4, S5


@patch("services.pipeline.search.search_web")
@patch("services.pipeline.fetcher.fetch_url")
@patch("services.pipeline.intent_parser.chat")
@patch("services.pipeline.credibility.chat")
@patch("services.pipeline.plan_generator.chat")
def test_full_pipeline_mocked(mock_plan, mock_cred, mock_intent, mock_fetch, mock_search):
    import json

    # Mock 搜索
    mock_search.return_value = [
        {"url": "https://arxiv.org/abs/1706.03762", "title": "Attention Is All You Need", "snippet": "The dominant sequence transduction model..."}
    ]
    # Mock 抓取
    mock_fetch.return_value = "<html><head><title>Attention Is All You Need</title></head><body><p>The Transformer architecture relies entirely on self-attention.</p></body></html>"
    # Mock 意图解析 — 使用实际 pipeline 的 step_name（S3_search, S3_fetch 而非 S3）
    mock_intent.return_value = (json.dumps({
        "steps": [
            {"step_name": "S1", "enabled": True},
            {"step_name": "S2", "enabled": False},
            {"step_name": "S3_search", "enabled": True, "config": {"max_results": 5}},
            {"step_name": "S3_fetch", "enabled": True},
            {"step_name": "S4", "enabled": True, "config": {"operators": ["relation", "sufficiency"]}},
            {"step_name": "S5", "enabled": True},
        ]
    }), {"total_tokens": 50})
    # Mock 可信度 (一致)
    mock_cred.return_value = ('{"relation": "一致", "confidence": 0.9, "rationale": "Same"}', {"total_tokens": 30})
    # Mock 方案生成
    mock_plan.return_value = (json.dumps({
        "minimal_action": {"what": "阅读Transformer论文", "why": "基础", "steps": ["读abstract"], "estimated_time": "1h"},
        "development_plan": {"phases": []},
        "sources": [{"doc_id": "d1", "key_claim": "...", "credibility": "高可信"}],
        "confidence": 0.85,
        "caveats": [],
    }), {"total_tokens": 200})

    orch = ResearchOrchestrator()
    result = orch.run(query="帮我调研Transformer注意力机制")

    assert result["status"] == "ok"
    assert "S5" in result["outputs"]
    assert "plan" in result["outputs"]["S5"]
    assert result["outputs"]["S5"]["plan"]["minimal_action"]["what"]
    assert len(result["trace"]) > 0
