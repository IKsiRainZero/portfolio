# Eval Meta-Module Implementation Plan (M1-M6) — v5

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform eval from passive dashboard into the project's decision-making central nervous system — a meta-module that provides traceable, data-driven justification for every engineering decision.

**Architecture:** Dual-track transition. Core paths (deepseek_client, Flask hooks, agent_service) stay hardcoded. New sources use `emit_event()`. 6-ring trace chain with `chain_hash` integrity. Dual water source (retrospective + prospective). Probe cards for innovation signals. Meta-eval L2 on independent thread.

**Tech Stack:** Python/Flask, JavaScript (vanilla), Chart.js, JSONL/JSON file storage, threading.Timer

**Spec reference:** `docs/superpowers/specs/2026-06-13-eval-meta-module-design.md`

**Revision history:**
| Version | Date | Trigger | Changes |
|---------|------|---------|---------|
| v1 | 2026-06-13 | 初始 | M1-M6 完整计划 |
| v2 | 2026-06-13 | 对计划的反馈1 (总工程师) | M1 部署断裂修复、决策面注册表提前到 M3、beacon 披露提前到 M1、perf_check.sh 自动化 |
| v3 | 2026-06-13 | 对计划的反馈2 (交互设计顾问) | 评分卡折叠顺序与追问路径对齐、创新信号区/概念提示改为可配置、M3 增加用户路径测试 |
| v4 | 2026-06-13 | 对计划的反馈3 (安全审计师) | beacon 频率限制(10次/60s)、各M安全回归测试、探测卡忽略审计API |
| v5 | 2026-06-13 | 对计划的反馈4 (审计AI) | M1 alert_id契约验证、M3覆盖卡片三态空状态、M5探测卡resolution字段 |

---

## File Map

| File | Purpose | M1 | M2 | M3 | M4 | M5 | M6 |
|------|---------|:--:|:--:|:--:|:--:|:--:|:--:|
| `services/eval/trace_logger.py` | emit_event(), event_types registry | ● | | | | | |
| `services/eval/eval_store.py` | event storage, chain_hash, decision surface registry | ● | ● | | ● | | |
| `services/eval/eval_engine.py` | ingest findings, health checks, error patterns, decision surface loader | | ● | | ● | ● | |
| `services/eval/meta_evaluator.py` | L2 response rate definition | | ● | | | | |
| `routes/api_eval.py` | beacon, trace-chain, decision surfaces, probe ignore | ● | ● | ● | | ● | |
| `config.py` | scan resource limits, eval_coverage config | | | | ● | ● | |
| `server.py` | L2 independent Timer | ● | | | | | |
| `static/js/modules/eval-api.js` | sendBeacon, trace-chain fetch, decision surface API | ● | ● | ● | | | |
| `static/js/modules/eval-main.js` | probe cards, trace panel, concept tooltips, decision questions | | | ● | | ● | |
| `static/js/modules/eval-ui.js` | narrative rendering, probe card rendering | | | ● | | ● | |
| `static/js/modules/eval-charts.js` | coverage chart (M3) | | | ● | | | |
| `templates/pages/eval.html` | beacon disclosure, innovation area, coverage card | | | ● | | ● | |
| `tests/test_eval_core.py` | emit_event tests, chain_hash tests | ● | ● | | | | |
| `tests/test_eval_engine.py` | health check tests, scan limit tests | | | | ● | ● | |
| `tests/test_eval_api.py` | beacon 403, trace-chain, decision surface, probe ignore tests | ● | ● | ● | | ● | |
| `data/eval/modules/` | decision surface YAML files | | | | ● | | |

---

## M1: Event Pipeline Generalization — Dual Track (3-5 commits)

**Goal:** New `emit_event()` for all NEW event sources. Three core paths untouched.

### Task 1.1: Add scan resource limits to config.py

**Files:** Modify `portfolio-app/config.py`

- [ ] **Step 1: Add config constants**

```python
# ── 前瞻性扫描资源限制 (安全约束) ──
SCAN_MAX_FILE_BYTES = int(os.environ.get("SCAN_MAX_FILE_BYTES", "1048576"))  # 1MB
SCAN_MAX_FILES = int(os.environ.get("SCAN_MAX_FILES", "1000"))
SCAN_TIMEOUT_SECONDS = int(os.environ.get("SCAN_TIMEOUT_SECONDS", "30"))
```

- [ ] **Step 2: Verify import**

Run: `python -c "import config; print(config.SCAN_MAX_FILE_BYTES)"`
Expected: `1048576`

- [ ] **Step 3: Commit**

```bash
git add portfolio-app/config.py
git commit -m "feat: add scan resource limit configs for M5 prospective water sources"
```

### Task 1.2: Implement emit_event() + event_types registry

**Files:** Modify `services/eval/trace_logger.py`

- [ ] **Step 1: Write failing tests**

Create/modify `tests/test_eval_core.py` (add to existing TestTraceLogger class or new class):

```python
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
        import json
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eval_core.py::TestEmitEvent -v`
Expected: FAIL — `emit_event` / `register_event_type` not defined

- [ ] **Step 3: Implement emit_event() and event_types registry**

In `services/eval/trace_logger.py`, add after existing imports:

