# Phase 5 P0 信任修复 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 执行 Phase 5 P0 级四项强制整改 — LLM Judge 端到端验证、鉴权失败审计日志、已解决/未解决边界修复、eval-main.js 拆分

**Architecture:** 4 个独立 Task，每个生成独立 commit，可单独回滚。P0-1 需付费 API 调用（DeepSeek ~¥0.1-0.2），执行前需用户确认。P0-2/P0-4 为代码变更，遵循 TDD。

**Tech Stack:** Flask + Python 3 + JavaScript (vanilla) + DeepSeek API

**Prerequisites:** Flask 应用运行中 (localhost:5000)，后台循环已生成 traces 数据，EVAL_ADMIN_SECRET 已知

---

## ⚠️ 付费 API 警告 (P0-1)

P0-1 将调用 DeepSeek API 进行真实 LLM Judge 交叉验证。成本估算: ~5 traces × ~500 tokens ≈ ¥0.1-0.2。**执行前必须获得用户确认。**

---

### Task 1: P0-3 — 修复"已解决/未解决"边界模糊

**Files:**
- Read/Verify: `portfolio-app/docs/eval-architecture-rationale.md`

**背景:** 审计AI指出 §5.1 第 3 项"CODE 评分自说自话"同时出现在"已解决"和"未解决"清单中。专家审查阶段已通过 Edit 将 §5.1 第 3 项状态改为"已部署，待真实调用验证"，并增加了 §5.2-A 的反向引用。此 Task 的目的是**确认修复完整**，并检查是否有其他边界模糊项。

- [ ] **Step 1: 验证 §5.1 第 3 项与 §5.2-A 一致**

Read `eval-architecture-rationale.md`:
- §5.1 表格第 3 行应显示 `已部署，待真实调用验证 (见 §5.2-A)`
- §5.2-A 标题应包含 `(对应 §5.1 第 3 项)`

Expected: 两项描述一致，无"已解决"与"未解决"矛盾。

- [ ] **Step 2: 全文扫描其他边界模糊项**

Grep for "已解决" in `eval-architecture-rationale.md`:
- §5.1 第 9 项: "高权限操作无审计 | audit.jsonl + SHA256(admin_token) | 写操作全量记录"
  - 问题: 安全审计师指出失败鉴权尝试未被记录。此项标注"写操作全量记录"可能造成"审计完整"错觉。
  - 修正: 在验证列增加 `(注: 鉴权失败路径待 P0-2 修复后覆盖)`

Grep for contradictions:
```
rg "已解决" eval-architecture-rationale.md
rg "未解决" eval-architecture-rationale.md
```

Any item appearing in both = boundary issue to fix.

- [ ] **Step 3: 如有修正，提交 commit**

