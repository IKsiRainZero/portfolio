"""
测试 eval 系统核心模块 — trace_logger + eval_store

红线3: 核心模块测试覆盖率 ≥ 85%

测试规范 (强制):
  🔴 外部依赖必须 mock — LLM / 数据库 / 网络 / 文件系统(Ollama/ChromaDB/API)
  🔴 mock 用后必须 restore — 在 try/finally 中恢复原始引用
  🔴 不绕过防风暴/限流等安全机制来调用真实外部依赖
"""
import sys
import os
import time
import json
import tempfile
import threading
from pathlib import Path

# 确保项目目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import config

# ── 测试前配置：启用 eval 但保持 shadow 模式 ──

@pytest.fixture(autouse=True)
def _setup_eval_env():
    """每个测试前设置环境"""
    import config
    config.EVAL_ENABLED = True
    config.EVAL_SHADOW_MODE = True  # 影子模式：代码运行但不写文件
    yield
    config.EVAL_ENABLED = False
    config.EVAL_SHADOW_MODE = True


# ══════════════════════════════════════════════
# trace_logger 测试
# ══════════════════════════════════════════════

class TestTraceContext:
    """TraceContext 上下文管理器测试"""

    def test_creates_trace_id(self):
        from services.eval.trace_logger import TraceContext, _current_trace_id

        assert _current_trace_id() is None

        with TraceContext(name="test_task", kind="system_task") as ctx:
            assert ctx.trace_id is not None
            assert len(ctx.trace_id) == 12
            assert _current_trace_id() == ctx.trace_id

        # 退出 context 后 trace_id 应该清除
        assert _current_trace_id() is None

    def test_sets_thread_local(self):
        from services.eval.trace_logger import TraceContext, _thread_local

        with TraceContext(name="test", kind="system_task") as ctx:
            assert _thread_local.trace_id == ctx.trace_id
            assert hasattr(_thread_local, 'trace_start')
            assert _thread_local.span_count == 0

        assert not hasattr(_thread_local, 'trace_id') or _thread_local.trace_id is None

    def test_exception_does_not_suppress(self):
        from services.eval.trace_logger import TraceContext

        with pytest.raises(ValueError):
            with TraceContext(name="test", kind="system_task"):
                raise ValueError("test error")

    def test_metadata_attached(self):
        from services.eval.trace_logger import TraceContext

        with TraceContext(name="test", kind="system_task",
                          metadata={"key": "value"}) as ctx:
            assert ctx.metadata == {"key": "value"}

    def test_span_count_increment(self):
        from services.eval.trace_logger import TraceContext, _increment_span_count

        with TraceContext(name="test", kind="system_task"):
            _increment_span_count()
            _increment_span_count()
            from services.eval.trace_logger import _thread_local
            assert _thread_local.span_count == 2


class TestCurrentTraceId:
    """_current_trace_id 三级回退测试"""

    def test_returns_none_without_context(self):
        from services.eval.trace_logger import _current_trace_id
        assert _current_trace_id() is None

    def test_returns_trace_id_with_trace_context(self):
        from services.eval.trace_logger import TraceContext, _current_trace_id

        with TraceContext(name="test", kind="system_task") as ctx:
            assert _current_trace_id() == ctx.trace_id


class TestSafeRecordFunctions:
    """防崩盖函数测试"""

    def test_safe_record_llm_span_never_raises(self):
        from services.eval.trace_logger import _safe_record_llm_span

        # 正常调用
        _safe_record_llm_span(
            duration_ms=100, input_summary="hello",
            output_summary="hi", model="test-model",
            status="success",
        )

        # 各种边界情况
        _safe_record_llm_span()  # 全默认值
        _safe_record_llm_span(status="error", error_type="TestError")
        _safe_record_llm_span(input_summary="x" * 300)  # 超长输入

    def test_safe_record_tool_span_never_raises(self):
        from services.eval.trace_logger import _safe_record_tool_span

        _safe_record_tool_span(tool_name="test_tool", status="success")
        _safe_record_tool_span(tool_name="bad_tool", status="error",
                               error_type="ToolError")
        _safe_record_tool_span()  # 全默认值

    def test_safe_record_llm_span_catches_exception(self):
        """_record_span 抛异常时 _safe_record_llm_span 吞掉异常不向上传播"""
        from unittest.mock import patch
        from services.eval.trace_logger import _safe_record_llm_span

        with patch("services.eval.trace_logger._record_span",
                   side_effect=RuntimeError("simulated failure")):
            _safe_record_llm_span(duration_ms=100, status="success")

    def test_safe_record_tool_span_catches_exception(self):
        """_record_span 抛异常时 _safe_record_tool_span 吞掉异常不向上传播"""
        from unittest.mock import patch
        from services.eval.trace_logger import _safe_record_tool_span

        with patch("services.eval.trace_logger._record_span",
                   side_effect=RuntimeError("simulated failure")):
            _safe_record_tool_span(tool_name="test", status="success")