```python
# ══════════════════════════════════════════════
# 通用事件发射器 (M1: 双轨并行 — 新增来源用 emit_event, 核心路径保持硬编码)
# ══════════════════════════════════════════════

_event_types_registry = {}  # event_type -> {"description": str, "water_type": "retrospective"|"prospective"}


def register_event_type(event_type, description, water_type="retrospective"):
    """注册一个事件类型。已注册类型才能被 emit_event 接受。"""
    _event_types_registry[event_type] = {
        "description": description,
        "water_type": water_type,
    }


def emit_event(event_type, payload, timeout=5):
    """
    通用事件发射器 — 不依赖 Flask request context。
    
    安全约束:
      - event_type 必须在 _event_types_registry 中注册，否则拒绝写入 + 触发安全告警
      - payload 值序列化为 JSON，写入 events.jsonl
      - 内部委托现有 _record_span() 确保事件进入同一存储体系
    
    返回: True(成功) / False(被拒绝)
    """
    if event_type not in _event_types_registry:
        _log_security_event("emit_event_rejected_unregistered", {
            "event_type": event_type,
        })
        return False
    
    try:
        data_dir = Path(__file__).parent.parent.parent / "data" / "eval"
        data_dir.mkdir(parents=True, exist_ok=True)
        events_file = data_dir / "events.jsonl"
        
        entry = {
            "event_id": _generate_id(),
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "water_type": _event_types_registry[event_type]["water_type"],
            "payload": payload,
        }
        with open(events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


# 预注册已知事件类型
register_event_type("review_agent.finding", "Review Agent 审查发现", "retrospective")
register_event_type("knowledge.health_check", "知识管线健康检查", "retrospective")
register_event_type("eval.error_pattern_match", "历史错误模式匹配", "retrospective")
register_event_type("git.commit", "Git 提交事件", "retrospective")
register_event_type("test.run", "测试运行结果", "retrospective")
register_event_type("feedback.received", "用户反馈接收", "retrospective")
register_event_type("ui.interaction", "前端行为追踪", "retrospective")
register_event_type("eval.decision_surface_load_failed", "决策面加载失败", "retrospective")
```

Note: Need to add imports for `json`, `Path`, `datetime` if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_eval_core.py::TestEmitEvent -v`
Expected: 3 PASS

- [ ] **Step 5: Verify existing 172 tests still pass**

Run: `pytest tests/ -q`
Expected: 172+ passed (existing tests unaffected)

- [ ] **Step 6: Commit**

```bash
git add services/eval/trace_logger.py tests/test_eval_core.py
git commit -m "feat(M1): emit_event() generic event emitter + event_types whitelist

Security: unregistered event types rejected with security alert.
No Flask context required — works from any Python module.
Pre-registered: review_agent, knowledge, git, test, feedback, ui interaction."
```

### Task 1.3: Add /api/eval/beacon endpoint (frontend behavior tracking)

> **v3 修正 (安全审计师反馈):** 增加滑动窗口频率限制 — 每IP每60秒最多10次请求，超限返回429。

**Files:** Modify `routes/api_eval.py`, `static/js/modules/eval-api.js`

- [ ] **Step 1: Write failing test for beacon endpoint**

In `tests/test_eval_api.py`:

```python
def test_beacon_no_token_returns_403(self, client):
    """beacon 端点需要 admin token"""
    resp = client.post("/api/eval/beacon", json={"event_type": "ui.interaction", "panel_id": "overview"})
    assert resp.status_code == 403

def test_beacon_valid_token_returns_200(self, client, admin_headers):
    """合法 token + 合法字段返回 200"""
    resp = client.post("/api/eval/beacon",
        json={"event_type": "ui.interaction", "panel_id": "overview", "timestamp": 1700000000},
        headers=admin_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"

def test_beacon_rejects_unknown_fields(self, client, admin_headers):
    """非白名单字段被丢弃"""
    resp = client.post("/api/eval/beacon",
        json={"event_type": "ui.interaction", "panel_id": "overview", "mouse_x": 100, "keystrokes": "abc"},
        headers=admin_headers)
    assert resp.status_code == 200
    # mouse_x and keystrokes should be stripped by backend filter

def test_beacon_rejects_field_too_long(self, client, admin_headers):
    """超长字段被拒绝"""
    resp = client.post("/api/eval/beacon",
        json={"event_type": "x" * 51, "panel_id": "overview"},
        headers=admin_headers)
    assert resp.status_code == 400

def test_beacon_rate_limit_returns_429(self, client, admin_headers, monkeypatch):
    """每60秒超过10个请求后返回429"""
    import time
    # 冻结时间防止窗口滑出
    frozen = 1700000000.0
    monkeypatch.setattr(time, "time", lambda: frozen)
    for i in range(10):
        resp = client.post("/api/eval/beacon",
            json={"event_type": "ui.interaction", "panel_id": "overview", "timestamp": 1700000000},
            headers=admin_headers)
        assert resp.status_code == 200, f"request {i} should pass"
    # 第11个请求被拒绝
    resp = client.post("/api/eval/beacon",
        json={"event_type": "ui.interaction", "panel_id": "overview", "timestamp": 1700000000},
        headers=admin_headers)
    assert resp.status_code == 429
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_eval_api.py::test_beacon_no_token_returns_403 -v`
Expected: FAIL (404 or 405)

- [ ] **Step 3: Implement beacon endpoint**

In `routes/api_eval.py`, add after existing read endpoints:

```python
import time as _time_module  # if not already imported at top of file

BEACON_WHITELIST = {"event_type", "panel_id", "timestamp"}

# ── Beacon 频率限制 ──
_BEACON_RATE_LIMIT = 10       # max requests per window
_BEACON_RATE_WINDOW = 60      # window size in seconds
_beacon_rate_state = {}       # { ip_or_session_key: [timestamps...] }

def _check_beacon_rate_limit(key):
    """滑动窗口频率限制。返回 True=超限, False=放行。"""
    now = _time_module.time()
    window_start = now - _BEACON_RATE_WINDOW
    # 清理过期记录
    _beacon_rate_state[key] = [t for t in _beacon_rate_state.get(key, []) if t > window_start]
    if len(_beacon_rate_state[key]) >= _BEACON_RATE_LIMIT:
        return True
    _beacon_rate_state[key].append(now)
    return False

@eval_bp.route("/eval/beacon", methods=["POST"])
def beacon():
    """前端行为追踪端点。仅接受白名单字段。每60秒最多10次请求。"""
    if not _check_admin(request):
        return _require_admin()
    # 频率限制 (基于 IP + X-Forwarded-For 回退)
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
    if _check_beacon_rate_limit(client_ip):
        return jsonify({"error": "rate limit exceeded", "retry_after": _BEACON_RATE_WINDOW}), 429
    try:
        data = request.get_json(silent=True) or {}
        # 字段白名单过滤
        filtered = {k: data[k] for k in BEACON_WHITELIST if k in data}
        # 长度校验
        if "event_type" in filtered and len(str(filtered["event_type"])) > 50:
            return jsonify({"error": "event_type too long"}), 400
        if "panel_id" in filtered and len(str(filtered["panel_id"])) > 50:
            return jsonify({"error": "panel_id too long"}), 400
        filtered.setdefault("event_type", "ui.interaction")
        filtered.setdefault("timestamp", int(_time_module.time()))
        # 发射事件
        from services.eval.trace_logger import emit_event
        emit_event("ui.interaction", filtered)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

Note: need to `import time` in this file if not already imported.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_eval_api.py -k beacon -v`
Expected: 5 PASS (4 original + rate_limit)

- [ ] **Step 5: Add frontend sendBeacon + disclosure text**

In `static/js/modules/eval-api.js`, add:

```javascript
var EvalAPI = window.EvalAPI || {};

// ── Beacon (前端行为追踪) ──
EvalAPI.sendBeacon = function(eventType, panelId) {
    var token = (document.querySelector('meta[name="admin-token"]') || {}).content || '';
    fetch('/api/eval/beacon', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Admin-Token': token,
        },
        body: JSON.stringify({
            event_type: eventType,
            panel_id: panelId,
            timestamp: Date.now(),
        }),
        keepalive: false,
    }).catch(function() {});
};
```

In `templates/pages/eval.html`, add disclosure text at the bottom of `{% block content %}` (before closing `</div>` of `.eval-container`):

```html
<div style="font-size:11px;color:var(--text3);text-align:center;padding:16px 0;border-top:1px solid var(--border-light);margin-top:32px">
  本页面交互行为（点击、展开、切换面板）已匿名记录，用于优化评估系统。不追踪任何个人身份信息。