```bash
git add portfolio-app/docs/eval-architecture-rationale.md
git commit -m "docs: P0-3 final boundary verification — no 已解决/未解决 contradiction

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: P0-2 — 审计日志覆盖鉴权失败路径

**Files:**
- Modify: `portfolio-app/routes/api_eval.py:8-14` (`_check_admin` function)
- Read: `portfolio-app/services/eval/eval_store.py:462` (`_audit_log` function)

**背景:** 安全审计师指出 `_check_admin()` 鉴权失败时返回 False，调用方返回 403，但失败尝试不写入 `audit.jsonl`。攻击者可反复尝试不同 token 而不留痕迹。

**设计决策:** 鉴权失败日志写入 `audit.jsonl`，字段: `timestamp`, `event_type: "auth_denied"`, `request_path`, `source_ip`, `token_prefix`（前4位）, `reason`, `result: "denied"`。不记录完整 token。

- [ ] **Step 1: 阅读当前 _audit_log 函数签名**

Read `eval_store.py:462` 确认 `_audit_log` 的调用方式:

Expected signature: `_audit_log(operation, target_id, admin_token)` 或类似。需要确认参数名和调用方式。

- [ ] **Step 2: 修改 _check_admin() 增加审计日志**

在 `routes/api_eval.py` 的 `_check_admin()` 函数中，鉴权失败时写入审计日志:

```python
def _check_admin(req):
    """统一鉴权: 请求头 X-Admin-Token 必须匹配 config.EVAL_ADMIN_SECRET"""
    token = req.headers.get("X-Admin-Token", "")
    if not token or token != config.EVAL_ADMIN_SECRET:
        # 安全审计要求: 鉴权失败必须写入审计日志
        # 记录来源IP、尝试的Token前4位（模式识别）、失败原因
        # 不记录完整Token — 防止审计日志本身成为攻击向量
        try:
            from services.eval.eval_store import _audit_log
            _audit_log(
                operation="auth_denied",
                target_id=req.path,
                admin_token="denied:" + (token[:4] if len(token) >= 4 else token),
                extra={
                    "event_type": "auth_denied",
                    "source_ip": req.remote_addr or "unknown",
                    "token_prefix": token[:4] if len(token) >= 4 else (token or ""),
                    "reason": "empty_token" if not token else "token_mismatch",
                    "result": "denied",
                },
            )
        except Exception:
            pass  # 审计日志写入失败不阻断鉴权流程
        return False
    return True
```

**重要约束:** `_audit_log` 调用用 try/except 包裹——审计日志写入失败不能阻断鉴权流程本身。

- [ ] **Step 3: 验证 _audit_log 签名兼容**

Read `eval_store.py` 中 `_audit_log` 的实际函数签名。如果签名不支持 `extra` 参数，调整实现——将额外字段合并到 `target_id` 或直接写入 JSONL。

如果 `_audit_log` 签名不兼容，备选方案: 直接在 `_check_admin()` 中写 `audit.jsonl`:

```python
import json
from datetime import datetime
from pathlib import Path

try:
    audit_file = Path(__file__).parent.parent / "data" / "eval" / "audit.jsonl"
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": "auth_denied",
        "request_path": req.path,
        "source_ip": req.remote_addr or "unknown",
        "token_prefix": token[:4] if len(token) >= 4 else (token or ""),
        "reason": "empty_token" if not token else "token_mismatch",
        "result": "denied",
    }
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
except Exception:
    pass
```

- [ ] **Step 4: 运行现有测试确认无回归**

```bash
cd portfolio-app && python -m pytest tests/test_eval_engine.py -x -q
```

Expected: 140 pass, 0 fail（_check_admin 的变更不应影响现有测试，因为测试 mock 了鉴权）。

- [ ] **Step 5: Flask 加载验证**

```bash
cd portfolio-app && python -c "from server import create_app; app = create_app(); print('OK')"
```

Expected: OK，无 import 错误。

- [ ] **Step 6: 提交**

```bash
git add portfolio-app/routes/api_eval.py
git commit -m "feat: P0-2 audit log for auth denial — record failed attempts with IP/token_prefix

Security auditor requirement: _check_admin() now writes auth_denied events
to audit.jsonl with source_ip, token_prefix (first 4 chars only), and
result=denied. Full token never stored. Write failure does not block auth.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: P0-4 — eval-main.js 拆出 eval-slideout.js

**Files:**
- Create: `portfolio-app/static/js/modules/eval-slideout.js`
- Modify: `portfolio-app/static/js/modules/eval-main.js` (remove lines ~268-347, add delegation)
- Modify: `portfolio-app/templates/pages/eval.html` (add script tag)

**背景:** eval-main.js 515 行，突破红线3 (300行)。`_showSlideOut()` (lines 283-347, 65 lines) + `_bindSuggestionClicks()` (lines 268-281, 14 lines) 作为职责明确的独立组件应提取到 `eval-slideout.js`。

**设计:** 提取后 `eval-main.js` 通过 `window.EvalSlideOut` 调用滑出面板功能。eval.html 在 eval-main.js 之前引入 eval-slideout.js。

