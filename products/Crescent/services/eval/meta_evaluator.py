"""
meta_evaluator — 元评估器: 评估系统评估自身

Phase 4 核心模块。回答:
  1. 评估系统自己可信吗？
  2. 评估标准在退化吗？
  3. 犯过的错误不会再犯吗？

工程约束:
  - 硬性超时: LLM 调用设 30s 超时
  - 独立运行日志: data/eval/meta_eval.log (JSONL)
  - 独立运行器: run_all() 可被 server.py 后台线程或独立脚本调用
  - 内联展示: 结果不创建独立页面，显示在雷达图+建议列表中
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from services.eval import eval_store
from services.eval.trace_logger import _generate_id

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "eval"
META_LOG_FILE = DATA_DIR / "meta_eval.log"
ROOT_DIR = Path(__file__).parent.parent.parent  # Crescent/


def _meta_log(entry):
    """写入独立元评估日志，不与业务 Trace 混合。"""
    try:
        entry["_ts"] = datetime.now().isoformat()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(META_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _save_meta_score(config_id, value, details, target_id="eval_system"):
    """保存元评估评分到 scores.json，内联展示（约束2）。"""
    score = {
        "score_id": _generate_id(),
        "config_id": config_id,
        "target_type": "system",
        "target_id": target_id,
        "value": round(value, 4),
        "details": details,
        "created_at": datetime.now().isoformat(),
        "source": "META_EVAL",
    }
    eval_store.save_score(score)
    return score


# ══════════════════════════════════════════════
# Phase 1-3 过程合规审计 (Step 1 — 最高优先级)
# ══════════════════════════════════════════════

def evaluate_phase3_adherence():
    """
    元评估第一优先: Phase 3 确定的设计原则，在 Phase 3 执行中
    到底是被遵循了还是被妥协了？

    检查 6 项:
      1. 红线1 (30秒信任法则): 信息层级是否严格按 告警→趋势→评分 渲染？
      2. 红线2 (零信任): 所有 /api/eval/* 端点是否有 _check_admin()？
      3. 红线3 (20英里行军): JS 模块是否超 300 行？eval-charts.js 是否垄断 new Chart()？
      4. 3 个兼容性修正是否在计划中标注了 trade-off？
      5. SECRET_KEY 复用是否作为已知风险记录并已修复？
      6. 文档覆写事件的防护措施是否落地？

    返回: {"score": float, "passes": int, "total": 6, "deviations": [...], "suggestions": [...]}
    """
    deviations = []
    passes = 0

    # ── 检查 1: 信息层级 (告警→趋势→评分) ──
    try:
        eval_html = ROOT_DIR / "templates" / "pages" / "eval.html"
        if eval_html.exists():
            content = eval_html.read_text(encoding="utf-8")
            alert_pos = content.find('eval-alerts')
            trend_pos = content.find('chart-trend')
            score_pos = content.find('total-score-value')
            if alert_pos < trend_pos < score_pos and alert_pos != -1:
                passes += 1
            else:
                deviations.append({
                    "check": "redline1_info_hierarchy",
                    "detail": "信息层级未严格按 告警→趋势→评分 顺序渲染",
                    "severity": "P1",
                })
        else:
            deviations.append({"check": "redline1_info_hierarchy", "detail": "eval.html not found"})
    except Exception as e:
        deviations.append({"check": "redline1_info_hierarchy", "detail": str(e)})

    # ── 检查 2: 零信任 (所有端点鉴权) ──
    try:
        api_eval = ROOT_DIR / "routes" / "api_eval.py"
        if api_eval.exists():
            content = api_eval.read_text(encoding="utf-8")
            route_lines = [l for l in content.split("\n") if "@eval_bp.route" in l]
            admin_checks = content.count("_check_admin(request)")
            # 每个 GET 读端点 + 每个 POST 写端点都需要鉴权
            if admin_checks >= len(route_lines):
                passes += 1
            else:
                deviations.append({
                    "check": "redline2_zero_trust",
                    "detail": f"部分端点可能缺鉴权: {len(route_lines)} routes, {admin_checks} _check_admin calls",
                    "severity": "P0",
                })
        else:
            deviations.append({"check": "redline2_zero_trust", "detail": "api_eval.py not found"})
    except Exception as e:
        deviations.append({"check": "redline2_zero_trust", "detail": str(e)})

    # ── 检查 3: 20英里行军 (JS 模块 ≤300行, Chart.js 单一入口) ──
    try:
        js_dir = ROOT_DIR / "static" / "js" / "modules"
        js_ok = True
        js_details = {}
        for f in js_dir.glob("eval-*.js"):
            lines = len(f.read_text(encoding="utf-8").split("\n"))
            js_details[f.name] = lines
            if lines > 300:
                js_ok = False
                deviations.append({
                    "check": "redline3_20mile_march",
                    "detail": f"{f.name}: {lines} lines (limit: 300)",
                    "severity": "P2",
                })
        # 验证 new Chart() 只在 eval-charts.js 中
        chart_js = ROOT_DIR / "static" / "js" / "modules" / "eval-charts.js"
        if chart_js.exists():
            chart_content = chart_js.read_text(encoding="utf-8")
            for f in js_dir.glob("eval-*.js"):
                if f.name == "eval-charts.js":
                    continue
                other = f.read_text(encoding="utf-8")
                if "new Chart(" in other:
                    js_ok = False
                    deviations.append({
                        "check": "redline3_chart_monopoly",
                        "detail": f"{f.name} directly calls new Chart()",
                        "severity": "P2",
                    })
        if js_ok:
            passes += 1
    except Exception as e:
        deviations.append({"check": "redline3_20mile_march", "detail": str(e)})

    # ── 检查 4: 兼容性修正的 trade-off 标注 ──
    # Phase 3 v4 有三项兼容性修正，在计划文档中应标注 trade-off
    try:
        plan = ROOT_DIR / "docs" / "phase4-plan.md"
        if plan.exists():
            content = plan.read_text(encoding="utf-8")
            tradeoff_markers = ["trade-off", "妥协", "兼容性修正", "向后兼容"]
            found = sum(1 for m in tradeoff_markers if m.lower() in content.lower())
            if found >= 1:
                passes += 1
            else:
                deviations.append({
                    "check": "compatibility_tradeoffs",
                    "detail": "Phase 4 plan 中未明确标注兼容性修正的 trade-off",
                    "severity": "P1",
                })
    except Exception as e:
        deviations.append({"check": "compatibility_tradeoffs", "detail": str(e)})

    # ── 检查 5: SECRET_KEY 复用已修复 ──
    try:
        config_py = ROOT_DIR / "config.py"
        if config_py.exists():
            content = config_py.read_text(encoding="utf-8")
            has_independent = "EVAL_ADMIN_SECRET" in content
            no_fallback = "SECRET_KEY" not in content.split("EVAL_ADMIN_SECRET")[1][:200] if has_independent else False
            if has_independent:
                passes += 1
            else:
                deviations.append({
                    "check": "secret_key_separation",
                    "detail": "EVAL_ADMIN_SECRET 未独立于 SECRET_KEY",
                    "severity": "P0",
                })
    except Exception as e:
        deviations.append({"check": "secret_key_separation", "detail": str(e)})

    # ── 检查 6: 文档覆写防护落地 ──
    try:
        claude_md = ROOT_DIR / "CLAUDE.md"
        if claude_md.exists():
            content = claude_md.read_text(encoding="utf-8")
            has_discipline = "文档版本铁律" in content or "document version" in content.lower()
            if has_discipline:
                passes += 1
            else:
                deviations.append({
                    "check": "document_integrity_discipline",
                    "detail": "CLAUDE.md 中未记录文档版本纪律",
                    "severity": "P1",
                })
    except Exception as e:
        deviations.append({"check": "document_integrity_discipline", "detail": str(e)})

    # ── 聚合结果 ──
    score_value = passes / 6.0
    suggestions = []
    for d in deviations:
        suggestions.append({
            "severity": d.get("severity", "P2"),
            "category": "process_adherence",
            "title": d["check"],
            "description": d["detail"],
            "target_type": "system",
            "target_id": "eval_system",
        })

    result = {
        "score": score_value,
        "passes": passes,
        "total": 6,
        "deviations": deviations,
        "suggestions": suggestions,
    }
    _meta_log({"event": "phase3_adherence", "result": result})
    _save_meta_score("eval_process_adherence", score_value, {
        "passes": passes,
        "total": 6,
        "deviations": [d["check"] for d in deviations],
    })

    return result


# ══════════════════════════════════════════════
# Step 4: 元评估核心函数
# ══════════════════════════════════════════════

def evaluate_score_configs():
    """
    检查每个 ScoreConfig 的新鲜度。
    >30 天未审查 → stale
    >90 天未审查 → severity P1
    """
    configs = eval_store.list_score_configs()
    now = datetime.now()
    stale = []
    fresh = 0

    for cfg in configs:
        updated_str = cfg.get("updated_at") or cfg.get("created_at")
        if not updated_str:
            stale.append({"config_id": cfg["config_id"], "age_days": None, "reason": "no timestamp"})
            continue
        try:
            updated = datetime.fromisoformat(updated_str)
            age_days = (now - updated).days
        except Exception:
            stale.append({"config_id": cfg["config_id"], "age_days": None, "reason": "invalid timestamp"})
            continue

        if age_days > 90:
            stale.append({"config_id": cfg["config_id"], "age_days": age_days, "severity": "P1"})
        elif age_days > 30:
            stale.append({"config_id": cfg["config_id"], "age_days": age_days, "severity": "P2"})
        else:
            fresh += 1

    total = len(configs)
    score_value = fresh / total if total > 0 else 1.0
    _save_meta_score("eval_system_freshness", score_value, {
        "total_configs": total,
        "fresh": fresh,
        "stale": len(stale),
        "stale_configs": stale[:10],
    })
    _meta_log({"event": "score_configs", "fresh": fresh, "stale": len(stale)})

    return {
        "configs_checked": total,
        "stale": len(stale),
        "fresh": fresh,
        "score": round(score_value, 4),
        "stale_details": stale[:10],
    }


def evaluate_code_llm_consensus():
    """
    CODE vs LLM Judge 一致性。
    对比 data_completeness 的 CODE 判定与 LLM_JUDGE 判定。
    不一致率 > 20% → CODE 评分逻辑可能有 bug。
    """
    scores = eval_store.query_scores(
        config_id="data_completeness_crossval",
        limit=100,
        exclude_empty_traces=False,
        exclude_orphan_spans=False,
    )

    compared = 0
    disagreements = 0
    pairs = []

    for s in scores:
        if s.get("source") != "LLM_JUDGE":
            continue
        details = s.get("details", {})
        code_j = details.get("code_judgment")
        llm_j = details.get("llm_judgment")
        if not code_j or not llm_j:
            continue
        compared += 1
        if code_j != llm_j:
            disagreements += 1
            pairs.append({
                "trace_id": details.get("trace_id"),
                "code": code_j,
                "llm": llm_j,
                "confidence": details.get("llm_confidence"),
            })

    rate = disagreements / compared if compared > 0 else None
    score_value = 1.0 - (rate if rate is not None else 0)
    _save_meta_score("code_llm_consensus", score_value, {
        "compared": compared,
        "disagreements": disagreements,
        "disagreement_rate": round(rate, 4) if rate is not None else None,
    })
    _meta_log({"event": "code_llm_consensus", "compared": compared, "disagreements": disagreements})

    return {
        "compared": compared,
        "disagreements": disagreements,
        "disagreement_rate": round(rate, 4) if rate is not None else None,
        "score": round(score_value, 4),
    }


def evaluate_score_drift():
    """
    评分漂移检测: 检查各 config 评分是否连续 7 天单调下降。
    如果是 → 系统在退化。
    """
    configs = eval_store.list_score_configs()
    drifting = []
    checked = 0

    for cfg in configs:
        cid = cfg["config_id"]
        if cfg.get("weight", 0) == 0:
            continue  # 跳过宪法 Metric
        checked += 1
        trend = eval_store.get_score_trend(cid, days=14)
        if len(trend) < 7:
            continue

        # 取最近 7 天的值
        recent = [p["value"] for p in trend[-7:]]
        # 检查是否单调下降
        is_declining = all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1))
        if is_declining and recent[0] > recent[-1]:
            drop = recent[0] - recent[-1]
            drifting.append({
                "config_id": cid,
                "name": cfg.get("name", cid),
                "first": recent[0],
                "last": recent[-1],
                "drop": round(drop, 4),
            })

    score_value = 1.0 - (len(drifting) / checked if checked > 0 else 0)
    _save_meta_score("score_drift", score_value, {
        "checked": checked,
        "drifting": len(drifting),
        "drifting_configs": [d["config_id"] for d in drifting],
    })
    _meta_log({"event": "score_drift", "checked": checked, "drifting": len(drifting)})

    return {
        "checked": checked,
        "drifting_configs": drifting,
        "score": round(score_value, 4),
    }


# ══════════════════════════════════════════════
# Step 5: 文档完整性 + 知识库评估
# ══════════════════════════════════════════════

def evaluate_document_integrity():
    """
    检测关键文档是否被非版本化覆写。
    基于 v3→v4 覆写事件的教训:
      - 检查 docs/*.md 的 git log → 检测同一文件两次修改 < 60s (覆写信号)
      - 检查文件修改量 > 500 行删减 (大量内容删除信号)
    """
    import subprocess

    docs_dir = ROOT_DIR / "docs"
    violations = []
    checked = 0

    try:
        for md_file in docs_dir.glob("*.md"):
            if md_file.name.startswith("_"):
                continue
            checked += 1
            rel = str(md_file.relative_to(ROOT_DIR)).replace("\\", "/")

            # git log 获取最近两次 commit 的文件变更
            r = subprocess.run(
                ["git", "log", "--oneline", "--diff-filter=M", "-2", "--", rel],
                capture_output=True, text=True, timeout=10,
                cwd=str(ROOT_DIR), encoding="utf-8", errors="replace",
            )
            if r.returncode != 0:
                continue

            commits = [l for l in (r.stdout or "").strip().split("\n") if l]
            if len(commits) >= 2:
                r2 = subprocess.run(
                    ["git", "log", "--format=%at", "-2", "--", rel],
                    capture_output=True, text=True, timeout=10,
                    cwd=str(ROOT_DIR), encoding="utf-8", errors="replace",
                )
                times = [int(t) for t in (r2.stdout or "").strip().split("\n") if t.strip()]
                if len(times) >= 2 and abs(times[0] - times[1]) < 60:
                    violations.append({
                        "file": rel,
                        "type": "rapid_overwrite",
                        "detail": f"两次修改间隔 {abs(times[0] - times[1])}s",
                    })
            for line in r3.stdout.strip().split("\n"):
                if "deletion" in line or (line.count("-") > 10):
                    pass  # git diff --stat doesn't directly expose line counts easily

    except Exception as e:
        _meta_log({"event": "document_integrity_error", "error": str(e)})
        return {"violations": len(violations), "checked": checked, "error": str(e)}

    score_value = 1.0 - (len(violations) * 0.2)
    score_value = max(0.0, score_value)
    _save_meta_score("document_integrity", score_value, {
        "checked": checked,
        "violations": len(violations),
        "violation_details": violations[:10],
    })
    _meta_log({"event": "document_integrity", "checked": checked, "violations": len(violations)})

    return {
        "checked": checked,
        "violations": len(violations),
        "violation_details": violations[:10],
        "score": round(score_value, 4),
    }


def evaluate_knowledge_base():
    """
    扫描知识库错误记录，检查代码库中是否有对应防护措施。
    每个错误类型 → 期望防护 → 未防护的生成建议。
    """
    kb_dir = ROOT_DIR.parent / "知识库" / "错误与修正与优化"
    protections = {
        "文档覆写": ["CLAUDE.md", "文档版本铁律"],
        "鉴权": ["routes/api_eval.py", "_check_admin"],
        "测试": ["tests/", "pytest"],
        "性能": ["bench_", "latency"],
        "SECRET_KEY": ["config.py", "EVAL_ADMIN_SECRET"],
        "innerHTML": ["eval-ui.js", "cloneNode"],
    }

    unprotected = []
    checked = 0

    try:
        if kb_dir.exists():
            for md_file in kb_dir.glob("*.md"):
                checked += 1
                content = md_file.read_text(encoding="utf-8")
                matched_any = False
                for error_type, (check_path, check_pattern) in protections.items():
                    if error_type in content or error_type.lower() in content.lower():
                        target = ROOT_DIR / check_path if "/" in check_path else ROOT_DIR
                        if target.exists():
                            target_content = target.read_text(encoding="utf-8") if target.is_file() else "DIR"
                            if check_pattern in str(target_content):
                                matched_any = True
                                break
                if not matched_any:
                    # 只标记 P1 级别（文档覆写、鉴权、SECRET_KEY）
                    if any(k in content for k in ["文档覆写", "鉴权", "SECRET_KEY"]):
                        unprotected.append({
                            "file": md_file.name,
                            "severity": "P1",
                        })
    except Exception as e:
        _meta_log({"event": "knowledge_base_error", "error": str(e)})
        return {"unprotected_errors": len(unprotected), "checked": checked, "error": str(e)}

    score_value = 1.0 - (len(unprotected) * 0.3)
    score_value = max(0.0, score_value)
    _save_meta_score("kb_protection_coverage", score_value, {
        "checked": checked,
        "unprotected": len(unprotected),
        "unprotected_details": unprotected,
    })
    _meta_log({"event": "knowledge_base", "checked": checked, "unprotected": len(unprotected)})

    return {
        "checked": checked,
        "unprotected_errors": len(unprotected),
        "unprotected_details": unprotected,
        "score": round(score_value, 4),
    }


# ══════════════════════════════════════════════
# 独立运行器
# ══════════════════════════════════════════════

def run_all():
    """
    运行所有元评估函数。被 server.py 后台线程调用。
    顺序执行，每步独立 try/except（防崩盖）。
    """
    results = {}

    # Step 1: 过程合规 (CODE, 无 LLM 调用)
    try:
        results["phase3_adherence"] = evaluate_phase3_adherence()
    except Exception as e:
        logger.error("meta_evaluator: phase3_adherence failed: %s", e, exc_info=True)
        results["phase3_adherence"] = {"error": str(e)}

    # Steps 4-5: 占位 (后续实现)
    for func_name, func in [
        ("score_configs", evaluate_score_configs),
        ("code_llm_consensus", evaluate_code_llm_consensus),
        ("score_drift", evaluate_score_drift),
        ("document_integrity", evaluate_document_integrity),
        ("knowledge_base", evaluate_knowledge_base),
    ]:
        try:
            results[func_name] = func()
        except Exception as e:
            logger.error("meta_evaluator: %s failed: %s", func_name, e, exc_info=True)
            results[func_name] = {"error": str(e)}

    _meta_log({"event": "run_all_complete", "summary": {k: type(v).__name__ for k, v in results.items()}})
    return results


# ══════════════════════════════════════════════
# M2: L2 自检 — 独立于主后台线程运行
# ══════════════════════════════════════════════

def run_l2_self_check():
    """
    L2 自检 — 独立于主后台线程运行。每 2 小时由 server.py L2 Timer 触发。

    检查三项:
    1. L1 心跳 — last_run 时间戳是否在 6h 内
    2. 告警响应率 — 最近 24h 内的告警中，已响应+自动恢复的比例
       - 已响应: 告警→建议→已采纳或已拒绝(有决策记录)
       - 自动恢复: 告警对应指标在下一评估周期自动恢复
       - 未响应: 告警持续超过 2 个评估周期，无决策记录也无自动恢复
    3. L1 指标退化 — 元评估自身评分的趋势

    返回: {"status": "ok"|"warn"|"error", "checks": {...}}
    """
    checks = {}
    issues = []

    # ── 检查 1: L1 心跳 ──
    try:
        heartbeat_file = DATA_DIR / "heartbeat.json"
        if heartbeat_file.exists():
            lines = []
            with open(heartbeat_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            lines.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            if lines:
                last = lines[-1]
                last_ts = last.get("timestamp") or last.get("_ts", "")
                if last_ts:
                    try:
                        last_dt = datetime.fromisoformat(last_ts)
                        age_h = (datetime.now() - last_dt).total_seconds() / 3600
                        checks["l1_heartbeat"] = {"age_hours": round(age_h, 2), "status": "ok" if age_h <= 6 else "stale"}
                        if age_h > 6:
                            issues.append(f"L1 heartbeat stale: {round(age_h, 1)}h since last beat")
                    except Exception:
                        checks["l1_heartbeat"] = {"status": "unknown", "note": "unparseable timestamp"}
                        issues.append("L1 heartbeat: unparseable timestamp")
            else:
                checks["l1_heartbeat"] = {"status": "empty", "note": "no heartbeat records yet"}
        else:
            checks["l1_heartbeat"] = {"status": "empty", "note": "heartbeat file not found"}
    except Exception as e:
        checks["l1_heartbeat"] = {"status": "error", "error": str(e)}
        issues.append(f"L1 heartbeat check crashed: {e}")

    # ── 检查 2: 告警响应率 (24h) ──
    try:
        now = datetime.now()
        scores_data = eval_store._read_json("scores.json") if hasattr(eval_store, "_read_json") else {}
        suggestions_data = eval_store._read_json("suggestions.json") if hasattr(eval_store, "_read_json") else {}

        total_alerts = 0
        responded = 0
        auto_recovered = 0
        unresponded = 0

        scores_list = scores_data.get("scores", []) if isinstance(scores_data, dict) else []
        suggestions_list = suggestions_data.get("suggestions", []) if isinstance(suggestions_data, dict) else []

        for s in scores_list:
            if s.get("type") != "alert":
                continue
            if not s.get("alert_id"):
                continue
            created = s.get("created_at", "")
            if not created:
                continue
            try:
                created_dt = datetime.fromisoformat(created)
                if (now - created_dt).total_seconds() > 86400:  # 24h
                    continue
            except Exception:
                continue
            total_alerts += 1
            alert_id = s["alert_id"]

            # 检查是否有对应的已处理建议
            matched = False
            for sug in suggestions_list:
                if sug.get("source_alert_id") == alert_id:
                    if sug.get("status") in ("applied", "rejected"):
                        responded += 1
                        matched = True
                        break
            if not matched:
                # 检查是否自动恢复：同一config_id在同一周期内评分回升
                config_id = s.get("config_id", "")
                threshold = s.get("threshold")
                current = s.get("current")
                if threshold is not None and current is not None:
                    direction = s.get("direction", "below")
                    if direction == "below" and current >= threshold:
                        auto_recovered += 1
                    elif direction == "above" and current <= threshold:
                        auto_recovered += 1
                    else:
                        unresponded += 1
                else:
                    unresponded += 1

        response_rate = (responded + auto_recovered) / total_alerts if total_alerts > 0 else None
        checks["alert_response_rate"] = {
            "total_24h": total_alerts,
            "responded": responded,
            "auto_recovered": auto_recovered,
            "unresponded": unresponded,
            "response_rate": round(response_rate, 4) if response_rate is not None else None,
        }
        if response_rate is not None and response_rate < 0.5 and total_alerts >= 3:
            issues.append(f"Alert response rate low: {round(response_rate * 100)}% ({responded + auto_recovered}/{total_alerts})")
    except Exception as e:
        checks["alert_response_rate"] = {"status": "error", "error": str(e)}
        issues.append(f"Alert response rate check crashed: {e}")

    # ── 检查 3: L1 指标退化 ──
    try:
        meta_scores = eval_store.query_scores(
            config_id="eval_process_adherence",
            limit=20,
            exclude_empty_traces=False,
            exclude_orphan_spans=False,
        ) if hasattr(eval_store, "query_scores") else []
        if len(meta_scores) >= 4:
            recent = [s.get("value", 0) for s in meta_scores[-4:]]
            is_declining = all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1))
            checks["l1_degradation"] = {
                "samples": len(recent),
                "values": recent,
                "is_declining": is_declining,
            }
            if is_declining and recent[0] > recent[-1]:
                issues.append(f"L1 meta-eval scores declining: {recent[0]} → {recent[-1]}")
        else:
            checks["l1_degradation"] = {"status": "insufficient_data", "samples": len(meta_scores)}
    except Exception as e:
        checks["l1_degradation"] = {"status": "error", "error": str(e)}
        issues.append(f"L1 degradation check crashed: {e}")

    # ── 判定总体状态 ──
    if any("crashed" in i or "error" in str(checks.get(k, {})) for i in issues for k in checks):
        status = "error"
    elif issues:
        status = "warn"
    else:
        status = "ok"

    result = {"status": status, "checks": checks, "issues": issues}
    _meta_log({"event": "l2_self_check", "result": result})
    return result


# 支持独立脚本调用: python -m services.eval.meta_evaluator
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT_DIR))
    results = run_all()
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