</div>
```

- [ ] **Step 6: Commit**

```bash
git add routes/api_eval.py tests/test_eval_api.py static/js/modules/eval-api.js
git commit -m "feat(M1): /api/eval/beacon endpoint + frontend sendBeacon

Security: admin auth required. Field whitelist (event_type/panel_id/timestamp only).
Rate limit: 10 req/60s per IP — 429 on exceed. Length limits enforced (50 chars).
Backend filtering rejects mouse/keyboard data."
Length limits enforced (50 chars). Backend filtering rejects mouse/keyboard data."
```

### Task 1.4: Add L2 independent Timer + L2 stub in server.py

**Files:** Modify `server.py`

- [ ] **Step 1: Add L2 timer with stub function**

In `server.py`, after the Flask app is created and before `app.run()`, add:

```python
def _start_meta_eval_l2_timer():
    """启动元评估 L2 独立检查线程 (每 2 小时)。
    
    M1: 使用 stub — run_l2_self_check() 实现在 M2 Task 2.2 完成。
         此处用 try/except 保护，防止 ImportError 导致应用崩溃。
    """
    import threading
    import sys
    from pathlib import Path
    from datetime import datetime

    def _l2_check():
        try:
            # M2 完成前，使用最低限度的 stub 检查
            try:
                from services.eval.meta_evaluator import run_l2_self_check
                result = run_l2_self_check()
            except ImportError:
                result = {"status": "pending", "note": "L2 not yet implemented — will activate in M2"}

            log_file = Path(__file__).parent / "data" / "eval" / "meta_eval_l2.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "result": result,
                }, ensure_ascii=False) + "\n")
            # 检查是否连续两次失败
            if result.get("status") not in ("ok", "pending"):
                with open(log_file) as f:
                    lines = f.readlines()
                if len(lines) >= 2:
                    prev = json.loads(lines[-2])
                    if prev.get("status") not in ("ok", "pending"):
                        print(f"[L2 WARNING] Meta-eval L2 failed twice consecutively ({result.get('status')})"
                              f" — manual intervention required", file=sys.stderr)
        except Exception as e:
            print(f"[L2 ERROR] Meta-eval L2 check crashed: {e}", file=sys.stderr)

    timer = threading.Timer(7200, _l2_check)  # 2 hours
    timer.daemon = True
    timer.start()
    return timer
```

Then call it after `create_app()`:

```python
if __name__ == "__main__":
    app = create_app()
    _start_meta_eval_l2_timer()
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
```

- [ ] **Step 2: Verify server.py loads without crash**

Run: `python -c "import server; print('L2 timer setup OK')"`
Expected: `L2 timer setup OK` (no crash — L2 stub handles missing import gracefully)

- [ ] **Step 3: Commit**

```bash
git add server.py
git commit -m "feat(M1): L2 independent timer with stub — graceful degrade until M2"
```

- [ ] **Step 4: Note for M2** — After `run_l2_self_check()` is implemented in Task 2.2, the ImportError fallback silently activates the real check. No code change needed in server.py.

### Task 1.5: Create performance benchmark script

**Files:** Create `scripts/perf_check.sh`

- [ ] **Step 1: Write the script**

```bash
#!/bin/bash
# perf_check.sh — Eval system performance regression test
# Run at each M acceptance gate. All metrics must stay within green/red lines.

ADMIN_TOKEN="${EVAL_ADMIN_TOKEN:-test}"
BASE="${1:-http://localhost:5000}"
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass=0
fail=0

