"""
eval_store — 评估数据存储层

管理:
  - traces.jsonl: Trace + Span 数据 (追加写)
  - scores.json: ScoreConfig + Score 评分数据
  - suggestions.json: Suggestion 建议数据
  - meta_results.json: MetaEvalResult 元评估结果

关键功能:
  - 孤儿Span查询/清理
  - 聚合查询 (默认排除空Trace+孤儿Span)
  - apply_suggestion() 子指标基线记录
  - _git_commits_touching_file() 冲突检测
"""
import json
import os
import time
import uuid
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime

try:
    import yaml
except ImportError:
    yaml = None

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "eval"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT_DIR = DATA_DIR / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_MAX_VERSIONS = 10


# ══════════════════════════════════════════════
# 底层读写
# ══════════════════════════════════════════════

def _read_jsonl(filename):
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return []
    results = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return results


def _read_json(filename):
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _snapshot_before_write(filename):
    """在覆写/追加前将当前文件复制到 snapshots/，保留最近10个版本"""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    snapshot_name = f"{filepath.stem}.{ts}{filepath.suffix}"
    snapshot_path = SNAPSHOT_DIR / snapshot_name
    import shutil
    shutil.copy2(filepath, snapshot_path)

    # 裁剪：每种文件只保留最近 SNAPSHOT_MAX_VERSIONS 个
    stem = filepath.stem
    suffix = filepath.suffix
    existing = sorted(
        [p for p in SNAPSHOT_DIR.iterdir() if p.name.startswith(stem + ".") and p.suffix == suffix],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in existing[SNAPSHOT_MAX_VERSIONS:]:
        old.unlink()


def _write_json(filename, data):
    _snapshot_before_write(filename)
    filepath = DATA_DIR / filename
    tmp = DATA_DIR / f".{filename}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, filepath)


def _append_jsonl(filename, data):
    _snapshot_before_write(filename)
    filepath = DATA_DIR / filename
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, default=str) + "\n")


# ══════════════════════════════════════════════
# Span 操作
# ══════════════════════════════════════════════

def append_span(span_data):
    """写入 Span（由 trace_logger._record_span 调用）"""
    _append_jsonl("traces.jsonl", span_data)


def list_orphan_spans(hours=24):
    """查询最近 N 小时内 orphan=True 的 Span"""
    rows = _read_jsonl("traces.jsonl")
    cutoff = time.time() - hours * 3600
    orphans = []
    for r in rows:
        if not r.get("orphan"):
            continue
        ts = r.get("timestamp", "")
        try:
            t = time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
        except (ValueError, TypeError):
            continue
        if t >= cutoff:
            orphans.append(r)
    return orphans