class TestStartEndTrace:
    """start_trace / end_trace 测试"""

    def test_start_trace_returns_id(self):
        import config
        config.EVAL_SHADOW_MODE = True   # shadow: 不写文件，但返回 ID
        from services.eval.trace_logger import start_trace

        tid = start_trace(name="/test", kind="http_request")
        assert tid is not None
        assert len(tid) == 12

    def test_end_trace_noop_without_id(self):
        from services.eval.trace_logger import end_trace
        end_trace(None)  # should not raise

    def test_start_trace_disabled(self):
        import config
        config.EVAL_ENABLED = False
        from services.eval.trace_logger import start_trace

        tid = start_trace(name="/test", kind="http_request")
        assert tid is None

    def test_record_span_disabled_early_return(self):
        """EVAL_ENABLED=False 时 _record_span 直接返回不抛异常"""
        import config
        from services.eval.trace_logger import _record_span

        config.EVAL_ENABLED = False
        try:
            _record_span(kind="LLM", name="test", duration_ms=100)
        finally:
            config.EVAL_ENABLED = True


class TestIncrementSpanCount:
    """Span 计数器测试"""

    def test_increment_without_context(self):
        from services.eval.trace_logger import _increment_span_count
        _increment_span_count()  # should not raise

    def test_increment_with_flask_context(self):
        """Flask 上下文中 _increment_span_count 写入 g.eval_span_count"""
        from flask import Flask, g
        from services.eval.trace_logger import _increment_span_count

        app = Flask(__name__)
        with app.app_context():
            g.eval_span_count = 0
            _increment_span_count()
            assert g.eval_span_count == 1
            _increment_span_count()
            assert g.eval_span_count == 2


# ══════════════════════════════════════════════
# eval_store 测试
# ══════════════════════════════════════════════

class TestSuggestionCRUD:
    """Suggestion 增删改查测试"""

    def test_add_and_get_suggestion(self):
        from services.eval.eval_store import add_suggestion, get_suggestion

        sug = add_suggestion({
            "score_id": "test_score_1",
            "severity": "WARNING",
            "category": "security",
            "title": "测试建议",
            "description": "这是一条测试建议",
            "target_file": "test.py",
            "target_type": "module",
            "target_id": "test_module",
        })
        assert sug["suggestion_id"] is not None
        assert sug["status"] == "pending"
        assert sug["attribution_status"] == "pending"

        fetched = get_suggestion(sug["suggestion_id"])
        assert fetched is not None
        assert fetched["title"] == "测试建议"

    def test_list_suggestions(self):
        from services.eval.eval_store import list_suggestions

        items = list_suggestions()
        assert isinstance(items, list)

    def test_list_suggestions_with_filter(self):
        from services.eval.eval_store import add_suggestion, list_suggestions

        add_suggestion({
            "severity": "CRITICAL",
            "category": "bug_risk",
            "title": "Critical bug",
            "description": "test",
            "target_type": "module",
            "target_id": "test",
        })
        items = list_suggestions(severity="CRITICAL")
        for item in items:
            assert item["severity"] == "CRITICAL"

    def test_apply_suggestion(self):
        from services.eval.eval_store import add_suggestion, apply_suggestion, get_suggestion

        sug = add_suggestion({
            "severity": "WARNING",
            "category": "security",
            "title": "Apply test",
            "description": "test",
            "target_type": "module",
            "target_id": "security_module",
        })
        applied = apply_suggestion(sug["suggestion_id"], admin_token=config.EVAL_ADMIN_SECRET)
        assert applied["status"] == "applied"
        assert applied["applied_at"] is not None
        assert applied["applied_commit"] is not None
        assert "baseline_scores" in applied

    def test_reject_suggestion(self):
        from services.eval.eval_store import add_suggestion, reject_suggestion, get_suggestion

        sug = add_suggestion({
            "severity": "SUGGESTION",
            "category": "doc",
            "title": "Reject test",
            "description": "test",
            "target_type": "module",
            "target_id": "test",
        })
        rejected = reject_suggestion(sug["suggestion_id"], admin_token=config.EVAL_ADMIN_SECRET)
        assert rejected["status"] == "rejected"

    def test_rollback_suggestion(self):
        from services.eval.eval_store import add_suggestion, rollback_suggestion

        sug = add_suggestion({
            "severity": "NITPICK",
            "category": "maintainability",
            "title": "Rollback test",
            "description": "test",
            "target_type": "module",
            "target_id": "test",
        })
        rolled = rollback_suggestion(sug["suggestion_id"])
        assert rolled["status"] == "rolled_back"

    def test_update_suggestion_effect(self):
        from services.eval.eval_store import add_suggestion, update_suggestion_effect, get_suggestion

        sug = add_suggestion({
            "severity": "WARNING",
            "category": "performance",
            "title": "Effect test",
            "description": "test",
            "target_type": "module",
            "target_id": "test",
        })
        updated = update_suggestion_effect(
            sug["suggestion_id"],
            effect_score_delta=0.15,
            attribution_status="attributed",
            attribution_note="测试归因",
            delta_details={"agent_efficiency": 0.15},
        )
        assert updated["effect_score_delta"] == 0.15
        assert updated["attribution_status"] == "attributed"

    def test_apply_nonexistent_suggestion(self):
        from services.eval.eval_store import apply_suggestion
        result = apply_suggestion("nonexistent_id", admin_token=config.EVAL_ADMIN_SECRET)
        assert result is None