check() {
    local name="$1" red="$2" actual="$3" unit="$4"
    if (( $(echo "$actual > $red" | bc -l 2>/dev/null || echo 0) )); then
        echo -e "${RED}[FAIL]${NC} $name: $actual$unit > $red$unit (red line)"
        ((fail++))
    else
        echo -e "${GREEN}[PASS]${NC} $name: $actual$unit <= $red$unit"
        ((pass++))
    fi
}

# 1. /api/eval/summary p95 latency
echo "--- /api/eval/summary p95 (100 requests) ---"
total=0
for i in $(seq 1 100); do
    t=$(curl -s -o /dev/null -w '%{time_total}' -H "X-Admin-Token: $ADMIN_TOKEN" "$BASE/api/eval/summary")
    total=$(echo "$total + $t" | bc)
done
avg=$(echo "scale=4; $total / 100" | bc)
echo "p95 estimate: ~$(echo "scale=4; $avg * 2" | bc)s (avg ${avg}s)"
check "/api/eval/summary p95" 0.5 "$avg" "s"

# 2. emit_event latency (if endpoint available)
echo "--- emit_event latency (10 calls) ---"
for i in $(seq 1 10); do
    curl -s -o /dev/null -w '%{time_total}\n' -X POST -H "Content-Type: application/json" \
        -H "X-Admin-Token: $ADMIN_TOKEN" \
        -d '{"event_type":"ui.interaction","panel_id":"perf_test","timestamp":'"$(date +%s)"'}' \
        "$BASE/api/eval/beacon"
done | awk '{sum+=$1; n++} END {printf "avg: %.4fs\n", sum/n}'

echo ""
echo "--- Result: $pass passed, $fail failed ---"
if [ $fail -gt 0 ]; then exit 1; fi
```

- [ ] **Step 2: Verify script is executable**

```bash
chmod +x scripts/perf_check.sh
bash scripts/perf_check.sh 2>&1 | head -20
```

(Will fail if no server running — that's expected. It validates script syntax.)

- [ ] **Step 3: Commit**

```bash
git add scripts/perf_check.sh
git commit -m "feat(M1): performance benchmark script for CI acceptance gates"
```

### Task 1.6: M1 integration test + verify

> **v4 修正 (审计AI反馈):** M1 必须验证 `_build_alerts()` 产出 `alert_id`，否则 M2 L2 响应率无法追溯告警→建议链路。

- [ ] **Step 1: Run full test suite**

```bash
cd portfolio-app && python -m pytest tests/ -q
```
Expected: 176+ passed (original 172 + 7 new tests)

- [ ] **Step 2: Verify existing core paths untouched**

```bash
git diff main -- services/eval/trace_logger.py | grep -E "^-.*_record_(llm|tool|http)_span"
```
Expected: **empty** (no core span recording functions were removed or modified)

- [ ] **Step 3: Verify alert_id contract for M2 trace chain**

```bash
cd portfolio-app && python -c "
import json
from pathlib import Path
scores_file = Path('data/eval/scores.json')
if not scores_file.exists():
    print('OK: cold start — no scores.json yet')
    exit(0)
scores = json.loads(scores_file.read_text())
alerts = [s for s in scores if s.get('type') == 'alert']
if not alerts:
    print('OK: no alerts yet')
    exit(0)
missing = [a for a in alerts if not a.get('alert_id')]
assert len(missing) == 0, f'CONTRACT BREAK: {len(missing)} alert(s) missing alert_id — M2 trace chain will fail'
print(f'OK: {len(alerts)} alerts all have alert_id — M2 contract satisfied')
"
```
If this fails: add `alert_id` generation to `_build_alerts()` before proceeding. Use `_generate_id()` (already in `services/eval/trace_logger.py`).

- [ ] **Step 4: Commit any final cleanup**

```bash
git add -A
git commit -m "chore(M1): integration verification — all tests pass, core paths untouched, alert_id contract verified"
```

**M1 Acceptance:**
- [x] emit_event() with whitelist + event_types registry
- [x] /api/eval/beacon endpoint with admin auth + field filtering
- [x] Beacon disclosure text in eval.html
- [x] L2 independent Timer with stub (graceful ImportError handling)
- [x] 3 core paths (deepseek_client / Flask hooks / agent_service) untouched
- [x] `scripts/perf_check.sh` created — verify with `bash scripts/perf_check.sh`
- [x] All existing 172 tests pass + 7+ new tests
- [x] emit_event() call latency < 5ms p95
- [x] `_build_alerts()` alert records contain `alert_id` — M2 trace-chain contract verified
- [x] **Security regression:** `pytest tests/test_eval_api.py -k "test_apply_reject_no_token_returns_403"` → audit.jsonl has `"result": "denied"`

---

## M2: Trace Chain Connectivity (2-3 commits)

### Task 2.1: Add chain_hash to eval_store

**Files:** Modify `services/eval/eval_store.py`

Add `chain_hash` field when saving suggestions:

```python
import hashlib

def _compute_chain_hash(event_id, metric_id, alert_id, suggestion_id):
    raw = f"{event_id}{metric_id}{alert_id}{suggestion_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def _verify_chain_hash(entry):
    """验证追溯链完整性。返回 True/False"""
    stored = entry.get("chain_hash")
    if not stored:
        return False
    computed = _compute_chain_hash(
        entry.get("source_event_id", ""),
        entry.get("source_metric_id", ""),
        entry.get("source_alert_id", ""),
        entry.get("suggestion_id", ""),
    )
    return stored == computed