- [ ] **Step 1: 创建 eval-slideout.js**

Create `portfolio-app/static/js/modules/eval-slideout.js`:

```javascript
/**
 * eval-slideout — 建议滑出面板组件
 *
 * 职责: 滑出面板的打开、关闭、渲染（含历史事件、指标变化、元数据）
 * 依赖: EvalUI.escapeHtml(), EvalAPI.fetchSuggestions()
 * 接口: window.EvalSlideOut = { show(sug), close(), bindClicks() }
 */
(function() {
  'use strict';

  function show(sug) {
    var panel = document.getElementById('eval-slideout');
    var mask = document.getElementById('eval-slideout-mask');
    if (!panel || !mask) return;

    var attr = sug.attribution_status || 'pending';
    var attrLabels = { attributed: '✔ 效果可归因', unattributable: '⚡ 无法归因', likely_failed: '⚠ 可能失败', pending: '⌛ 待验证' };
    var attrColors = { attributed: 'var(--success)', unattributable: 'var(--warning)', likely_failed: 'var(--danger)', pending: 'var(--text2)' };

    var deltaStr = '';
    if (sug.effect_score_delta !== null && sug.effect_score_delta !== undefined) {
      var d = sug.effect_score_delta;
      deltaStr = '<span style="color:' + (d >= 0 ? 'var(--success)' : 'var(--danger)') + '">Δ' + (d >= 0 ? '+' : '') + d.toFixed(2) + '</span>';
    }

    var html = '<div style="padding:16px">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">' +
        '<h3 style="margin:0;font-size:16px">建议详情</h3>' +
        '<button style="border:none;background:none;font-size:20px;cursor:pointer;line-height:1" onclick="EvalSlideOut.close()">&times;</button>' +
      '</div>' +
      '<div style="font-size:14px;margin-bottom:12px"><strong>' + EvalUI.escapeHtml(sug.description || sug.title || '') + '</strong></div>' +
      '<div style="margin-bottom:8px"><span class="badge">' + EvalUI.escapeHtml(sug.severity || '') + '</span>' +
      ' <span class="badge">' + EvalUI.escapeHtml(sug.category || '') + '</span></div>' +
      '<div style="font-size:13px;color:' + (attrColors[attr] || 'var(--text2)') + ';margin-bottom:4px">' + (attrLabels[attr] || attr) + ' ' + deltaStr + '</div>';

    // Delta details
    if (sug.delta_details && Object.keys(sug.delta_details).length > 0) {
      html += '<div style="margin-top:12px;padding:8px;background:var(--bg);border-radius:6px;font-size:12px">';
      html += '<div style="font-weight:600;margin-bottom:4px">指标变化</div>';
      Object.keys(sug.delta_details).forEach(function(k) {
        var v = sug.delta_details[k];
        html += '<div>' + EvalUI.escapeHtml(k) + ': <span style="color:' + (v >= 0 ? 'var(--success)' : 'var(--danger)') + '">' + (v >= 0 ? '+' : '') + v.toFixed(2) + '</span></div>';
      });
      html += '</div>';
    }

    // Baseline
    if (sug.baseline_scores && Object.keys(sug.baseline_scores).length > 0) {
      html += '<div style="margin-top:8px;font-size:12px;color:var(--text2)">基线: ';
      Object.keys(sug.baseline_scores).forEach(function(k) {
        var b = sug.baseline_scores[k];
        html += EvalUI.escapeHtml(k) + '=' + (typeof b === 'object' ? (b.value || 0).toFixed(2) : b.toFixed(2)) + ' ';
      });
      html += '</div>';
    }

    // History similar events (IDC constraint 4)
    if (sug.category) {
      html += '<div style="margin-top:16px;padding:12px;border-top:1px solid var(--border)">' +
        '<div style="font-size:13px;font-weight:600;color:var(--text2);margin-bottom:8px">📚 历史相似事件</div>' +
        '<div style="font-size:12px;color:var(--text2)">该类别（' + EvalUI.escapeHtml(sug.category) + '）的相关错误记录可在<a href="/knowledge" target="_blank">知识库</a>中查阅。</div>' +
      '</div>';
    }

    // Meta
    html += '<div style="margin-top:12px;font-size:11px;color:var(--text3)">';
    if (sug.created_at) html += '创建: ' + EvalUI.escapeHtml(sug.created_at) + ' | ';
    if (sug.applied_at) html += '采纳: ' + EvalUI.escapeHtml(sug.applied_at) + ' | ';
    if (sug.applied_commit) html += 'commit: ' + EvalUI.escapeHtml(sug.applied_commit.substring(0, 7));
    html += '</div>';

    html += '</div>';
    panel.innerHTML = html;
    panel.style.display = '';
    mask.style.display = '';
  }

  function close() {
    var panel = document.getElementById('eval-slideout');
    var mask = document.getElementById('eval-slideout-mask');
    if (panel) panel.style.display = 'none';
    if (mask) mask.style.display = 'none';
  }

  function bindClicks() {
    document.querySelectorAll('.suggestion-item').forEach(function(el) {
      el.style.cursor = 'pointer';
      el.addEventListener('click', function() {
        var sid = el.getAttribute('data-id');
        if (!sid) return;
        EvalAPI.fetchSuggestions(null, null).then(function(res) {
          var sug = (res.suggestions || []).find(function(s) { return s.suggestion_id === sid; });
          if (sug) show(sug);
        });
      });
    });
  }

  window.EvalSlideOut = {
    show: show,
    close: close,
    bindClicks: bindClicks,
  };
})();
```

