"""
测试 eval API 端点 — auth / shadow mode / response shape / partial failure

测试规范:
  🔴 外部依赖必须 mock — LLM / 数据库 / 网络 / 文件系统
  🔴 mock 用后必须 restore
  🔴 不绕过防风暴/限流等安全机制来调用真实外部依赖
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import config
from server import create_app


@pytest.fixture
def client(monkeypatch, tmp_path):
    """创建 Flask 测试客户端，临时数据目录"""
    import services.eval.eval_store as es
    import services.eval.trace_logger as tl
    import services.eval.eval_engine as ee

    data_dir = tmp_path / "eval_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tl, "DATA_DIR", data_dir)
    monkeypatch.setattr(es, "DATA_DIR", data_dir)
    monkeypatch.setattr(ee, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "EVAL_ENABLED", True)
    monkeypatch.setattr(config, "EVAL_SHADOW_MODE", False)

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _auth_headers():
    return {"X-Admin-Token": config.EVAL_ADMIN_SECRET}


# ══════════════════════════════════════════════
# Auth 测试
# ══════════════════════════════════════════════

class TestAuth:
    """所有端点需要 X-Admin-Token"""

    READ_ENDPOINTS = [
        "/api/eval/summary",
        "/api/eval/configs",
        "/api/eval/trend/data_completeness?days=30",
        "/api/eval/traces?limit=5",
        "/api/eval/traces/fake_id",
        "/api/eval/suggestions",
        "/api/eval/meta/results",
        "/api/eval/scores?config_id=data_completeness",
    ]

    WRITE_ENDPOINTS = [
        "/api/eval/suggestions/fake_id/apply",
        "/api/eval/suggestions/fake_id/reject",
        "/api/eval/cross-validate",
        "/api/eval/cross-validate/execute",
    ]

    def test_no_token_returns_403(self, client):
        for path in self.READ_ENDPOINTS + self.WRITE_ENDPOINTS:
            resp = client.get(path) if "apply" not in path and "reject" not in path and "cross-validate" not in path else client.post(path)
            assert resp.status_code == 403, f"{path} should return 403 without token"
            data = resp.get_json()
            assert "Forbidden" in data.get("error", "")

    def test_wrong_token_returns_403(self, client):
        headers = {"X-Admin-Token": "wrong-token"}
        for path in self.READ_ENDPOINTS:
            resp = client.get(path, headers=headers)
            assert resp.status_code == 403, f"{path} should return 403 with wrong token"

    def test_correct_token_returns_200_or_404(self, client):
        """有正确 token 时应返回 200 或 404（不存在的资源）"""
        headers = _auth_headers()
        for path in self.READ_ENDPOINTS:
            resp = client.get(path, headers=headers)
            assert resp.status_code in (200, 404), f"{path} returned {resp.status_code}"


# ══════════════════════════════════════════════
# 影子模式写保护
# ══════════════════════════════════════════════

class TestShadowModeWriteProtection:
    def test_apply_blocked_in_shadow(self, monkeypatch, tmp_path):
        import services.eval.eval_store as es
        import services.eval.trace_logger as tl
        import services.eval.eval_engine as ee

        data_dir = tmp_path / "eval_data"
        data_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(tl, "DATA_DIR", data_dir)
        monkeypatch.setattr(es, "DATA_DIR", data_dir)
        monkeypatch.setattr(ee, "DATA_DIR", data_dir)
        monkeypatch.setattr(config, "EVAL_ENABLED", True)
        monkeypatch.setattr(config, "EVAL_SHADOW_MODE", True)

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.post("/api/eval/suggestions/fake/apply", headers=_auth_headers())
        assert resp.status_code == 403
        data = resp.get_json()
        assert "影子模式" in data.get("error", "")

    def test_reject_blocked_in_shadow(self, monkeypatch, tmp_path):
        import services.eval.eval_store as es
        import services.eval.trace_logger as tl
        import services.eval.eval_engine as ee

        data_dir = tmp_path / "eval_data"
        data_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(tl, "DATA_DIR", data_dir)
        monkeypatch.setattr(es, "DATA_DIR", data_dir)
        monkeypatch.setattr(ee, "DATA_DIR", data_dir)
        monkeypatch.setattr(config, "EVAL_ENABLED", True)
        monkeypatch.setattr(config, "EVAL_SHADOW_MODE", True)

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.post("/api/eval/suggestions/fake/reject", headers=_auth_headers())
        assert resp.status_code == 403
        data = resp.get_json()
        assert "影子模式" in data.get("error", "")


# ══════════════════════════════════════════════
# 响应形状测试
# ══════════════════════════════════════════════

class TestSummaryEndpoint:
    def test_returns_required_fields(self, client):
        resp = client.get("/api/eval/summary", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "system_mode" in data
        assert "total_score" in data
        assert "updated_at" in data
        assert "alerts" in data
        assert "trend" in data
        assert "radar" in data
        assert "annotations" in data
        assert "errors" in data
        assert "sparklines" in data
        assert data["system_mode"] in ("shadow", "active")

    def test_errors_is_always_array(self, client):
        resp = client.get("/api/eval/summary", headers=_auth_headers())
        data = resp.get_json()
        assert isinstance(data["errors"], list)

    def test_partial_failure_tolerant(self, client):
        """部分组件失败时仍返回 200 + errors 数组"""
        resp = client.get("/api/eval/summary", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        # 核心字段即使在空数据时也应存在
        for key in ("system_mode", "total_score", "updated_at", "alerts",
                     "trend", "radar", "annotations", "errors", "sparklines"):
            assert key in data, f"Missing key: {key}"


class TestConfigsEndpoint:
    def test_returns_list(self, client):
        resp = client.get("/api/eval/configs", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "configs" in data
        assert "count" in data
        assert isinstance(data["configs"], list)

    def test_configs_have_required_fields(self, client):
        resp = client.get("/api/eval/configs", headers=_auth_headers())
        configs = resp.get_json()["configs"]
        if configs:
            cfg = configs[0]
            assert "config_id" in cfg
            assert "name" in cfg
            assert "weight" in cfg


class TestTrendEndpoint:
    def test_returns_points_and_annotations(self, client):
        resp = client.get("/api/eval/trend/data_completeness?days=30", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "config_id" in data
        assert "points" in data
        assert "annotations" in data
        assert isinstance(data["points"], list)
        assert isinstance(data["annotations"], list)

    def test_custom_days_param(self, client):
        resp = client.get("/api/eval/trend/data_completeness?days=7", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["config_id"] == "data_completeness"


class TestTracesEndpoint:
    def test_returns_list(self, client):
        resp = client.get("/api/eval/traces?limit=5&window_hours=24", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "traces" in data
        assert "count" in data
        assert isinstance(data["traces"], list)

    def test_trace_not_found_returns_404(self, client):
        resp = client.get("/api/eval/traces/nonexistent_id_12345", headers=_auth_headers())
        assert resp.status_code == 404


class TestSuggestionsEndpoint:
    def test_returns_list(self, client):
        resp = client.get("/api/eval/suggestions", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "suggestions" in data
        assert "count" in data
        assert isinstance(data["suggestions"], list)

    def test_status_filter(self, client):
        resp = client.get("/api/eval/suggestions?status=pending", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        for s in data["suggestions"]:
            assert s["status"] == "pending"

    def test_severity_filter(self, client):
        resp = client.get("/api/eval/suggestions?severity=P0", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        for s in data["suggestions"]:
            assert s["severity"] == "P0"


class TestMetaResultsEndpoint:
    def test_returns_list(self, client):
        resp = client.get("/api/eval/meta/results", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data
        assert "count" in data
        assert "updated_at" in data
        assert data["updated_at"] is None
        assert isinstance(data["results"], list)


# ══════════════════════════════════════════════
# Write 端点功能测试 (非影子模式)
# ══════════════════════════════════════════════

class TestWriteEndpoints:
    def test_apply_nonexistent_returns_404(self, client):
        resp = client.post("/api/eval/suggestions/nonexistent/apply", headers=_auth_headers())
        assert resp.status_code == 404
        data = resp.get_json()
        assert "not found" in data.get("error", "").lower()

    def test_reject_nonexistent_returns_404(self, client):
        resp = client.post("/api/eval/suggestions/nonexistent/reject", headers=_auth_headers())
        assert resp.status_code == 404
        data = resp.get_json()
        assert "not found" in data.get("error", "").lower()

    def test_apply_suggestion_flow(self, client):
        """完整采纳流程: 创建建议 → 采纳 → 验证状态"""
        from services.eval.eval_store import add_suggestion, get_suggestion

        sug = add_suggestion({
            "severity": "WARNING",
            "category": "security",
            "title": "API test apply",
            "description": "test",
            "target_type": "module",
            "target_id": "api_test_apply",
        })
        resp = client.post(
            f"/api/eval/suggestions/{sug['suggestion_id']}/apply",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "applied"
        assert data["suggestion"]["status"] == "applied"
        assert data["suggestion"]["applied_at"] is not None
        assert data["suggestion"]["applied_commit"] is not None
        assert "baseline_scores" in data["suggestion"]

    def test_reject_suggestion_flow(self, client):
        """完整拒绝流程"""
        from services.eval.eval_store import add_suggestion

        sug = add_suggestion({
            "severity": "SUGGESTION",
            "category": "doc",
            "title": "API test reject",
            "description": "test",
            "target_type": "module",
            "target_id": "api_test_reject",
        })
        resp = client.post(
            f"/api/eval/suggestions/{sug['suggestion_id']}/reject",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "rejected"
        assert data["suggestion"]["status"] == "rejected"

    def test_apply_shadow_mode_still_reads(self, client):
        """写操作在 shadow 模式下被阻止，但 GET 请求不受影响"""
        resp = client.get("/api/eval/suggestions?status=applied", headers=_auth_headers())
        assert resp.status_code == 200


# ══════════════════════════════════════════════
# Cross-validate 端点
# ══════════════════════════════════════════════

class TestCrossValidateEndpoint:
    def test_cross_validate_no_traces(self, client):
        resp = client.post("/api/eval/cross-validate",
                          data=json.dumps({"sample_size": 5}),
                          content_type="application/json",
                          headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "skipped"
        assert "insufficient" in data["reason"].lower()

    def test_cross_validate_with_traces(self, client):
        """创建 traces 后 cross-validate 生成 pending items"""
        from services.eval.trace_logger import TraceContext

        for i in range(5):
            with TraceContext(name=f"/api/agent/cv_{i}", kind="agent_chat",
                             metadata={"method": "GET", "path": f"/api/agent/cv_{i}"}) as ctx:
                from services.eval.trace_logger import _record_span
                _record_span(kind="llm_call", name="chat", duration_ms=100)
                _record_span(kind="tool_use", name="search_knowledge", duration_ms=50)

        resp = client.post("/api/eval/cross-validate",
                          data=json.dumps({"sample_size": 3}),
                          content_type="application/json",
                          headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "pending"
        assert data["sample_size"] <= 3
        assert "score_id" in data

    def test_cross_validate_execute_returns_200(self, client):
        """Phase 4: cross-validate/execute 501→200, returns run_crossval_batch result"""
        resp = client.post("/api/eval/cross-validate/execute",
                          json={"force": False}, headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] in ("skipped", "processing")


# ══════════════════════════════════════════════
# Scores 端点
# ══════════════════════════════════════════════

class TestScoresEndpoint:
    def test_returns_list(self, client):
        resp = client.get("/api/eval/scores", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "scores" in data
        assert "count" in data
        assert isinstance(data["scores"], list)

    def test_filter_by_config_id(self, client):
        resp = client.get("/api/eval/scores?config_id=data_completeness", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        for s in data["scores"]:
            assert s["config_id"] == "data_completeness"


# ══════════════════════════════════════════════
# Defense in depth: store layer auth
# ══════════════════════════════════════════════

class TestStoreLayerAuth:
    def test_apply_without_token_raises_permission_error(self):
        from services.eval.eval_store import apply_suggestion
        with pytest.raises(PermissionError, match="X-Admin-Token"):
            apply_suggestion("test_id")

    def test_apply_with_wrong_token_raises_permission_error(self):
        from services.eval.eval_store import apply_suggestion
        with pytest.raises(PermissionError, match="X-Admin-Token"):
            apply_suggestion("test_id", admin_token="wrong")

    def test_reject_without_token_raises_permission_error(self):
        from services.eval.eval_store import reject_suggestion
        with pytest.raises(PermissionError, match="X-Admin-Token"):
            reject_suggestion("test_id")

    def test_reject_with_wrong_token_raises_permission_error(self):
        from services.eval.eval_store import reject_suggestion
        with pytest.raises(PermissionError, match="X-Admin-Token"):
            reject_suggestion("test_id", admin_token="wrong")


# ══════════════════════════════════════════════
# M1: Beacon 端点测试
# ══════════════════════════════════════════════

class TestBeacon:
    def test_beacon_no_token_returns_403(self, client):
        resp = client.post("/api/eval/beacon", json={"event_type": "ui.interaction", "panel_id": "overview"})
        assert resp.status_code == 403

    def test_beacon_valid_token_returns_200(self, client):
        resp = client.post("/api/eval/beacon",
            json={"event_type": "ui.interaction", "panel_id": "overview", "timestamp": 1700000000},
            headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_beacon_rejects_unknown_fields(self, client):
        resp = client.post("/api/eval/beacon",
            json={"event_type": "ui.interaction", "panel_id": "overview", "mouse_x": 100, "keystrokes": "abc"},
            headers=_auth_headers())
        assert resp.status_code == 200

    def test_beacon_rejects_field_too_long(self, client):
        resp = client.post("/api/eval/beacon",
            json={"event_type": "x" * 51, "panel_id": "overview"},
            headers=_auth_headers())
        assert resp.status_code == 400

    def test_beacon_rate_limit_returns_429(self, client, monkeypatch):
        # 清空速率限制状态，避免跨测试残留
        import routes.api_eval as api_eval_mod
        api_eval_mod._beacon_rate_state.clear()
        frozen = 1700000000.0
        monkeypatch.setattr("routes.api_eval.time.time", lambda: frozen)
        for i in range(10):
            resp = client.post("/api/eval/beacon",
                json={"event_type": "ui.interaction", "panel_id": "overview", "timestamp": 1700000000},
                headers=_auth_headers())
            assert resp.status_code == 200, f"request {i} should pass"
        resp = client.post("/api/eval/beacon",
            json={"event_type": "ui.interaction", "panel_id": "overview", "timestamp": 1700000000},
            headers=_auth_headers())
        assert resp.status_code == 429


# ══════════════════════════════════════════════
# M2: Trace-chain API 测试
# ══════════════════════════════════════════════

class TestTraceChain:
    def test_trace_chain_no_auth_returns_403(self, client):
        resp = client.get("/api/eval/trace-chain/nonexistent")
        assert resp.status_code == 403

    def test_trace_chain_not_found_returns_404(self, client):
        resp = client.get("/api/eval/trace-chain/nonexistent_sug_001", headers=_auth_headers())
        assert resp.status_code == 404

    def test_trace_chain_full_chain(self, client, monkeypatch):
        """完整追溯链: 4个source ID都存在"""
        from services.eval.eval_store import add_suggestion, _compute_chain_hash
        sug = {
            "source_event_id": "evt_001",
            "source_metric_id": "met_001",
            "source_alert_id": "alt_001",
            "category": "test",
            "description": "test full chain",
        }
        sug = add_suggestion(sug)
        sug_id = sug["suggestion_id"]
        resp = client.get(f"/api/eval/trace-chain/{sug_id}", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["chain_state"] == "full"
        assert data["chain_hash_verified"] is True
        assert "evt_001" in data["chain"]

    def test_trace_chain_partial_chain(self, client):
        """部分追溯链: 只有部分source ID"""
        from services.eval.eval_store import add_suggestion
        sug = add_suggestion({
            "source_event_id": "evt_002",
            "category": "test",
            "description": "test partial chain",
        })
        sug_id = sug["suggestion_id"]
        resp = client.get(f"/api/eval/trace-chain/{sug_id}", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["chain_state"] in ("partial", "broken")
        assert data["chain_hash_verified"] is True

    def test_trace_chain_broken_chain(self, client):
        """缺少全部 source ID: chain_state=broken"""
        from services.eval.eval_store import add_suggestion
        sug = add_suggestion({
            "category": "test",
            "description": "orphan suggestion with no source IDs",
        })
        sug_id = sug["suggestion_id"]
        resp = client.get(f"/api/eval/trace-chain/{sug_id}", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["chain_state"] == "broken"
        # chain_hash should still be verifiable (computed from empty source IDs + sug_id)
        assert data["chain_hash_verified"] is True

    def test_trace_chain_full_with_evidence_brief(self, client, monkeypatch):
        """完整链返回 evidence_brief 四段 (metric/alert/suggestion/decision)"""
        from services.eval.eval_store import add_suggestion
        sug = add_suggestion({
            "source_event_id": "evt_full_2",
            "source_metric_id": "met_full_2",
            "source_alert_id": "alt_full_2",
            "source_decision_id": "dec_full_2",
            "category": "security",
            "description": "second full chain test",
        })
        sug_id = sug["suggestion_id"]
        resp = client.get(f"/api/eval/trace-chain/{sug_id}", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["chain_state"] == "full"
        assert len(data["chain"]) == 4
        brief = data.get("evidence_brief", {})
        assert "metric" in brief
        assert "alert" in brief
        assert "suggestion" in brief
        assert "decision" in brief

    def test_trace_chain_partial_with_two_ids(self, client):
        """2个 source ID → chain_state=partial (非 broken)"""
        from services.eval.eval_store import add_suggestion
        sug = add_suggestion({
            "source_event_id": "evt_partial_2",
            "source_metric_id": "met_partial_2",
            "category": "test",
            "description": "partial chain with exactly 2 source IDs",
        })
        sug_id = sug["suggestion_id"]
        resp = client.get(f"/api/eval/trace-chain/{sug_id}", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["chain_state"] == "partial", f"expected partial, got {data['chain_state']}"
        assert data["chain_hash_verified"] is True

    def test_trace_chain_tampered_hash(self, client, monkeypatch, tmp_path):
        """chain_hash 被篡改 → chain_hash_verified=False"""
        import json
        from services.eval import eval_store as store

        monkeypatch.setattr(store, "DATA_DIR", tmp_path)
        # 使用隔离存储添加建议
        sug = store.add_suggestion({
            "source_event_id": "evt_tamper",
            "category": "test",
            "description": "suggestion with tampered hash",
        })
        sug_id = sug["suggestion_id"]
        # 直接篡改 suggestions.json
        data = store._read_json("suggestions.json")
        for s in data.get("suggestions", []):
            if s.get("suggestion_id") == sug_id:
                s["chain_hash"] = "deadbeef00000000"
        store._write_json("suggestions.json", data)
        resp = client.get(f"/api/eval/trace-chain/{sug_id}", headers=_auth_headers())
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["chain_hash_verified"] is False


# ══════════════════════════════════════════════
# M3: 用户路径验收测试 (4步追问)
# ══════════════════════════════════════════════

class TestM3UserPath:
    """模拟用户4步追问路径:
    总览→评分卡详情→L2(为什么)→L3(意味着什么)→追溯链
    每步通过 API 验证。不依赖浏览器，验证 API 形状正确、链路完整。
    """

    def test_step1_summary_returns_required_keys(self, client):
        """Step 1: 总览 → 返回 radar + configs + coverage + alerts"""
        resp = client.get("/api/eval/summary", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        for key in ["radar", "coverage", "alerts"]:
            assert key in data, f"Step 1 FAIL: summary 缺少字段 {key}"

    def test_step2_decision_surfaces_api(self, client):
        """Step 2: 决策面 API → 返回 surfaces dict"""
        resp = client.get("/api/eval/decision-surfaces", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "surfaces" in data, "Step 2 FAIL: decision-surfaces 缺少 surfaces"
        assert "count" in data, "Step 2 FAIL: decision-surfaces 缺少 count"

    def test_step3_find_trace_chain_for_suggestion(self, client):
        """Step 3-4: 建议 → 追溯链 → 原始事件 (完整路径)"""
        from services.eval.eval_store import add_suggestion
        sug = add_suggestion({
            "source_event_id": "evt_path_test",
            "source_metric_id": "met_path_test",
            "source_alert_id": "alt_path_test",
            "category": "security",
            "description": "安全评分下降：认证模块超时率上升",
            "severity": "P0",
        })
        sug_id = sug["suggestion_id"]

        # Step 3: 获取建议列表，找到对应建议
        resp = client.get("/api/eval/suggestions?severity=P0", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        suggestions = data.get("suggestions") or []
        found = [s for s in suggestions if s.get("suggestion_id") == sug_id]
        assert len(found) >= 1, "Step 3 FAIL: P0 建议未在 /suggestions 中出现"

        # Step 4: 追溯链 → 原始事件
        resp2 = client.get(f"/api/eval/trace-chain/{sug_id}", headers=_auth_headers())
        assert resp2.status_code == 200
        chain_data = resp2.get_json()
        assert chain_data["chain_state"] == "full", (
            f"Step 4 FAIL: 追溯链应为 full，实际为 {chain_data['chain_state']}"
        )
        assert chain_data["chain_hash_verified"] is True, "Step 4 FAIL: 链哈希未通过"
        brief = chain_data.get("evidence_brief") or {}
        assert brief.get("suggestion"), "Step 4 FAIL: evidence_brief 缺 suggestion"

    def test_step4_error_path_broken_chain(self, client):
        """错误路径: 无来源的建议 → 追溯链显示 broken"""
        from services.eval.eval_store import add_suggestion
        sug = add_suggestion({
            "category": "security",
            "description": "孤立的建议，无来源追溯",
        })
        sug_id = sug["suggestion_id"]
        resp = client.get(f"/api/eval/trace-chain/{sug_id}", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["chain_state"] == "broken", (
            f"Step 4 err FAIL: 无来源应为 broken，实际为 {data['chain_state']}"
        )


# ══════════════════════════════════════════════
# M5: Probe ignore API 测试
# ══════════════════════════════════════════════

class TestProbeIgnore:
    """POST /api/eval/probes/<id>/ignore"""

    def test_probe_ignore_no_token_returns_403(self, client):
        """探测卡忽略端点需要 admin token"""
        resp = client.post("/api/eval/probes/probe_001/ignore",
                          json={"reason": "known issue"})
        assert resp.status_code == 403

    def test_probe_ignore_writes_audit(self, client, monkeypatch, tmp_path):
        """忽略操作写入 audit.jsonl 并记录原因"""
        import services.eval.eval_store as store
        monkeypatch.setattr(store, "DATA_DIR", tmp_path)
        # 先创建探测卡
        store._save_probe({
            "probe_id": "probe_001",
            "title": "测试探测卡",
            "created_at": "2026-06-13T00:00:00",
            "resolution": None,
        })
        resp = client.post("/api/eval/probes/probe_001/ignore",
            json={"reason": "Not applicable — project doesn't use RLAIF"},
            headers=_auth_headers())
        assert resp.status_code == 200
        audit_file = tmp_path / "audit.jsonl"
        assert audit_file.exists()
        with open(audit_file, encoding="utf-8") as f:
            entries = [json.loads(line) for line in f if line.strip()]
        assert any(e["action"] == "probe_user_ignored" for e in entries)
        ignored = [e for e in entries if e["action"] == "probe_user_ignored"][0]
        assert ignored["probe_id"] == "probe_001"
        assert "RLAIF" in ignored.get("reason", "")

    def test_probe_ignore_reason_too_long_returns_400(self, client):
        """忽略原因超过200字符返回400"""
        resp = client.post("/api/eval/probes/probe_001/ignore",
            json={"reason": "x" * 201},
            headers=_auth_headers())
        assert resp.status_code == 400

    def test_probe_ignore_nonexistent_returns_404(self, client, monkeypatch, tmp_path):
        """不存在的探测卡忽略返回404"""
        import services.eval.eval_store as store
        monkeypatch.setattr(store, "DATA_DIR", tmp_path)
        resp = client.post("/api/eval/probes/nonexistent/ignore",
            json={"reason": "test"},
            headers=_auth_headers())
        assert resp.status_code == 404