```

- [ ] Step 1: Write failing test for chain_hash
- [ ] Step 2: Implement chain_hash in save_suggestion
- [ ] Step 3: Run tests, commit

### Task 2.2: Add L2 response rate definition to meta_evaluator.py

**Files:** Modify `services/eval/meta_evaluator.py`

Add `run_l2_self_check()` function:

```python
def run_l2_self_check():
    """
    L2 自检 — 独立于主后台线程运行。
    
    检查三项:
    1. L1 心跳 — last_run 时间戳是否在 6h 内
    2. 告警响应率 — 最近 24h 内的告警中，已响应 + 自动恢复的比例
       - 已响应: 告警→建议→已采纳或已拒绝(有决策记录)
       - 自动恢复: 告警对应指标在下一评估周期自动恢复(需被记录)
       - 未响应: 告警持续超过 2 个评估周期，无决策记录也无自动恢复
    3. L1 指标退化 — 元评估自身评分的趋势
    
    返回: {"status": "ok"|"warn"|"error", "checks": {...}}
    """
    ...
```

- [ ] Step 1: Write test for L2 check
- [ ] Step 2: Implement run_l2_self_check
- [ ] Step 3: Run tests, commit

### Task 2.2b: Add _load_decision_surfaces() to eval_store.py

**Files:** Modify `services/eval/eval_store.py`

This is the centralized loader for all decision surface YAML files. eval_engine must NOT directly read YAML files — it calls this function.

- [ ] **Step 1: Implement _load_decision_surfaces()**

In `services/eval/eval_store.py`, add:

```python
import yaml

_decisions_registry = None  # cached in-memory

def _load_decision_surfaces(force_reload=False):
    """
    Load all decision surface YAML files from data/eval/modules/.
    
    Returns dict: {module_name: surface_data, ...}
    Single file parse failure does not affect others — the failing file
    is skipped and recorded via emit_event.
    """
    global _decisions_registry
    if _decisions_registry is not None and not force_reload:
        return _decisions_registry
    
    modules_dir = DATA_DIR / "modules"
    if not modules_dir.exists():
        return {}
    
    registry = {}
    for yaml_file in sorted(modules_dir.glob("*.yaml")):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data and isinstance(data, dict) and "module" in data:
                registry[data["module"]] = data
        except Exception as e:
            try:
                from services.eval.trace_logger import emit_event
                emit_event("eval.decision_surface_load_failed", {
                    "file": str(yaml_file),
                    "error": str(e)[:200],
                })
            except Exception:
                pass
    
    _decisions_registry = registry
    return registry
```

- [ ] **Step 2: Write test**

```python
def test_load_decision_surfaces_empty_dir(self, tmp_path, monkeypatch):
    import yaml
    from services.eval.eval_store import _load_decision_surfaces
    monkeypatch.setattr("services.eval.eval_store.DATA_DIR", tmp_path)
    result = _load_decision_surfaces(force_reload=True)
    assert result == {}

def test_load_decision_surfaces_valid_and_invalid(self, tmp_path, monkeypatch):
    import yaml
    from services.eval.eval_store import _load_decision_surfaces
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()
    (modules_dir / "valid.yaml").write_text(yaml.dump({
        "module": "test_module", "decision_surface": []
    }))
    (modules_dir / "broken.yaml").write_text(":not:valid:yaml:")
    monkeypatch.setattr("services.eval.eval_store.DATA_DIR", tmp_path)
    result = _load_decision_surfaces(force_reload=True)
    assert len(result) == 1
    assert "test_module" in result
    # broken.yaml skipped, no crash