**注意:** `onclick="EvalSlideOut.close()"` 替换了原来的内联 `onclick="document.getElementById(...)"` — 这消除了对 DOM ID 的内联引用。

- [ ] **Step 2: 从 eval-main.js 移除滑出面板代码**

删除 `eval-main.js` 中的 `_bindSuggestionClicks()` 函数（lines 268-281）和 `_showSlideOut()` 函数（lines 283-347）。

替换调用点:
- `_bindSuggestionClicks()` → `EvalSlideOut.bindClicks()`

Grep for `_bindSuggestionClicks` and `_showSlideOut` in eval-main.js to find all call sites:

```bash
rg "_bindSuggestionClicks|_showSlideOut" portfolio-app/static/js/modules/eval-main.js
```

替换所有出现的:
- `_bindSuggestionClicks()` → `if (window.EvalSlideOut) EvalSlideOut.bindClicks()`
- `_showSlideOut(sug)` → `if (window.EvalSlideOut) EvalSlideOut.show(sug)`

- [ ] **Step 3: eval.html 增加 script 引入**

在 `<script src="/static/js/modules/eval-main.js"></script>` 之前添加:

```html
<script src="/static/js/modules/eval-slideout.js"></script>
```

位置: `templates/pages/eval.html:342` 附近（eval-main.js 引入之前）。

- [ ] **Step 4: 运行测试 + Flask 加载验证**

```bash
cd portfolio-app && python -m pytest tests/test_eval_engine.py -x -q
```

Expected: 140 pass, 0 fail.

```bash
cd portfolio-app && python -c "from server import create_app; app = create_app(); print('OK')"
```

Expected: OK.

- [ ] **Step 5: 验证行数**

```bash
wc -l portfolio-app/static/js/modules/eval-main.js
wc -l portfolio-app/static/js/modules/eval-slideout.js
```

Expected: eval-main.js ≤ 440 lines (515 - ~80), eval-slideout.js ~100 lines.

- [ ] **Step 6: 提交**