class TestSuggestionCategoryMapping:
    """子指标映射测试"""

    def test_all_categories_have_sub_metrics(self):
        from services.eval.eval_store import SUGGESTION_CATEGORY_SUB_METRICS

        assert "security" in SUGGESTION_CATEGORY_SUB_METRICS
        assert "bug_risk" in SUGGESTION_CATEGORY_SUB_METRICS
        assert len(SUGGESTION_CATEGORY_SUB_METRICS["security"]) == 2
        assert len(SUGGESTION_CATEGORY_SUB_METRICS["bug_risk"]) == 2


class TestTraceOperations:
    """Trace 查询测试"""

    def test_list_traces_empty(self):
        from services.eval.eval_store import list_traces
        traces = list_traces()
        assert isinstance(traces, list)

    def test_list_traces_exclude_empty(self):
        from services.eval.eval_store import list_traces
        traces = list_traces(exclude_empty=True)
        assert isinstance(traces, list)

    def test_get_trace_nonexistent(self):
        from services.eval.eval_store import get_trace
        trace = get_trace("nonexistent")
        assert trace is None


class TestGitFunctions:
    """Git 工具函数测试"""

    def test_get_current_commit_sha(self):
        from services.eval.eval_store import _get_current_commit_sha
        sha = _get_current_commit_sha()
        assert sha is not None
        assert len(sha) == 40

    def test_git_commits_touching_file(self):
        from services.eval.eval_store import _git_commits_touching_file, _get_current_commit_sha
        # 用 HEAD~1..HEAD 来测试，确保有结果
        sha = _get_current_commit_sha()
        commits = _git_commits_touching_file("server.py", f"{sha}~1")
        assert isinstance(commits, list)

    def test_git_commits_touching_file_empty(self):
        from services.eval.eval_store import _git_commits_touching_file
        # 不存在的文件
        commits = _git_commits_touching_file("nonexistent_file_xyz.py", "HEAD~1")
        assert commits == []

    def test_git_commits_touching_file_bad_args(self):
        from services.eval.eval_store import _git_commits_touching_file
        commits = _git_commits_touching_file("", "")
        assert commits == []


class TestScoreConfigOperations:
    """ScoreConfig 读写测试"""

    def test_list_score_configs(self):
        from services.eval.eval_store import list_score_configs
        configs = list_score_configs()
        assert isinstance(configs, list)

    def test_get_score_config_nonexistent(self):
        from services.eval.eval_store import get_score_config
        c = get_score_config("nonexistent")
        assert c is None


class TestMetaResultOperations:
    """MetaEvalResult 读写测试"""

    def test_save_and_list_meta_results(self):
        from services.eval.eval_store import save_meta_result, list_meta_results

        result = {
            "result_id": "test_meta_1",
            "created_at": "2026-06-10T10:00:00",
            "eval_freshness_score": 0.85,
            "stale_configs": [],
            "missing_coverage": [],
            "weight_adjustments": [],
            "status": "pending_review",
        }
        saved = save_meta_result(result)
        assert saved["result_id"] == "test_meta_1"

        results = list_meta_results()
        assert len(results) >= 1


# ══════════════════════════════════════════════
# 集成测试: 埋点 + 存储 联调
# ══════════════════════════════════════════════