```

- [ ] **Step 3: Run tests + commit**

```bash
pytest tests/ -k decision_surface -v
git add services/eval/eval_store.py tests/
git commit -m "feat(M3): _load_decision_surfaces() — centralized YAML loader with failure isolation"
```

### Task 2.3: Add trace-chain API endpoint + evidence_brief

**Files:** Modify `routes/api_eval.py`

Add `GET /api/eval/trace-chain/<suggestion_id>` endpoint returning:
```json
{
  "chain": ["evt_001", "met_001", "alt_001", "sug_001"],
  "evidence_brief": {
    "metric": "data_completeness: 0.72 (↓0.13). 5/20 traces missing TOOL span.",
    "alert": "阈值0.9触发。missing_traces: [trace_12, trace_15, ...]",
    "suggestion": ...,
    "decision": ...
  },
  "chain_state": "full" | "partial" | "broken",
  "chain_hash_verified": true
}
```

- [ ] Step 1: Write 6 tests (full×2, partial×2, broken×2)
- [ ] Step 2: Implement endpoint
- [ ] Step 3: Run tests, verify p95 < 200ms with curl loop
- [ ] Step 4: Add frontend narrative rendering in eval-ui.js
- [ ] Step 5: Commit

**M2 Acceptance:**
- [x] chain_hash computed on save, verified in meta-eval
- [x] L2 response rate 3-state definition in meta_evaluator.py comments
- [x] trace-chain API with evidence_brief
- [x] 3 trace states (full/partial/broken) each with 2 tests
- [x] trace-chain API p95 < 200ms
- [x] `bash scripts/perf_check.sh` — all metrics within limits
- [x] **Security regression:** `pytest tests/test_eval_api.py -k "test_apply_reject_no_token_returns_403"` → audit.jsonl has `"result": "denied"`

---

## M3: Dashboard Explorability Upgrade (3-5 commits)

### Task 3.1: Score card 3-layer fold — user inquiry path ordering

> **v3 修正 (交互设计顾问反馈):** 折叠顺序按用户自然追问路径排列。
> 用户看到异常分数时第一反应是"为什么这么低/高？"→ 然后才是"这个分数在上下文中意味着什么？"
> L2 = 子指标分解 + 关联建议（回答"为什么"），L3 = 参照系 + 计算说明（回答"意味着什么"）

**Files:** Modify `static/js/modules/eval-main.js`, `static/js/modules/eval-ui.js`

- [ ] Step 1: Update `renderScoreCard` — L2 fold shows sub-indicator breakdown + related suggestions (answers "why so low/high?")
- [ ] Step 2: Add L3 collapsible section with reference frame (system avg / last month / baseline) + computation explanation + decision question from YAML (answers "what does this score mean in context?")
- [ ] Step 3: Add decision surfaces API endpoint `GET /api/eval/decision-surfaces`
- [ ] Step 4: Commit

### Task 3.2: Innovation signal area (probe cards) + concept tooltips

> **v3 修正 (交互设计顾问反馈 + 用户裁示):** 问题2和3因人而异，改为可配置选项而非强制单一种格式。

**Files:** Modify `templates/pages/eval.html`, `static/js/modules/eval-main.js`, `static/js/modules/eval-ui.js`

- [ ] Step 0: Add `EvalUIConfig` to eval-main.js (before other steps — config consumed by steps 1-4):

```javascript
// Eval UI 可配置选项 — 按用户偏好调整，无需改代码
var EvalUIConfig = {
    // 创新信号区位置: 'tab'(独立Tab, 默认) | 'overview'(总览面板内嵌)
    innovationSignalPlacement: 'tab',
    // 概念提示密度: 'sparse'(两层分层, 默认) | 'dense'(全部可见)
    tooltipDensity: 'sparse',
};
```

- [ ] Step 1: Add "创新信号" area — placement controlled by `EvalUIConfig.innovationSignalPlacement`:
  - `'tab'` (default): 独立 Tab 或模块详情面板底部子区域，蓝色信息条样式，与告警红色横幅/建议标准卡片视觉分离。用户需主动切换才能看到。
  - `'overview'`: 总览面板内嵌区域（备选，适合希望一眼看到探测卡的用户）
  - 两种模式共享相同的 `renderProbeCard()` 渲染逻辑

- [ ] Step 2: Add `renderProbeCard()` to eval-ui.js (countdown + ignore button)

- [ ] Step 3: Add ⓘ concept tooltips — density controlled by `EvalUIConfig.tooltipDensity`:
  - `'sparse'` (default): 两层分层。第一层 — 核心概念（决策面、探测卡、双水源）仅在首次出现的面板显示 ⓘ。第二层 — 技术细节（L0/L1/L2、水源类型）在元评估面板"系统说明"区域统一解释，主界面不显示 ⓘ
  - `'dense'`: 所有概念在所有出现位置都显示 ⓘ 图标（适合喜欢深入探索的用户）

- [ ] Step 4: Add frontend beacon tracking for tab switches and slideout opens

- [ ] Step 5: Add beacon disclosure text at Dashboard bottom

- [ ] Step 6: Commit

### Task 3.3: eval_coverage detector + coverage card (with empty-state guidance)

> **v4 修正 (审计AI反馈):** 覆盖卡片必须区分三种状态，避免空目录时显示无意义的 0/22。

**Files:** Modify `services/eval/eval_engine.py`, `routes/api_eval.py`, `static/js/modules/eval-charts.js`, `static/js/modules/eval-ui.js`

- [ ] Step 1: Implement `_check_eval_coverage()` — list services/ vs decision surfaces. Return status field:
  - `"empty"`: `data/eval/modules/` dir exists but has zero YAML files → coverage_state = `"cold_start"`
  - `"partial"`: ≥1 YAML loaded → coverage_state = `"partial"`, include `covered`/`uncovered` counts
  - `"load_error"`: dir has files but all failed to parse → coverage_state = `"load_failed"`

- [ ] Step 2: Add `GET /api/eval/coverage` endpoint returning `{coverage_state, covered_count, uncovered_count, module_list: [...]}`

- [ ] Step 3: Add coverage card to M3 details panel with three-state rendering:
  - `"cold_start"`: 显示引导文案 "决策面覆盖: 尚未定义。[点击了解如何创建决策面 →]"，蓝色信息条样式，链接到元评估面板的系统说明区域
  - `"partial"`: 正常显示 "已覆盖: N / 未覆盖: M"，附模块列表
  - `"load_failed"`: 显示警告 "决策面加载失败，请检查系统日志"，红色警告条样式

- [ ] Step 4: Commit

**M3 Acceptance:**
- [x] Score cards show L2 (sub-indicator breakdown + related suggestions) and L3 (reference frame + computation explanation + decision question)
- [x] Innovation signal area with probe cards (countdown + ignore) — placement configurable via `EvalUIConfig.innovationSignalPlacement`
- [x] Concept tooltips — density configurable via `EvalUIConfig.tooltipDensity` (`'sparse'` two-layer | `'dense'` all-visible)
- [x] eval_coverage card with 3-state rendering (cold_start/partial/load_failed) — no meaningless 0/22
- [x] _load_decision_surfaces() in eval_store.py — centralized YAML registry
- [x] /api/eval/summary p95 stays < 500ms
- [x] `bash scripts/perf_check.sh` — all metrics within limits
- [x] **Security regression:** `pytest tests/test_eval_api.py -k "test_apply_reject_no_token_returns_403"` → audit.jsonl has `"result": "denied"`
- [x] **User path test (交互设计顾问要求):** 给定追问场景"安全评分为什么从0.85降到0.72？"，测试者从 Dashboard 开始：
  1. 30秒内定位到安全评分卡
  2. 展开 L2 看到子指标分解
  3. 找到触发评分下降的具体建议
  4. 通过建议打开追溯面板看到原始事件
  - 任一步骤 >30秒或中途放弃 → M3 不予验收

---

## M4: Knowledge Pipeline + Review Agent Integration (2-3 commits)

### Task 4.1: knowledge_health_check()

**Files:** Modify `services/eval/eval_engine.py`

```python
def _knowledge_health_check():
    """检查知识管线健康度"""
    checks = {
        "chroma_sync_age_days": _check_last_sync_time(),
        "source_json_count": len(list((DATA_DIR / "knowledge").glob("*.json"))),
        "chroma_collection_count": _count_chroma_entries(),
        "orphan_kb_tags": _find_orphan_tags(),
    }
    from services.eval.trace_logger import emit_event
    emit_event("knowledge.health_check", checks)
    return checks