def find_trace_by_window(timestamp, window_seconds=5):
    """按时间窗口查找匹配的 Trace（±5秒）"""
    rows = _read_jsonl("traces.jsonl")
    try:
        span_ts = time.mktime(time.strptime(timestamp[:19], "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        return None

    for r in rows:
        if r.get("event") == "trace_end":
            continue
        if "trace_id" not in r or "span_id" in r:
            continue
        try:
            trace_ts = time.mktime(time.strptime(r["timestamp"][:19], "%Y-%m-%dT%H:%M:%S"))
        except (ValueError, TypeError):
            continue
        if abs(span_ts - trace_ts) <= window_seconds:
            return r
    return None


def attach_span_to_trace(span_id, trace_id):
    """将孤儿 Span 关联到 Trace（通过重写 traces.jsonl）"""
    rows = _read_jsonl("traces.jsonl")
    modified = False
    for r in rows:
        if r.get("span_id") == span_id:
            r["trace_id"] = trace_id
            r["orphan"] = False
            modified = True
    if modified:
        # 重写整个文件
        filepath = DATA_DIR / "traces.jsonl"
        with open(filepath, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def mark_orphan_confirmed(span_id):
    """标记 Span 为确认无法关联"""
    rows = _read_jsonl("traces.jsonl")
    modified = False
    for r in rows:
        if r.get("span_id") == span_id:
            r["orphan_confirmed"] = True
            modified = True
    if modified:
        filepath = DATA_DIR / "traces.jsonl"
        with open(filepath, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


# ══════════════════════════════════════════════
# Trace 查询
# ══════════════════════════════════════════════

def list_traces(limit=50, exclude_empty=True):
    """列出最近的 Trace。默认排除空Trace (span_count=0 且 duration<100ms)。"""
    rows = _read_jsonl("traces.jsonl")
    # 找到所有 trace_end 事件
    end_events = {}
    for r in rows:
        if r.get("event") == "trace_end":
            end_events[r["trace_id"]] = r

    traces = []
    seen = set()
    for r in reversed(rows):
        tid = r.get("trace_id")
        if not tid or tid in seen:
            continue
        if "span_id" in r:
            continue  # 跳过 Span 行
        if r.get("event") == "trace_end":
            continue  # 跳过 trace_end 行（从 trace_start 获取元数据）
        seen.add(tid)
        end = end_events.get(tid, {})
        span_count = end.get("span_count", 0)
        duration_ms = end.get("duration_ms", 0)

        if exclude_empty and span_count == 0 and duration_ms < 100:
            continue

        traces.append({
            "trace_id": tid,
            "name": r.get("name", ""),
            "kind": r.get("kind", ""),
            "timestamp": r.get("timestamp", ""),
            "duration_ms": duration_ms,
            "span_count": span_count,
            "error": end.get("error", False),
            "status_code": end.get("status_code"),
        })
        if len(traces) >= limit:
            break
    return traces


def get_trace(trace_id):
    """获取 Trace 详情，包含所有关联 Span"""
    rows = _read_jsonl("traces.jsonl")
    trace = None
    spans = []
    for r in rows:
        if r.get("trace_id") != trace_id:
            continue
        if "span_id" in r:
            spans.append(r)
        elif r.get("event") != "trace_end":
            trace = r
    if not trace:
        return None
    trace["spans"] = spans
    return trace


def _query_traces(*, min_duration_ms=None,
                  has_error=None, window_hours=None, limit=100):
    """
    统一 Trace 查询入口。封装 JSONL 存储细节，为 SQLite 迁移预留。
    trace_type 过滤由上层调用方负责（避免循环导入 _classify_trace_type）。
    所有上层模块应通过此函数查询 Trace，而非直接调用 list_traces 或 _read_jsonl。
    """
    traces = list_traces(limit=max(limit * 2, 500), exclude_empty=True)
    cutoff = time.time() - (window_hours or 24) * 3600 if window_hours else 0

    results = []
    for t in traces:
        # 时间窗口过滤 (基于 trace timestamp)
        ts_str = t.get("timestamp", "")
        try:
            ts = time.mktime(time.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S"))
            if window_hours and ts < cutoff:
                continue
        except (ValueError, TypeError):
            continue

        if min_duration_ms is not None and t.get("duration_ms", 0) < min_duration_ms:
            continue
        if has_error is not None and t.get("error", False) != has_error:
            continue

        results.append(t)
        if len(results) >= limit:
            break

    return results


# ══════════════════════════════════════════════
# ScoreConfig 操作
# ══════════════════════════════════════════════

DEFAULT_CONFIGS = {}

def list_score_configs():
    """列出所有 ScoreConfig"""
    data = _read_json("configs.json")
    return data.get("configs", [])


def get_score_config(config_id):
    for c in list_score_configs():
        if c.get("config_id") == config_id:
            return c
    return None


def save_score_config(config):
    data = _read_json("configs.json")
    configs = data.get("configs", [])
    for i, c in enumerate(configs):
        if c.get("config_id") == config.get("config_id"):
            configs[i] = config
            break
    else:
        configs.append(config)
    _write_json("configs.json", {"configs": configs, "updated_at": datetime.now().isoformat()})


# ══════════════════════════════════════════════
# Score 操作
# ══════════════════════════════════════════════

def save_score(score):
    """保存一条评分"""
    data = _read_json("scores.json")
    scores = data.get("scores", [])
    scores.append(score)
    _write_json("scores.json", {"scores": scores, "updated_at": datetime.now().isoformat()})


def query_scores(config_id=None, target_type=None, target_id=None,
                 exclude_empty_traces=True, exclude_orphan_spans=True,
                 limit=100):
    """查询评分，默认排除空Trace和孤儿Span"""
    data = _read_json("scores.json")
    scores = data.get("scores", [])

    # 构建需要排除的 trace_id 集合
    empty_trace_ids = set()
    orphan_trace_ids = set()
    if exclude_empty_traces or exclude_orphan_spans:
        rows = _read_jsonl("traces.jsonl")
        end_events = {}
        for r in rows:
            if r.get("event") == "trace_end":
                end_events[r["trace_id"]] = r
        for r in rows:
            tid = r.get("trace_id")
            if not tid:
                continue
            if r.get("orphan") and not r.get("orphan_confirmed"):
                orphan_trace_ids.add(tid)
        for tid, end in end_events.items():
            sc = end.get("span_count", 0)
            dur = end.get("duration_ms", 0)
            if sc == 0 and dur < 100:
                empty_trace_ids.add(tid)

    results = []
    for s in scores:
        # 评分可能关联到 trace_id（如果是在 Trace 上下文中记录的）
        tid = s.get("trace_id")
        if tid:
            if exclude_empty_traces and tid in empty_trace_ids:
                continue
            if exclude_orphan_spans and tid in orphan_trace_ids:
                continue
        if config_id and s.get("config_id") != config_id:
            continue
        if target_type and s.get("target_type") != target_type:
            continue
        if target_id and s.get("target_id") != target_id:
            continue
        results.append(s)
    return results[-limit:]


def get_latest_score(target_type, target_id, config_id):
    """获取最新一条评分"""
    scores = query_scores(
        config_id=config_id, target_type=target_type, target_id=target_id,
        exclude_empty_traces=False, exclude_orphan_spans=False,
    )
    return scores[-1] if scores else None


def get_latest_sub_score(target_type, target_id, config_id, sub_key=None):
    """
    获取子指标的最新评分。
    如果 sub_key 非空，从 Score.details 中提取子项分值。
    """
    score = get_latest_score(target_type, target_id, config_id)
    if not score:
        return None
    if sub_key and score.get("details"):
        sub_value = score["details"].get(sub_key)
        if sub_value is not None:
            return {"value": sub_value, "score_id": score["score_id"]}
    return {"value": score["value"], "score_id": score["score_id"]} if score else None


def get_score_trend(config_id, days=30):
    """获取评分趋势 (最近N天)，按时间升序排列"""
    scores = query_scores(config_id=config_id, limit=200)
    cutoff = time.time() - days * 86400
    trend = []
    for s in scores:
        ts = s.get("created_at", "")
        try:
            t = time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
        except (ValueError, TypeError):
            continue
        if t >= cutoff:
            trend.append({"date": ts[:10], "value": s["value"], "_ts": t})
    trend.sort(key=lambda p: p["_ts"])
    for p in trend:
        del p["_ts"]
    return trend


# ══════════════════════════════════════════════
# Suggestion 操作
# ══════════════════════════════════════════════

# 建议类别 → 追踪的具体子指标
#   来源: config_id 对应 eval_engine.DEFAULT_SCORE_CONFIGS 中的 config_id
#   sub_key 对应 Score.details 中的字段名 (CODE evaluator 自行填充)
#   review_agent 生成的 suggestion.category 与此处 key 匹配
SUGGESTION_CATEGORY_SUB_METRICS = {
    "security":       ["security_score.port_check", "security_score.ssrf_guard"],
    "performance":    ["agent_efficiency", "agent_efficiency.token_per_task"],
    "maintainability": ["code_health.complexity", "code_health.duplication"],
    "doc":            ["doc_coverage.docstring_ratio", "doc_coverage.architecture_refs"],
    "bug_risk":       ["agent_success_rate", "agent_tool_accuracy"],
    "architecture":   ["module_interop.import_health", "module_interop.circular_deps"],
}


def _generate_id():
    return uuid.uuid4().hex[:12]


# ══════════════════════════════════════════════
# M2: 追溯链完整性 — chain_hash
# ══════════════════════════════════════════════

def _compute_chain_hash(event_id="", metric_id="", alert_id="", suggestion_id=""):
    """计算六环追溯链的完整性哈希。SHA256，取前16字符。"""
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


def add_suggestion(suggestion):
    suggestion.setdefault("suggestion_id", _generate_id())
    suggestion.setdefault("status", "pending")
    suggestion.setdefault("created_at", datetime.now().isoformat())
    suggestion.setdefault("attribution_status", "pending")
    # M2: 计算追溯链完整性哈希
    suggestion["chain_hash"] = _compute_chain_hash(
        event_id=suggestion.get("source_event_id", ""),
        metric_id=suggestion.get("source_metric_id", ""),
        alert_id=suggestion.get("source_alert_id", ""),
        suggestion_id=suggestion.get("suggestion_id", ""),
    )
    data = _read_json("suggestions.json")
    items = data.get("suggestions", [])
    items.append(suggestion)
    _write_json("suggestions.json", {"suggestions": items, "updated_at": datetime.now().isoformat()})
    return suggestion


def list_suggestions(status=None, severity=None, limit=50):
    data = _read_json("suggestions.json")
    items = data.get("suggestions", [])
    if status:
        items = [s for s in items if s.get("status") == status]
    if severity:
        items = [s for s in items if s.get("severity") == severity]
    return items[-limit:]


def get_suggestion(suggestion_id):
    data = _read_json("suggestions.json")
    for s in data.get("suggestions", []):
        if s.get("suggestion_id") == suggestion_id:
            return s
    return None


def _audit_log(operation, target_id, admin_token=""):
    """高权限操作审计日志写入 audit.jsonl (SA 约束 4)。"""
    import hashlib
    try:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "admin_token_hash": "sha256:" + hashlib.sha256(admin_token.encode()).hexdigest()[:16] if admin_token else "none",
            "operation": operation,
            "target_id": target_id,
        }
        audit_file = DATA_DIR / "audit.jsonl"
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def apply_suggestion(suggestion_id, admin_token=None):
    """
    采纳建议 → 强制记录基线分数 + 当前 commit。
    纵深防御: admin_token 必须匹配 config.EVAL_ADMIN_SECRET。
    """
    import config
    if admin_token is None or admin_token != config.EVAL_ADMIN_SECRET:
        raise PermissionError("Forbidden — X-Admin-Token required")

    suggestion = get_suggestion(suggestion_id)
    if not suggestion:
        return None

    category = suggestion.get("category", "")
    sub_metrics = SUGGESTION_CATEGORY_SUB_METRICS.get(category, [])
    baseline_scores = {}

    for sub_metric in sub_metrics:
        parts = sub_metric.split(".", 1)
        config_id = parts[0]
        sub_key = parts[1] if len(parts) > 1 else None
        latest = get_latest_sub_score(
            target_type=suggestion.get("target_type", "module"),
            target_id=suggestion.get("target_id", ""),
            config_id=config_id,
            sub_key=sub_key,
        )
        if latest is not None:
            baseline_scores[sub_metric] = {
                "value": latest["value"],
                "score_id": latest["score_id"],
            }

    current_commit = _get_current_commit_sha()

    suggestion["status"] = "applied"
    suggestion["applied_at"] = datetime.now().isoformat()
    suggestion["baseline_scores"] = baseline_scores
    suggestion["applied_commit"] = current_commit
    suggestion["status_updated_at"] = datetime.now().isoformat()
    _save_suggestion(suggestion)
    _audit_log("apply_suggestion", suggestion_id, admin_token or "")
    return suggestion


def reject_suggestion(suggestion_id, admin_token=None):
    """拒绝建议。纵深防御: admin_token 必须匹配 config.EVAL_ADMIN_SECRET。"""
    import config
    if admin_token is None or admin_token != config.EVAL_ADMIN_SECRET:
        raise PermissionError("Forbidden — X-Admin-Token required")

    suggestion = get_suggestion(suggestion_id)
    if not suggestion:
        return None
    suggestion["status"] = "rejected"
    suggestion["status_updated_at"] = datetime.now().isoformat()
    _save_suggestion(suggestion)
    _audit_log("reject_suggestion", suggestion_id, admin_token or "")
    return suggestion


def rollback_suggestion(suggestion_id):
    suggestion = get_suggestion(suggestion_id)
    if not suggestion:
        return None
    suggestion["status"] = "rolled_back"
    suggestion["status_updated_at"] = datetime.now().isoformat()
    _save_suggestion(suggestion)
    return suggestion


def update_suggestion_effect(suggestion_id, effect_score_delta, attribution_status,
                              attribution_note=None, delta_details=None):
    suggestion = get_suggestion(suggestion_id)
    if not suggestion:
        return None
    suggestion["effect_score_delta"] = effect_score_delta
    suggestion["attribution_status"] = attribution_status
    if attribution_note:
        suggestion["attribution_note"] = attribution_note
    if delta_details:
        suggestion["delta_details"] = delta_details
    suggestion["status_updated_at"] = datetime.now().isoformat()
    _save_suggestion(suggestion)
    return suggestion


def _find_applied_unverified_suggestions(min_hours=24):
    """查找已采纳但效果未验证的建议"""
    data = _read_json("suggestions.json")
    results = []
    cutoff = time.time() - min_hours * 3600
    for s in data.get("suggestions", []):
        if s.get("status") != "applied":
            continue
        if s.get("attribution_status") not in (None, "pending"):
            continue
        applied_at = s.get("applied_at", "")
        try:
            t = time.mktime(time.strptime(applied_at[:19], "%Y-%m-%dT%H:%M:%S"))
        except (ValueError, TypeError):
            continue
        if t <= cutoff:
            results.append(s)
    return results


def _save_suggestion(suggestion):
    data = _read_json("suggestions.json")
    items = data.get("suggestions", [])
    for i, s in enumerate(items):
        if s.get("suggestion_id") == suggestion.get("suggestion_id"):
            items[i] = suggestion
            break
    _write_json("suggestions.json", {"suggestions": items, "updated_at": datetime.now().isoformat()})


# ══════════════════════════════════════════════
# MetaEvalResult 操作
# ══════════════════════════════════════════════

def save_meta_result(result):
    data = _read_json("meta_results.json")
    items = data.get("results", [])
    items.append(result)
    _write_json("meta_results.json", {"results": items, "updated_at": datetime.now().isoformat()})
    return result


def list_meta_results(limit=10):
    data = _read_json("meta_results.json")
    items = data.get("results", [])
    return items[-limit:]


# ══════════════════════════════════════════════
# Git 工具
# ══════════════════════════════════════════════

def _get_current_commit_sha():
    """获取当前 HEAD 的 commit SHA"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(Path(__file__).parent.parent.parent),
        )
        return result.stdout.strip()[:40] if result.returncode == 0 else None
    except Exception:
        return None


def _git_commits_touching_file(filepath, since_commit):
    """返回 since_commit 之后修改过 filepath 的所有 commit"""
    if not filepath or not since_commit:
        return []
    try:
        result = subprocess.run(
            ["git", "log", f"{since_commit}..HEAD", "--oneline", "--", filepath],
            capture_output=True, text=True, timeout=5,
            cwd=str(Path(__file__).parent.parent.parent),
        )
        commits = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split(" ", 1)
                sha = parts[0]
                msg = parts[1] if len(parts) > 1 else ""
                commits.append({"sha": sha, "message": msg})
        return commits
    except Exception:
        return []


# ══════════════════════════════════════════════
# M2: 决策面注册表 — 集中化 YAML 加载器
# ══════════════════════════════════════════════

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

    if yaml is None:
        return {}

    modules_dir = DATA_DIR / "modules"
    if not modules_dir.exists():
        _decisions_registry = {}
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


# ══════════════════════════════════════════════
# M5: 探测卡存储 (Probe Cards)
# ══════════════════════════════════════════════

def _probes_file():
    return DATA_DIR / "probes.json"


def _write_audit(entry):
    """写入 audit.jsonl。防崩盖，异常吞掉。"""
    try:
        audit_file = DATA_DIR / "audit.jsonl"
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _save_probe(probe):
    """保存探测卡。如果 probe_id 已存在则更新。"""
    try:
        probes = _load_probes()
        existing_idx = None
        for i, p in enumerate(probes):
            if p.get("probe_id") == probe.get("probe_id"):
                existing_idx = i
                break
        if existing_idx is not None:
            probes[existing_idx] = probe
        else:
            probes.append(probe)
        pf = _probes_file()
        with open(pf, "w", encoding="utf-8") as f:
            json.dump({"probes": probes, "updated_at": datetime.now().isoformat()},
                      f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _load_probes():
    """加载所有探测卡。防崩盖，异常返回空列表。"""
    try:
        pf = _probes_file()
        if not pf.exists():
            return []
        with open(pf, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("probes", [])
    except Exception:
        return []


def _resolve_probe(probe_id, resolution, reason=None):
    """记录探测卡结局。resolution: user_ignored | auto_expired | promoted_to_suggestion"""
    valid = {"user_ignored", "auto_expired", "promoted_to_suggestion"}
    if resolution not in valid:
        raise ValueError(f"Invalid resolution: {resolution}")
    try:
        probes = _load_probes()
        found = False
        for p in probes:
            if p.get("probe_id") == probe_id:
                p["resolution"] = resolution
                p["resolved_at"] = datetime.now().isoformat()
                if reason:
                    p["resolution_reason"] = reason
                found = True
                break
        if not found:
            return False
        pf = _probes_file()
        with open(pf, "w", encoding="utf-8") as f:
            json.dump({"probes": probes, "updated_at": datetime.now().isoformat()},
                      f, ensure_ascii=False, indent=2)
        _write_audit({
            "action": f"probe_{resolution}",
            "probe_id": probe_id,
            "reason": reason or None,
            "timestamp": int(time.time()),
        })
        return True
    except Exception:
        return False


def _cleanup_expired_probes():
    """自动过期超过30天的探测卡。返回过期数量。"""
    expired = 0
    try:
        now = datetime.now()
        probes = _load_probes()
        for p in probes:
            if p.get("resolution") is not None:
                continue
            created = p.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created)
                    if (now - dt).days >= 30:
                        _resolve_probe(p["probe_id"], "auto_expired")
                        expired += 1
                except Exception:
                    pass
    except Exception:
        pass
    return expired