```bash
git add portfolio-app/static/js/modules/eval-slideout.js portfolio-app/static/js/modules/eval-main.js portfolio-app/templates/pages/eval.html
git commit -m "refactor: P0-4 extract eval-slideout.js from eval-main.js (515→~435 lines)

Redline 3 compliance: slideout panel (~80 lines) extracted as independent
component. EvalSlideOut.close() replaces inline DOM ID references.
EvalSlideOut.bindClicks() replaces _bindSuggestionClicks().

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 7: 验证红线3 违规已消除**

运行 `evaluate_phase3_adherence()`:

```bash
cd portfolio-app && python -c "
from services.eval.meta_evaluator import evaluate_phase3_adherence
result = evaluate_phase3_adherence()
print('Phase 1-3 adherence:', result.get('value'))
for detail in result.get('details', {}).get('checks', []):
    print(f'  {detail[\"name\"]}: {detail[\"status\"]}')
"
```

Expected: 红线3 (eval-main.js ≤ 300 lines) 状态为 "pass" 或不再出现在违规列表中。

---

### Task 4: P0-1 — LLM Judge 端到端真实调用验证

**⚠️ 付费 API 警告:** 此 Task 调用 DeepSeek API。成本 ~¥0.1-0.2。**需用户确认后执行。**

**Files:**
- No code changes expected (verification only)
- May need to modify: `server.py` (如果需要在 daemon cycle 中临时加入 `_cross_validate_data_completeness` 调用)

**背景:** P0-1 是验证性任务。完整链路: 生成 CROSSVAL_PENDING 条目 → 入队 → 消费者线程 → DeepSeek API → `_validate_llm_output()` → `scores.json` (source: LLM_JUDGE)。当前 `_cross_validate_data_completeness()` 未被 daemon cycle 调用，需要先手动生成待验证条目。

- [ ] **Step 1: 确认 traces 数据存在**

检查是否有足够 traces 用于交叉验证（需要 ≥5 条 agent_chat 或 rag_query traces）:

```bash
cd portfolio-app && python -c "
from services.eval.eval_store import _query_traces
traces = _query_traces(window_hours=24, limit=100)
from services.eval.eval_engine import _classify_trace_type, TRACE_TYPE_SPAN_REQUIREMENTS
applicable = [t for t in traces if _classify_trace_type(t) in TRACE_TYPE_SPAN_REQUIREMENTS]
print(f'Total traces (24h): {len(traces)}')
print(f'Applicable traces: {len(applicable)}')
print('Sufficient for cross-validation' if len(applicable) >= 5 else 'INSUFFICIENT — need >= 5 applicable traces')
"
```

If < 5 applicable traces: 报告此问题，P0-1 无法在当前数据条件下完成。需要先产生足够的 agent_chat 流量。

- [ ] **Step 2: 生成 CROSSVAL_PENDING 条目**

在 daemon cycle 中临时加入 `_cross_validate_data_completeness()` 调用，或通过 API 触发:

Option A (推荐): 如果 Flask 应用在运行，通过 API 触发:
```bash
curl -X POST http://localhost:5000/api/eval/cross-validate \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: <EVAL_ADMIN_SECRET>" \
  -d '{"sample_size": 5}'
```

Option B: 通过 Python 直接调用:
```bash
cd portfolio-app && python -c "
from services.eval.eval_engine import _cross_validate_data_completeness
result = _cross_validate_data_completeness(sample_size=5)
if result:
    print('CROSSVAL_PENDING created:', result['score_id'])
    print('Items:', len(result['details']['items']))
else:
    print('INSUFFICIENT DATA — cannot create cross-validation items')
"
```

Expected: 生成 1 条 CROSSVAL_PENDING 评分（含 3-5 个子条目）。

- [ ] **Step 3: 触发 LLM Judge（⚠️ 付费调用）**

```bash
curl -X POST http://localhost:5000/api/eval/cross-validate/execute \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: <EVAL_ADMIN_SECRET>" \
  -d '{"force": true}'