```

- [ ] Step 1: Write tests (normal + empty knowledge)
- [ ] Step 2: Implement _knowledge_health_check
- [ ] Step 3: Add knowledge health card to Dashboard details panel
- [ ] Step 4: Run tests, verify daemon loop < 10s
- [ ] Step 5: Commit

### Task 4.2: review_agent + doc_indexer integration

**Files:** Modify `services/review_agent.py`

Add `emit_event("review_agent.finding", ...)` call after findings generation (single line appended — no logic change).

**Files:** Modify `services/eval/eval_engine.py`

```python
def _check_error_patterns():
    """扫描历史错误文档，匹配当前系统状态"""
    ...
```

- [ ] Step 1: Write tests for error pattern matching
- [ ] Step 2: Implement _check_error_patterns
- [ ] Step 3: Add review_agent emit_event call
- [ ] Step 4: Run tests, verify daemon loop < 10s
- [ ] Step 5: Commit

**M4 Acceptance:**
- [x] Knowledge health metrics on Dashboard
- [x] review_agent findings flow into eval events
- [x] Historical error pattern detection
- [x] Daemon health check < 10s per iteration
- [x] `bash scripts/perf_check.sh` — all metrics within limits
- [x] **Security regression:** `pytest tests/test_eval_api.py -k "test_apply_reject_no_token_returns_403"` → audit.jsonl has `"result": "denied"`

---

## M5: Prospective Water Sources + Probe Cards (2-3 commits)

### Task 5.1: Implement 3 prospective detectors with resource limits

**Files:** Modify `services/eval/eval_engine.py`

```python
def _check_kb_application_gap():
    """知识-应用差距检测。硬性限制: 单文件≤1MB, 最多1000文件, 30s超时."""
    ...

def _check_module_staleness():
    """模块变更停滞检测."""
    ...

def _check_error_recurrence():
    """重复错误指纹检测."""
    ...
```

- [ ] Step 1: Write tests for each detector (normal + timeout + too-many-files)
- [ ] Step 2: Implement all 3 detectors with configurable limits from config.py
- [ ] Step 3: Add probe card generation with recurrence_count
- [ ] Step 4: Run tests, verify each < 30s, daemon total < 60s
- [ ] Step 5: Commit

### Task 5.2: Probe card frontend + recurrence tracking + ignore audit + resolution

> **v3 修正 (安全审计师):** 探测卡"忽略"是决策行为，必须写入 audit.jsonl。
> **v4 修正 (审计AI):** 增加 `resolution` 字段区分用户忽略/自动过期/升级建议，避免审计盲区。

**Files:** Modify `routes/api_eval.py`, `static/js/modules/eval-ui.js`, `static/js/modules/eval-main.js`, `services/eval/eval_engine.py`, `tests/test_eval_api.py`

- [ ] **Step 0: Write failing test for probe ignore API**

In `tests/test_eval_api.py`:

```python
def test_probe_ignore_no_token_returns_403(self, client):
    """探测卡忽略端点需要 admin token"""
    resp = client.post("/api/eval/probes/probe_001/ignore", json={"reason": "known issue"})
    assert resp.status_code == 403

def test_probe_ignore_writes_audit(self, client, admin_headers, tmp_path, monkeypatch):
    """忽略操作写入 audit.jsonl 并记录原因"""
    import services.eval.eval_store as store
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    resp = client.post("/api/eval/probes/probe_001/ignore",
        json={"reason": "Not applicable — project doesn't use RLAIF"},
        headers=admin_headers)
    assert resp.status_code == 200
    audit_file = tmp_path / "audit.jsonl"
    assert audit_file.exists()
    import json
    with open(audit_file) as f:
        entries = [json.loads(line) for line in f]
    assert any(e["action"] == "probe_ignored" for e in entries)
    ignored = [e for e in entries if e["action"] == "probe_ignored"][0]
    assert ignored["probe_id"] == "probe_001"
    assert "RLAIF" in ignored.get("reason", "")

def test_probe_ignore_reason_too_long_returns_400(self, client, admin_headers):
    """忽略原因超过200字符返回400"""
    resp = client.post("/api/eval/probes/probe_001/ignore",
        json={"reason": "x" * 201},
        headers=admin_headers)
    assert resp.status_code == 400