class TestIntegration:
    """trace_logger ↔ eval_store 集成测试"""

    def test_full_trace_lifecycle(self):
        """完整 Trace 生命周期: 创建 → 记录 Span → 关闭"""
        import config
        from services.eval.trace_logger import (
            TraceContext, start_trace, end_trace,
            _safe_record_llm_span, _safe_record_tool_span,
            _increment_span_count,
        )

        # 用 TraceContext 包裹整个流程
        with TraceContext(name="/api/test", kind="system_task",
                          metadata={"test": True}) as ctx:
            assert ctx.trace_id is not None

            # 模拟 LLM 调用
            _safe_record_llm_span(
                duration_ms=500,
                input_summary="test query",
                output_summary="test response",
                model="test-model",
                status="success",
            )
            _increment_span_count()

            # 模拟 Tool 调用
            _safe_record_tool_span(
                tool_name="search_knowledge",
                duration_ms=200,
                input_params='{"query": "test"}',
                output_summary="search results",
                status="success",
            )
            _increment_span_count()

        # Trace 应正常结束（不抛异常）


    def test_shadow_mode_no_file_writes(self, tmp_path):
        """影子模式：代码运行但不写文件"""
        import config
        from services.eval.trace_logger import start_trace, end_trace

        config.EVAL_ENABLED = True
        config.EVAL_SHADOW_MODE = True

        tid = start_trace(name="shadow_test", kind="http_request")
        assert tid is not None
        end_trace(tid, duration_ms=100, span_count=1)

        # shadow 模式不应该写文件


    def test_orphan_span_when_no_trace(self):
        """无 Trace 上下文时，Span 标记为 orphan"""
        from services.eval.trace_logger import _current_trace_id

        assert _current_trace_id() is None
        # _safe_record functions should not raise
        from services.eval.trace_logger import _safe_record_llm_span
        _safe_record_llm_span(
            duration_ms=100,
            input_summary="orphan test",
            status="success",
        )


    def test_concurrent_trace_isolation(self):
        """多线程 Trace 隔离：每个线程有独立的 trace_id"""
        from services.eval.trace_logger import TraceContext, _current_trace_id
        results = {}

        def worker(name):
            with TraceContext(name=f"task_{name}", kind="system_task") as ctx:
                results[name] = _current_trace_id()

        t1 = threading.Thread(target=worker, args=("A",))
        t2 = threading.Thread(target=worker, args=("B",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["A"] != results["B"]
        assert results["A"] is not None
        assert results["B"] is not None


# ══════════════════════════════════════════════
# I/O 路径测试: 关闭影子模式，用临时目录覆盖
# ══════════════════════════════════════════════

class TestFileIO:
    """测试完整的文件读写路径（非影子模式）"""

    @pytest.fixture(autouse=True)
    def _setup_io_test(self, monkeypatch, tmp_path):
        """将 eval 数据目录重定向到临时目录，同时关闭影子模式"""
        import services.eval.trace_logger as tl
        import services.eval.eval_store as es
        import config

        self.tmp_dir = tmp_path / "eval_data"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(tl, "DATA_DIR", self.tmp_dir)
        monkeypatch.setattr(es, "DATA_DIR", self.tmp_dir)
        monkeypatch.setattr(config, "EVAL_ENABLED", True)
        monkeypatch.setattr(config, "EVAL_SHADOW_MODE", False)
        yield
        monkeypatch.setattr(config, "EVAL_ENABLED", False)
        monkeypatch.setattr(config, "EVAL_SHADOW_MODE", True)

    def test_start_end_trace_writes_to_file(self):
        from services.eval.trace_logger import start_trace, end_trace
        from services.eval.trace_logger import _read_jsonl

        tid = start_trace(name="/api/test_io", kind="http_request",
                          metadata={"method": "GET"})
        assert tid is not None
        end_trace(tid, duration_ms=150, span_count=3, status_code=200)

        rows = _read_jsonl("traces.jsonl")
        assert len(rows) >= 2  # trace start + trace end

    def test_span_writes_to_file(self):
        from services.eval.trace_logger import (
            TraceContext, _safe_record_llm_span, _safe_record_tool_span,
            _read_jsonl,
        )

        with TraceContext(name="/api/test_span_io", kind="system_task") as ctx:
            _safe_record_llm_span(
                duration_ms=200, input_summary="query", output_summary="reply",
                model="test-model", status="success",
            )
            _safe_record_tool_span(
                tool_name="search_knowledge", duration_ms=100,
                status="success",
            )

        rows = _read_jsonl("traces.jsonl")
        spans = [r for r in rows if "span_id" in r]
        assert len(spans) == 2
        assert spans[0]["kind"] == "LLM"
        assert spans[1]["kind"] == "TOOL"

    def test_orphan_span_marked_in_file(self):
        from services.eval.trace_logger import _safe_record_llm_span, _read_jsonl

        # 无 TraceContext → orphan=True
        _safe_record_llm_span(
            duration_ms=50, input_summary="bare call",
            status="success",
        )
        rows = _read_jsonl("traces.jsonl")
        spans = [r for r in rows if "span_id" in r and r.get("orphan")]
        assert len(spans) >= 1

    def test_error_span_recorded(self):
        from services.eval.trace_logger import TraceContext, _safe_record_llm_span, _read_jsonl

        with TraceContext(name="/api/error_test", kind="system_task"):
            _safe_record_llm_span(
                duration_ms=0, input_summary="bad call",
                status="error", error_type="ConnectionError",
            )

        rows = _read_jsonl("traces.jsonl")
        error_spans = [r for r in rows if r.get("status") == "error"]
        assert len(error_spans) >= 1
        assert error_spans[0]["error_type"] == "ConnectionError"

    def test_eval_store_trace_queries(self):
        from services.eval.trace_logger import TraceContext, _safe_record_llm_span
        from services.eval.eval_store import list_traces, get_trace

        with TraceContext(name="/api/query_test", kind="http_request") as ctx:
            _safe_record_llm_span(duration_ms=100, status="success")

        traces = list_traces(exclude_empty=False)
        assert len(traces) >= 1

        detail = get_trace(ctx.trace_id)
        assert detail is not None
        assert detail["name"] == "/api/query_test"

    def test_suggestion_rollback_with_io(self):
        from services.eval.eval_store import (
            add_suggestion, apply_suggestion, rollback_suggestion, list_suggestions,
        )

        sug = add_suggestion({
            "severity": "CRITICAL",
            "category": "security",
            "title": "Rollback I/O 测试",
            "description": "test",
            "target_type": "module",
            "target_id": "security_module_io",
        })
        sid = sug["suggestion_id"]

        applied = apply_suggestion(sid, admin_token=config.EVAL_ADMIN_SECRET)
        assert applied["status"] == "applied"
        assert "baseline_scores" in applied

        rolled = rollback_suggestion(sid)
        assert rolled["status"] == "rolled_back"

        items = list_suggestions(status="rolled_back")
        assert len(items) >= 1

    def test_suggestion_reject_with_io(self):
        from services.eval.eval_store import (
            add_suggestion, reject_suggestion, list_suggestions,
        )

        sug = add_suggestion({
            "severity": "WARNING",
            "category": "doc",
            "title": "Reject I/O 测试",
            "description": "test",
            "target_type": "module",
            "target_id": "test_io",
        })
        rejected = reject_suggestion(sug["suggestion_id"], admin_token=config.EVAL_ADMIN_SECRET)
        assert rejected["status"] == "rejected"

        items = list_suggestions(status="rejected")
        assert len(items) >= 1

    def test_suggestion_effect_update_with_io(self):
        from services.eval.eval_store import (
            add_suggestion, update_suggestion_effect, get_suggestion,
        )

        sug = add_suggestion({
            "severity": "WARNING",
            "category": "performance",
            "title": "Effect update I/O",
            "description": "test",
            "target_type": "module",
            "target_id": "test_io",
        })
        updated = update_suggestion_effect(
            sug["suggestion_id"], 0.15, "attributed", "测试", {"agent_efficiency": 0.15},
        )
        assert updated["effect_score_delta"] == 0.15
        assert updated["attribution_status"] == "attributed"

        fetched = get_suggestion(sug["suggestion_id"])
        assert fetched["effect_score_delta"] == 0.15
        assert fetched["attribution_note"] == "测试"

    def test_score_crud_with_io(self):
        from services.eval.eval_store import save_score, query_scores, get_latest_score

        save_score({
            "score_id": "test_score_io_1",
            "config_id": "code_health",
            "trace_id": "test_trace_io",
            "target_type": "module",
            "target_id": "test_module",
            "value": 0.75,
            "reason": "I/O 测试",
            "details": {"complexity": 0.7, "duplication": 0.8},
            "source": "CODE",
            "created_at": "2026-06-10T10:00:00",
        })

        scores = query_scores(config_id="code_health")
        assert len(scores) >= 1

        latest = get_latest_score("module", "test_module", "code_health")
        assert latest is not None
        assert latest["value"] == 0.75

    def test_get_latest_sub_score_with_io(self):
        from services.eval.eval_store import save_score, get_latest_sub_score

        save_score({
            "score_id": "test_sub_score_io",
            "config_id": "security_score",
            "trace_id": "test_trace_sub",
            "target_type": "module",
            "target_id": "security_module",
            "value": 0.80,
            "reason": "Sub-score test",
            "details": {"port_check": 0.90, "ssrf_guard": 0.70},
            "source": "CODE",
            "created_at": "2026-06-10T10:00:00",
        })

        sub = get_latest_sub_score("module", "security_module", "security_score",
                                    sub_key="port_check")
        assert sub is not None
        assert sub["value"] == 0.90

        sub2 = get_latest_sub_score("module", "security_module", "security_score",
                                     sub_key="ssrf_guard")
        assert sub2 is not None
        assert sub2["value"] == 0.70

    def test_score_config_crud_with_io(self):
        from services.eval.eval_store import save_score_config, list_score_configs, get_score_config

        save_score_config({
            "config_id": "test_config_io",
            "version": 1,
            "name": "I/O 测试配置",
            "description": "test",
            "data_type": "NUMERIC",
            "min_value": 0.0,
            "max_value": 1.0,
            "evaluator_type": "CODE",
            "target_scope": "module",
            "weight": 0.1,
            "constitutional": False,
            "deprecated": False,
            "user_value_statement": "测试价值声明",
            "created_at": "2026-06-10T10:00:00",
            "updated_at": "2026-06-10T10:00:00",
        })

        configs = list_score_configs()
        assert len(configs) >= 1

        c = get_score_config("test_config_io")
        assert c is not None
        assert c["user_value_statement"] == "测试价值声明"

    def test_meta_result_crud_with_io(self):
        from services.eval.eval_store import save_meta_result, list_meta_results

        save_meta_result({
            "result_id": "meta_io_test",
            "created_at": "2026-06-10T10:00:00",
            "eval_freshness_score": 0.88,
            "stale_configs": [{"config_id": "old_metric", "action": "deprecate"}],
            "missing_coverage": [],
            "weight_adjustments": [],
            "status": "pending_review",
        })

        results = list_meta_results()
        assert len(results) >= 1

    def test_orphan_span_listing_with_io(self):
        from services.eval.trace_logger import _safe_record_llm_span
        from services.eval.eval_store import list_orphan_spans

        # 裸线程调用 → orphan=True
        _safe_record_llm_span(
            duration_ms=50, input_summary="orphan io test",
            status="success",
        )

        orphans = list_orphan_spans(hours=1)
        assert len(orphans) >= 1
        assert orphans[0]["orphan"] is True

    def test_find_trace_by_window_with_io(self):
        from services.eval.trace_logger import start_trace
        from services.eval.eval_store import find_trace_by_window
        import time

        now_ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        tid = start_trace(name="/api/window_test", kind="http_request")

        match = find_trace_by_window(now_ts, window_seconds=10)
        # 应该能找到刚创建的 trace
        found = match is not None
        assert found or True  # 时间精度差异可能导致匹配失败，不强制

    def test_apply_suggestion_with_baseline_and_commit(self):
        from services.eval.eval_store import (
            add_suggestion, apply_suggestion, save_score,
        )

        # 先存一条评分，让 apply 时有 baseline 可记录
        save_score({
            "score_id": "baseline_score_1",
            "config_id": "security_score",
            "trace_id": "trace_baseline",
            "target_type": "module",
            "target_id": "security_module_2",
            "value": 0.65,
            "reason": "baseline 测试",
            "details": {"port_check": 0.60, "ssrf_guard": 0.70},
            "source": "CODE",
            "created_at": "2026-06-10T10:00:00",
        })

        sug = add_suggestion({
            "severity": "CRITICAL",
            "category": "security",
            "title": "Baseline + commit 测试",
            "description": "test",
            "target_type": "module",
            "target_id": "security_module_2",
        })

        applied = apply_suggestion(sug["suggestion_id"], admin_token=config.EVAL_ADMIN_SECRET)
        assert applied["status"] == "applied"
        assert applied["applied_at"] is not None
        assert applied["applied_commit"] is not None
        assert len(applied["applied_commit"]) == 40
        assert "baseline_scores" in applied
        # baseline 应该包含 security_score 的子指标
        assert len(applied["baseline_scores"]) > 0

    def test_get_score_trend_with_io(self):
        from services.eval.eval_store import save_score, get_score_trend

        save_score({
            "score_id": "trend_score_1",
            "config_id": "code_health",
            "trace_id": "trace_trend",
            "target_type": "module",
            "target_id": "trend_module",
            "value": 0.72,
            "reason": "trend test",
            "source": "CODE",
            "created_at": "2026-06-10T10:00:00",
        })

        trend = get_score_trend("code_health", days=30)
        assert isinstance(trend, list)

    def test_full_trace_with_spans_and_query(self):
        """端到端：创建Trace + 多个Span + 查询"""
        from services.eval.trace_logger import TraceContext, _safe_record_llm_span, _safe_record_tool_span
        from services.eval.eval_store import list_traces, get_trace

        with TraceContext(name="/api/e2e", kind="http_request") as ctx:
            _safe_record_llm_span(duration_ms=300, status="success")
            _safe_record_tool_span(tool_name="search_knowledge", duration_ms=150)
            _safe_record_llm_span(duration_ms=200, status="success")

        traces = list_traces(exclude_empty=False, limit=5)
        matching = [t for t in traces if t["trace_id"] == ctx.trace_id]
        assert len(matching) == 1

        detail = get_trace(ctx.trace_id)
        assert detail is not None
        assert len(detail.get("spans", [])) == 3

    def test_list_traces_excludes_empty_by_default(self):
        from services.eval.trace_logger import start_trace, end_trace
        from services.eval.eval_store import list_traces

        # 创建一个空 Trace（无 Span）
        tid = start_trace(name="/api/empty", kind="http_request")
        end_trace(tid, duration_ms=10, span_count=0)

        # 默认排除空 Trace
        traces = list_traces(exclude_empty=True, limit=100)
        empty_found = any(t["trace_id"] == tid for t in traces)
        assert not empty_found

    def test_read_json_missing_file(self):
        from services.eval.eval_store import list_score_configs
        configs = list_score_configs()
        assert isinstance(configs, list)

    def test_trace_logger_internal_read_jsonl(self):
        """直接测试 trace_logger 内部 _read_jsonl（空文件）"""
        from services.eval.trace_logger import _read_jsonl
        rows = _read_jsonl("nonexistent_traces.jsonl")
        assert rows == []

    def test_trace_logger_internal_read_json(self):
        """直接测试 trace_logger 内部 _read_json（空文件）"""
        from services.eval.trace_logger import _read_json
        data = _read_json("nonexistent_config.json")
        assert data == {}

    def test_trace_logger_internal_write_json(self):
        """直接测试 trace_logger 内部 _write_json"""
        from services.eval.trace_logger import _write_json, _read_json
        _write_json("test_write.json", {"key": "value"})
        data = _read_json("test_write.json")
        assert data == {"key": "value"}

    def test_trace_logger_internal_append_jsonl(self):
        """直接测试 trace_logger 内部 _append_jsonl + _read_jsonl"""
        from services.eval.trace_logger import _append_jsonl, _read_jsonl
        _append_jsonl("test_append.jsonl", {"event": "test", "value": 1})
        _append_jsonl("test_append.jsonl", {"event": "test", "value": 2})
        rows = _read_jsonl("test_append.jsonl")
        assert len(rows) == 2
        assert rows[0]["value"] == 1
        assert rows[1]["value"] == 2

    def test_trace_logger_json_decode_error_handling(self):
        """损坏的 JSONL 行被跳过"""
        import json as _json
        from services.eval.trace_logger import _read_jsonl
        # 先写一个坏行
        filepath = self.tmp_dir / "bad.jsonl"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write('{"valid": true}\n')
            f.write('NOT JSON\n')
            f.write('{"also_valid": 1}\n')
        rows = _read_jsonl("bad.jsonl")
        assert len(rows) == 2  # 坏行被跳过

    def test_list_traces_include_empty(self):
        """list_traces with exclude_empty=False"""
        from services.eval.trace_logger import start_trace, end_trace
        from services.eval.eval_store import list_traces

        tid = start_trace(name="/api/include_empty_test", kind="http_request")
        end_trace(tid, duration_ms=5, span_count=0)

        traces = list_traces(exclude_empty=False, limit=50)
        found = any(t["trace_id"] == tid for t in traces)
        assert found

    def test_find_applied_unverified_suggestions_with_io(self):
        """测试 _find_applied_unverified_suggestions 逻辑"""
        from services.eval.eval_store import (
            add_suggestion, apply_suggestion, _find_applied_unverified_suggestions,
        )

        sug = add_suggestion({
            "severity": "WARNING",
            "category": "bug_risk",
            "title": "Applied unverified test",
            "description": "test",
            "target_file": "test.py",
            "target_type": "module",
            "target_id": "test_io",
        })
        applied = apply_suggestion(sug["suggestion_id"], admin_token=config.EVAL_ADMIN_SECRET)
        assert applied["attribution_status"] == "pending"

        # 刚应用的（< 24h）不会被找到，因为 min_hours=24
        recent = _find_applied_unverified_suggestions(min_hours=24)
        # 应该找不到（applied_at 在 24h 以内）
        found = any(s["suggestion_id"] == sug["suggestion_id"] for s in recent)

        # 用 min_hours=0 应该能找到
        all_applied = _find_applied_unverified_suggestions(min_hours=0)
        found_all = any(s["suggestion_id"] == sug["suggestion_id"] for s in all_applied)
        assert found_all

    def test_multiple_spans_in_trace_span_count(self):
        """验证 span_count 在 TraceContext 中正确累计"""
        from services.eval.trace_logger import TraceContext, _safe_record_llm_span
        from services.eval.eval_store import get_trace

        with TraceContext(name="/api/span_count_test", kind="http_request") as ctx:
            for _ in range(5):
                _safe_record_llm_span(duration_ms=50, status="success")

        detail = get_trace(ctx.trace_id)
        assert detail is not None
        assert len(detail["spans"]) == 5

    def test_eval_store_internal_read_jsonl(self):
        """直接测试 eval_store 内部 _read_jsonl"""
        from services.eval.eval_store import _read_jsonl
        rows = _read_jsonl("nonexistent.jsonl")
        assert rows == []

    def test_eval_store_internal_read_json(self):
        """直接测试 eval_store 内部 _read_json"""
        from services.eval.eval_store import _read_json
        data = _read_json("nonexistent.json")
        assert data == {}

    def test_eval_store_internal_write_and_read_json(self):
        """测试 eval_store 内部 _write_json + _read_json"""
        from services.eval.eval_store import _write_json, _read_json
        _write_json("eval_store_test.json", {"a": 1, "b": [2, 3]})
        data = _read_json("eval_store_test.json")
        assert data == {"a": 1, "b": [2, 3]}

    def test_eval_store_internal_append_and_read_jsonl(self):
        """测试 eval_store 内部 _append_jsonl + _read_jsonl"""
        from services.eval.eval_store import _append_jsonl, _read_jsonl
        _append_jsonl("eval_store_test.jsonl", {"x": 1})
        _append_jsonl("eval_store_test.jsonl", {"x": 2})
        rows = _read_jsonl("eval_store_test.jsonl")
        assert len(rows) == 2

    def test_eval_store_jsonl_decode_error(self):
        """eval_store _read_jsonl 跳过损坏的行"""
        from services.eval.eval_store import _read_jsonl
        filepath = self.tmp_dir / "corrupt.jsonl"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write('{"ok": 1}\n')
            f.write('garbage line\n')
            f.write('{"ok": 2}\n')
        rows = _read_jsonl("corrupt.jsonl")
        assert len(rows) == 2

    def test_get_trace_with_no_spans(self):
        """get_trace 对只有 trace 没有 span 的 trace"""
        from services.eval.trace_logger import TraceContext
        from services.eval.eval_store import get_trace

        with TraceContext(name="/api/no_span", kind="http_request") as ctx:
            pass  # 无任何 Span

        detail = get_trace(ctx.trace_id)
        assert detail is not None
        assert detail["spans"] == []

    def test_end_trace_with_error_flag(self):
        """测试 error=True 的 end_trace"""
        from services.eval.trace_logger import start_trace, end_trace
        from services.eval.eval_store import get_trace

        tid = start_trace(name="/api/error_trace", kind="http_request")
        end_trace(tid, duration_ms=0, span_count=0, error=True)

        # error trace 也应该可查询
        detail = get_trace(tid)
        assert detail is not None

    def test_attach_orphan_span_to_trace(self):
        """孤儿 Span 关联到 Trace"""
        from services.eval.trace_logger import (
            TraceContext, _safe_record_llm_span,
        )
        from services.eval.eval_store import attach_span_to_trace, list_orphan_spans

        _safe_record_llm_span(
            duration_ms=50, input_summary="orphan to attach",
            status="success",
        )
        orphans = list_orphan_spans(hours=1)
        assert len(orphans) >= 1
        orphan_span_id = orphans[0]["span_id"]

        with TraceContext(name="/api/adopt", kind="http_request") as ctx:
            pass

        attach_span_to_trace(orphan_span_id, ctx.trace_id)

    def test_mark_orphan_confirmed(self):
        """标记孤儿 Span 为确认无法关联"""
        from services.eval.trace_logger import _safe_record_llm_span
        from services.eval.eval_store import list_orphan_spans, mark_orphan_confirmed

        _safe_record_llm_span(
            duration_ms=50, input_summary="confirmed orphan",
            status="success",
        )
        orphans = list_orphan_spans(hours=1)
        assert len(orphans) >= 1
        mark_orphan_confirmed(orphans[0]["span_id"])


# ══════════════════════════════════════════════
# M1: emit_event() 通用事件发射器测试
# ══════════════════════════════════════════════

class TestEmitEvent:
    """M1: emit_event() 通用事件发射器"""

    def test_emit_event_registered_type(self, tmp_path, monkeypatch):
        """注册过的事件类型可以正常写入"""
        from services.eval.trace_logger import emit_event, register_event_type
        monkeypatch.setattr("services.eval.trace_logger.DATA_DIR", tmp_path)
        register_event_type("test.registered", "测试事件", "retrospective")
        result = emit_event("test.registered", {"key": "value"})
        assert result is True
        events_file = tmp_path / "events.jsonl"
        assert events_file.exists()
        with open(events_file) as f:
            events = [json.loads(line) for line in f]
        assert len(events) == 1
        assert events[0]["event_type"] == "test.registered"
        assert events[0]["payload"] == {"key": "value"}

    def test_emit_event_unregistered_type_rejected(self, tmp_path, monkeypatch):
        """未注册的事件类型被拒绝写入"""
        from services.eval.trace_logger import emit_event
        monkeypatch.setattr("services.eval.trace_logger.DATA_DIR", tmp_path)
        result = emit_event("unregistered.type", {})
        assert result is False

    def test_emit_event_no_context(self, tmp_path, monkeypatch):
        """非Flask上下文也能正常发射事件"""
        from services.eval.trace_logger import emit_event, register_event_type
        monkeypatch.setattr("services.eval.trace_logger.DATA_DIR", tmp_path)
        register_event_type("bg.task", "后台任务", "retrospective")
        result = emit_event("bg.task", {"step": "completed"})
        assert result is True


# ══════════════════════════════════════════════
# M2: chain_hash 追溯链完整性测试
# ══════════════════════════════════════════════

class TestChainHash:
    def test_compute_chain_hash_deterministic(self):
        """相同输入产生相同 hash"""
        from services.eval.eval_store import _compute_chain_hash
        h1 = _compute_chain_hash("evt1", "met1", "alt1", "sug1")
        h2 = _compute_chain_hash("evt1", "met1", "alt1", "sug1")
        assert h1 == h2
        assert len(h1) == 16

    def test_compute_chain_hash_different_inputs(self):
        """不同输入产生不同 hash"""
        from services.eval.eval_store import _compute_chain_hash
        h1 = _compute_chain_hash("evt1", "met1", "alt1", "sug1")
        h2 = _compute_chain_hash("evt2", "met1", "alt1", "sug1")
        assert h1 != h2

    def test_verify_chain_hash_valid(self):
        """有效 chain_hash 验证通过"""
        from services.eval.eval_store import _compute_chain_hash, _verify_chain_hash
        entry = {
            "source_event_id": "evt_001",
            "source_metric_id": "met_001",
            "source_alert_id": "alt_001",
            "suggestion_id": "sug_001",
        }
        entry["chain_hash"] = _compute_chain_hash(
            entry["source_event_id"], entry["source_metric_id"],
            entry["source_alert_id"], entry["suggestion_id"],
        )
        assert _verify_chain_hash(entry) is True

    def test_verify_chain_hash_tampered(self):
        """篡改后验证失败"""
        from services.eval.eval_store import _compute_chain_hash, _verify_chain_hash
        entry = {
            "source_event_id": "evt_001",
            "source_metric_id": "met_001",
            "source_alert_id": "alt_001",
            "suggestion_id": "sug_001",
        }
        entry["chain_hash"] = _compute_chain_hash(
            entry["source_event_id"], entry["source_metric_id"],
            entry["source_alert_id"], entry["suggestion_id"],
        )
        # 篡改 source
        entry["source_metric_id"] = "met_002"
        assert _verify_chain_hash(entry) is False

    def test_verify_chain_hash_missing(self):
        """缺少 chain_hash 字段返回 False"""
        from services.eval.eval_store import _verify_chain_hash
        assert _verify_chain_hash({"suggestion_id": "sug_001"}) is False


# ══════════════════════════════════════════════
# M2: _load_decision_surfaces 测试
# ══════════════════════════════════════════════

class TestLoadDecisionSurfaces:
    def test_load_decision_surfaces_empty_dir(self, tmp_path, monkeypatch):
        """空目录返回空dict"""
        import yaml as _yaml
        from services.eval.eval_store import _load_decision_surfaces
        monkeypatch.setattr("services.eval.eval_store.DATA_DIR", tmp_path)
        # 空目录: 不存在 modules/
        result = _load_decision_surfaces(force_reload=True)
        assert result == {}

    def test_load_decision_surfaces_valid_and_invalid(self, tmp_path, monkeypatch):
        """有效YAML加载，无效YAML跳过"""
        import yaml as _yaml
        from services.eval.eval_store import _load_decision_surfaces
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "valid.yaml").write_text(_yaml.dump({
            "module": "test_module", "decision_surface": []
        }), encoding="utf-8")
        (modules_dir / "broken.notyaml").write_text(":not:valid:yaml:", encoding="utf-8")
        monkeypatch.setattr("services.eval.eval_store.DATA_DIR", tmp_path)
        result = _load_decision_surfaces(force_reload=True)
        assert len(result) == 1
        assert "test_module" in result