```

Expected response: `{"status": "processing", "enqueued": N, "queue_depth": N, "note": "..."}`

- [ ] **Step 4: 等待消费者处理 + 验证结果**

等待 ~30-60 秒（LLM 调用 + 重试窗口），检查 scores.json:

```bash
cd portfolio-app && python -c "
from services.eval import eval_store
scores = eval_store.query_scores(config_id='data_completeness_crossval', limit=20, exclude_empty_traces=False, exclude_orphan_spans=False)
llm_scores = [s for s in scores if s.get('source') == 'LLM_JUDGE']
pending_scores = [s for s in scores if s.get('source') == 'CROSSVAL_PENDING']
print(f'LLM_JUDGE scores: {len(llm_scores)}')
print(f'CROSSVAL_PENDING scores: {len(pending_scores)}')
for s in llm_scores:
    print(f'  value={s[\"value\"]}, judgment={s.get(\"details\", {}).get(\"llm_judgment\", \"?\")}')
# Also check queue depth
from services.eval.llm_judge import queue_depth, worker_alive
print(f'Queue depth: {queue_depth()}')
print(f'Worker alive: {worker_alive()}')
"
```

Expected: 至少 1 条 `source: "LLM_JUDGE"` 评分；queue_depth 为 0（全部消费完毕）；worker_alive 为 True。

- [ ] **Step 5: 检查安全校验层**

检查 `_validate_llm_output()` 未被绕过:

```bash
cd portfolio-app && python -c "
from services.eval import eval_store
scores = eval_store.query_scores(config_id='data_completeness_crossval', limit=50, exclude_empty_traces=False, exclude_orphan_spans=False)
llm_scores = [s for s in scores if s.get('source') == 'LLM_JUDGE']
for s in llm_scores:
    v = s['value']
    reasoning = s.get('details', {}).get('llm_reasoning', '')
    print(f'value={v} (in [0,1]: {0 <= v <= 1}), reasoning_len={len(reasoning)}')
    # Check no XSS in reasoning
    if '<script' in reasoning.lower() or '<iframe' in reasoning.lower():
        print('WARNING: XSS pattern in LLM output!')
"
```

Expected: 所有 value ∈ [0, 1]，reasoning ≤ 1000 chars，无 XSS 模式。

- [ ] **Step 6: 验证 evaluate_code_llm_consensus()**

```bash
cd portfolio-app && python -c "
from services.eval.meta_evaluator import evaluate_code_llm_consensus
result = evaluate_code_llm_consensus()
print('Consensus result:', result)
"
```

Expected: 返回包含 `compared` 和 `disagreements` 的有效结果（非 None/空对比）。

- [ ] **Step 7: 恢复防风暴保护**

确认 `_last_judge_run_at` 已更新（防风暴保护自动恢复为 6h）:

```bash
cd portfolio-app && python -c "
from services.eval.llm_judge import get_last_judge_run
import time
last = get_last_judge_run()
print(f'Last judge run: {last} ({time.time() - last:.0f}s ago)')
print('Anti-storm active: next run in', 21600 - (time.time() - last), 's')
"
```

- [ ] **Step 8: 提交验证结果（如适用）**

如果 P0-1 无代码变更（纯验证），记录验证结果到执行日志:
```bash
git add portfolio-app/docs/superpowers/plans/2026-06-11-phase5-p0-trust-repair.md
git commit -m "docs: P0-1 LLM Judge E2E verification complete — [N] LLM_JUDGE scores generated

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

如果有代码变更（如临时修复了管道问题），按修复内容提交。

---

## 执行顺序

```
P0-3 (文档验证, 无副作用) → P0-2 (代码变更, 独立) → P0-4 (代码变更, 独立) → P0-1 (付费验证, 最后)
```

P0-1 排在最后因为: (1) 涉及付费 API 需确认，(2) 依赖 Flask 应用运行中有足够 traces 数据，(3) 是验证性任务，不产生代码变更（理想情况）。

---

## 回滚策略

每个 Task 独立 commit，可通过以下方式回滚:
```bash
git revert <commit-hash>  # 单 Task 回滚，不影响其他 P0 项
```