```

- [ ] **Step 1: Run to verify fail**

Run: `pytest tests/test_eval_api.py -k probe_ignore -v`
Expected: FAIL (404 — endpoint not yet defined)

- [ ] **Step 2: Implement probe ignore API**

In `routes/api_eval.py`:

```python
@eval_bp.route("/eval/probes/<probe_id>/ignore", methods=["POST"])
def ignore_probe(probe_id):
    """探测卡忽略 — 决策行为，写入审计日志。"""
    if not _check_admin(request):
        return _require_admin()
    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason", "")).strip()[:200]  # max 200 chars, silently truncate
    if "reason" in data and len(str(data["reason"])) > 200:
        return jsonify({"error": "reason too long (max 200 chars)"}), 400
    try:
        from services.eval.eval_store import _write_audit
        _write_audit({
            "action": "probe_ignored",
            "probe_id": probe_id,
            "reason": reason or None,
            "timestamp": int(time.time()),
        })
        return jsonify({"status": "ok", "probe_id": probe_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

Note: Ensure `import time` is present at top of `routes/api_eval.py`.

- [ ] **Step 2b: Define resolution field in probe storage**

In `services/eval/eval_engine.py`, when a probe card is created (in `_check_kb_application_gap`, `_check_module_staleness`, `_check_error_recurrence`), include:

```python
"resolution": None,  # None=active, "user_ignored"|"auto_expired"|"promoted_to_suggestion"
```

In `services/eval/eval_store.py` (or wherever probes are persisted), add a helper:

```python
def _resolve_probe(probe_id, resolution, reason=None):
    """记录探测卡结局。resolution 必须是 user_ignored | auto_expired | promoted_to_suggestion"""
    valid = {"user_ignored", "auto_expired", "promoted_to_suggestion"}
    if resolution not in valid:
        raise ValueError(f"Invalid resolution: {resolution}")
    # 更新探测卡存储记录中的 resolution 字段
    # 写入 audit.jsonl
    _write_audit({
        "action": f"probe_{resolution}",
        "probe_id": probe_id,
        "reason": reason or None,
        "timestamp": int(time.time()),
    })
```

Update the ignore API (`routes/api_eval.py`) to call `_resolve_probe(probe_id, "user_ignored", reason)`.

In `_effect_tracking_loop()` or the daily daemon, add auto-expiry logic:
```python
# 探测卡自动过期检查 (30天)
for probe in _load_probes():
    if probe.get("resolution") is not None:
        continue
    age_days = (now - probe["created_at"]).days
    if age_days >= 30:
        _resolve_probe(probe["probe_id"], "auto_expired")
```

And in recurrence→promotion logic (Task 5.2 Step 3): when recurrence ≥ 3 triggers meta-eval suggestion, call `_resolve_probe(probe_id, "promoted_to_suggestion")`.

- [ ] **Step 2c: Update frontend to display resolution status**

In `static/js/modules/eval-ui.js`, probe card rendering must NOT simply remove resolved cards. Instead:
- Active probes: normal rendering (blue info bar, ignore button)
- `user_ignored`: show "已忽略（原因：xxx）" in muted style
- `auto_expired`: show "已过期（未处理）" in muted style
- `promoted_to_suggestion`: show "已升级为建议" with link to suggestion

Resolved probes render below active probes with a subtle divider and reduced opacity.

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/test_eval_api.py -k probe_ignore -v`
Expected: 3 PASS

- [ ] **Step 4: Implement probe card ignore button with optional reason**

In `static/js/modules/eval-ui.js`, update the ignore handler:

```javascript
EvalUI.ignoreProbe = function(probeId, cardEl) {
    var reason = '';
    // 可选忽略原因输入框
    var promptEl = document.createElement('div');
    promptEl.className = 'probe-ignore-prompt';
    promptEl.innerHTML = '<textarea placeholder="忽略原因（可选，不超过200字）" maxlength="200" rows="2" style="width:100%;margin:8px 0;padding:6px;font-size:13px;"></textarea>' +
        '<button class="btn-confirm-ignore">确认忽略</button>' +
        '<button class="btn-cancel-ignore">取消</button>';
    cardEl.appendChild(promptEl);

    promptEl.querySelector('.btn-cancel-ignore').addEventListener('click', function() {
        promptEl.remove();
    });

    promptEl.querySelector('.btn-confirm-ignore').addEventListener('click', function() {
        reason = promptEl.querySelector('textarea').value.trim().slice(0, 200);
        var token = (document.querySelector('meta[name="admin-token"]') || {}).content || '';
        fetch('/api/eval/probes/' + encodeURIComponent(probeId) + '/ignore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Admin-Token': token },
            body: JSON.stringify({ reason: reason }),
        }).then(function(r) {
            if (r.ok) { cardEl.remove(); }
        }).catch(function() {});
    });
};
```

In `static/js/modules/eval-main.js`, wire the ignore button to call `EvalUI.ignoreProbe(probeId, cardEl)` instead of directly removing the card.

- [ ] **Step 5: Commit**

```bash
git add routes/api_eval.py tests/test_eval_api.py static/js/modules/eval-ui.js static/js/modules/eval-main.js
git commit -m "feat(M5): probe ignore API with audit logging + optional reason

Security: POST /api/eval/probes/<id>/ignore writes audit.jsonl (action=probe_ignored).
Frontend: optional reason input (max 200 chars) before confirming ignore.
Decision traceability: who ignored which probe, when, and why."
```

**M5 Acceptance:**
- [x] 3 prospective detectors running daily (each < 30s)
- [x] Resource limits enforced (1MB/1000 files/30s)
- [x] probe cards with recurrence_count
- [x] 3x recurrence → meta-eval suggestion
- [x] `POST /api/eval/probes/<id>/ignore` with audit.jsonl logging + optional reason (max 200 chars)
- [x] Probe `resolution` field: user_ignored / auto_expired (30d) / promoted_to_suggestion — audit distinction, frontend shows outcome
- [x] Daemon total health check < 60s
- [x] `bash scripts/perf_check.sh` — all metrics within limits
- [x] **Security regression:** `pytest tests/test_eval_api.py -k "test_apply_reject_no_token_returns_403"` → audit.jsonl has `"result": "denied"`

---

## M6: Documentation + Meeting Sync (1 commit)

### Task 6.1: Final verification + sync

- [ ] Step 1: Run full test suite — all passing
- [ ] Step 2: **Security regression:** `pytest tests/test_eval_api.py -k "test_apply_reject_no_token_returns_403"` → audit.jsonl has `"result": "denied"`
- [ ] Step 3: Run perf comparison (`scripts/perf_compare.sh`)
- [ ] Step 4: Update spec to "executed" status with deviations noted
- [ ] Step 5: Write meeting sync summary (< 1500 words)
- [ ] Step 6: Final commit

---

## Performance Baselines to Verify Each M

| Measurement | Baseline | Red Line | Method |
|-------------|----------|----------|--------|
| `/api/eval/summary` p95 | < 500ms | ≥ 500ms | curl 100x |
| `emit_event()` latency | < 5ms | ≥ 10ms | time.perf_counter in test |
| Daemon single loop | < 60s | ≥ 60s | heartbeat log timestamps |
| Prospective detector (each) | < 30s | > 30s | first-run timing |
| `/api/eval/trace-chain/<id>` p95 | < 200ms | > 500ms | curl 50x |
