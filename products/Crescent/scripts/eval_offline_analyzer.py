"""离线评估分析器 — 扫描 eval 数据，检测回归趋势、知识缺口，输出可执行建议。

运行方式:
    python scripts/eval_offline_analyzer.py              # 输出到 stdout
    python scripts/eval_offline_analyzer.py --json       # 输出 JSON
    python scripts/eval_offline_analyzer.py --cron       # cron 模式，写入 data/eval/offline_suggestions.json

说明: 本脚本仅读取已有 eval 数据，不调用任何外部 API，可在无网络环境下安全运行。
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path(__file__).parent.parent / "data" / "eval"
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(Path(__file__).parent.parent))

RAG_FILES = {
    "baseline": DATA_DIR / "rag_baseline.json",
    "v2": DATA_DIR / "rag_v2.json",
    "crudrag": DATA_DIR / "crudrag_results.json",
}


def load_json(path):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def analyze_rag_regression():
    """对比 baseline 与 v2 的 RAG 指标，检测退化信号。"""
    baseline = load_json(RAG_FILES["baseline"])
    v2 = load_json(RAG_FILES["v2"])

    findings = []
    if not baseline or not v2:
        return {"status": "insufficient_data", "findings": findings}

    bs = baseline["summary"]
    vs = v2["summary"]

    # HR 对比 (不同 k 也要标注)
    hr_key = "hit_rate@5" if "hit_rate@5" in bs else "hit_rate@3"
    hr_delta = vs.get(hr_key, 0) - bs.get(hr_key, 0) if hr_key in vs else None
    if hr_delta is not None and hr_delta < -0.03:
        findings.append({
            "severity": "warning",
            "metric": "hit_rate",
            "delta": round(hr_delta, 4),
            "message": f"RAG Hit Rate 退化 {hr_delta:+.1%} (baseline={bs.get(hr_key):.1%} → v2={vs.get(hr_key):.1%})",
        })

    mrr_delta = vs.get("mrr", 0) - bs.get("mrr", 0)
    if mrr_delta < -0.02:
        findings.append({
            "severity": "warning",
            "metric": "mrr",
            "delta": round(mrr_delta, 4),
            "message": f"RAG MRR 退化 {mrr_delta:+.3f} (baseline={bs['mrr']:.4f} → v2={vs['mrr']:.4f})",
        })

    # 延迟对比
    latency_delta = vs.get("avg_latency_ms", 0) - bs.get("avg_latency_ms", 0)
    if latency_delta > 5000:
        findings.append({
            "severity": "warning" if latency_delta > 10000 else "info",
            "metric": "latency",
            "delta_ms": latency_delta,
            "message": f"RAG 延迟增加 {latency_delta:+.0f}ms (baseline={bs['avg_latency_ms']:.0f}ms → v2={vs['avg_latency_ms']:.0f}ms)",
        })

    return {
        "status": "ok",
        "baseline_summary": bs,
        "v2_summary": vs,
        "findings": findings,
    }


def analyze_domain_weakness():
    """识别检索表现最差的 5 个知识领域 (按 MRR)。"""
    baseline = load_json(RAG_FILES["baseline"])
    if not baseline or "details" not in baseline:
        return {"status": "no_detail_data"}

    from collections import defaultdict
    domain_stats = defaultdict(lambda: {"rr_sum": 0.0, "count": 0, "hits": 0, "misses": []})

    for d in baseline["details"]:
        domain = d["domain"]
        ds = domain_stats[domain]
        ds["rr_sum"] += d["rr"]
        ds["count"] += 1
        if d["hit"]:
            ds["hits"] += 1
        else:
            ds["misses"].append(d["question"])

    ranked = []
    for domain, ds in domain_stats.items():
        ds["mrr"] = ds["rr_sum"] / ds["count"]
        ds["hit_rate"] = ds["hits"] / ds["count"]
        ranked.append((domain, dict(ds)))

    ranked.sort(key=lambda x: x[1]["mrr"])

    weak_domains = []
    for domain, ds in ranked[:5]:
        if ds["mrr"] < 0.5 or ds["hit_rate"] < 0.6:
            weak_domains.append({
                "domain": domain,
                "mrr": round(ds["mrr"], 4),
                "hit_rate": round(ds["hit_rate"], 4),
                "sample_count": ds["count"],
                "miss_samples": ds["misses"][:3],
            })

    return {
        "status": "ok",
        "all_domains": [{"domain": d, "mrr": round(s["mrr"], 4), "hit_rate": round(s["hit_rate"], 4)} for d, s in ranked],
        "weak_domains": weak_domains,
    }


def analyze_data_gaps():
    """检查 eval 数据完整性。"""
    gaps = []

    for label, path in RAG_FILES.items():
        if not path.exists():
            gaps.append({"severity": "warning", "file": str(path), "message": f"缺失 {label} RAG 评估数据"})

    # 检查是否有 scores.json / heartbeat.json (doc 中提到但实际可能不存在)
    for fname in ["scores.json", "heartbeat.json", "golden_dataset.json"]:
        if not (DATA_DIR / fname).exists():
            gaps.append({"severity": "info", "file": str(DATA_DIR / fname), "message": f"eval 元数据文件 {fname} 尚未生成"})

    return gaps


def generate_suggestions(regression_result, domain_result, gaps):
    """根据分析结果生成可执行建议列表。"""
    suggestions = []

    # RAG 回归建议
    for f in regression_result.get("findings", []):
        if f.get("metric") == "hit_rate" and f.get("delta", 0) < 0:
            suggestions.append({
                "priority": 2,
                "category": "rag_retrieval",
                "action": "检查 BM25 权重配置是否合理，对比纯向量 vs 混合检索的 per-query 差异",
                "trigger": f["message"],
            })
        if f.get("metric") == "latency" and f.get("delta_ms", 0) > 10000:
            suggestions.append({
                "priority": 1,
                "category": "rag_performance",
                "action": "BM25 全量加载导致延迟飙升，考虑缓存预热或限制 BM25 文档数",
                "trigger": f["message"],
            })

    # 领域弱点建议
    for wd in domain_result.get("weak_domains", []):
        suggestions.append({
            "priority": 2,
            "category": "knowledge_gap",
            "action": f"补充 {wd['domain']} 领域的知识库文档 (当前 HR={wd['hit_rate']:.1%}, MRR={wd['mrr']:.3f})",
            "trigger": f"miss 样例: {wd['miss_samples'][:2]}",
        })

    # 数据缺口建议
    for g in gaps:
        if g["severity"] == "warning":
            suggestions.append({
                "priority": 3,
                "category": "eval_completeness",
                "action": f"运行对应评测脚本生成 {Path(g['file']).name}",
                "trigger": g["message"],
            })

    suggestions.sort(key=lambda s: s["priority"])
    return suggestions


def main():
    json_mode = "--json" in sys.argv
    cron_mode = "--cron" in sys.argv

    regression = analyze_rag_regression()
    domain = analyze_domain_weakness()
    gaps = analyze_data_gaps()
    suggestions = generate_suggestions(regression, domain, gaps)

    output = {
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "rag_regression": regression,
        "domain_weakness": domain,
        "data_gaps": gaps,
        "suggestions": suggestions,
        "summary": f"共 {len(suggestions)} 条建议 (P1={sum(1 for s in suggestions if s['priority']==1)}, P2={sum(1 for s in suggestions if s['priority']==2)}, P3={sum(1 for s in suggestions if s['priority']==3)})",
    }

    if cron_mode:
        output["_mode"] = "cron"
        output_path = DATA_DIR / "offline_suggestions.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"→ {output_path} ({len(suggestions)} suggestions)")
        return

    if json_mode:
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # 人类可读输出
    print("=" * 60)
    print("  Eval Offline Analyzer")
    print("=" * 60)

    print(f"\n-- RAG regression ({regression['status']}) --")
    for f in regression.get("findings", []):
        marker = "[WARN]" if f["severity"] == "warning" else "[INFO]"
        print(f"  {marker} {f['message']}")
    if not regression.get("findings"):
        print("  [OK] No significant regression")

    print(f"\n-- Domain weakness ({domain['status']}) --")
    for wd in domain.get("weak_domains", []):
        print(f"  [GAP] {wd['domain']}: MRR={wd['mrr']:.3f}, HR={wd['hit_rate']:.1%} (n={wd['sample_count']})")
        for m in wd.get("miss_samples", [])[:2]:
            print(f"         miss: {m[:60]}...")
    if not domain.get("weak_domains"):
        print("  [OK] All domains normal")

    print(f"\n-- Data gaps ({len(gaps)} items) --")
    for g in gaps:
        marker = "[WARN]" if g["severity"] == "warning" else "[INFO]"
        print(f"  {marker} {g['message']}")

    print(f"\n-- Suggestions ({len(suggestions)} items) --")
    for s in suggestions:
        print(f"  [P{s['priority']}] [{s['category']}] {s['action']}")
        print(f"       trigger: {s['trigger']}")


if __name__ == "__main__":
    main()
