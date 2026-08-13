"""
RAG 检索评测脚本 — 可配置评估管道
支持: 搜索配置对比、自定义测试集、结果版本化

用法:
  python scripts/eval_rag.py                        # 默认配置评测
  python scripts/eval_rag.py --config hybrid         # 指定配置
  python scripts/eval_rag.py --config compare        # 全配置对比
  python scripts/eval_rag.py --test-set my_test.json # 自定义测试集
  python scripts/eval_rag.py --k 10                  # 调整 top-k
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.rag_service import search
import chromadb
from config import CHROMA_PATH, CHROMA_COLLECTION

# ── 搜索配置预设 ──
SEARCH_CONFIGS = {
    "hybrid": {
        "label": "向量+BM25混合检索",
        "use_hybrid": True,
        "use_reranker": False,
    },
    "hybrid+reranker": {
        "label": "混合检索 + Reranker精排",
        "use_hybrid": True,
        "use_reranker": True,
    },
    "vector-only": {
        "label": "纯向量检索",
        "use_hybrid": False,
        "use_reranker": False,
    },
    "bm25-only": {
        "label": "纯BM25检索",
        "use_hybrid": False,
        "use_reranker": False,
        "vector_mode": "disabled",
    },
}

DEFAULT_TEST_SET = Path(__file__).parent.parent / "data" / "eval" / "rag_test_set.json"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "eval"


def load_test_set(path=None):
    path = Path(path) if path else DEFAULT_TEST_SET
    if not path.exists():
        raise FileNotFoundError(f"测试集不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def is_relevant(chunk, item):
    source = chunk.get("source", "")
    title = chunk.get("title", "")
    text = chunk.get("text", "")
    combined = f"{source} {title} {text}".lower()

    for rel_src in item.get("relevant_sources", []):
        if rel_src.lower() in source.lower():
            return True

    keywords = item.get("relevant_keywords", [])
    if keywords:
        hits = sum(1 for kw in keywords if kw.lower() in combined)
        if hits >= 2:
            return True
    return False


def run_eval(test_set, k=5, config_name="hybrid", dynamic_ratio=0.85):
    """单次评测运行。返回 {"summary": ..., "details": ...}"""
    cfg = SEARCH_CONFIGS.get(config_name, SEARCH_CONFIGS["hybrid"])
    use_hybrid = cfg.get("use_hybrid", True)
    use_reranker = cfg.get("use_reranker", False)

    # bm25-only: 禁用向量路径，让 search() 走降级
    if cfg.get("vector_mode") == "disabled":
        dynamic_ratio = 0.0
        use_hybrid = False

    total_queries = len(test_set)
    hit_count = 0
    reciprocal_ranks = []
    recall_scores = []
    total_time = 0
    details = []

    label = cfg["label"]
    print(f"\n{'='*60}")
    print(f"  评测配置: {label}  (k={k})")
    print(f"  use_hybrid={use_hybrid}, use_reranker={use_reranker}, ratio={dynamic_ratio}")
    print(f"{'='*60}\n")

    for i, item in enumerate(test_set):
        question = item["question"]
        domain = item.get("domain", "?")

        t0 = time.time()
        try:
            chunks = search(question, k=k, dynamic_ratio=dynamic_ratio,
                          use_hybrid=use_hybrid, use_reranker=use_reranker)
        except Exception as e:
            print(f"  [{i+1:2d}] ERR: {e}")
            continue
        elapsed = time.time() - t0
        total_time += elapsed

        hit_rank = None
        relevant_found = 0
        for rank, chunk in enumerate(chunks, 1):
            if is_relevant(chunk, item):
                relevant_found += 1
                if hit_rank is None:
                    hit_rank = rank

        hit = hit_rank is not None
        rr = 1.0 / hit_rank if hit_rank else 0.0
        hit_count += 1 if hit else 0
        reciprocal_ranks.append(rr)
        recall_scores.append(relevant_found)

        status = "HIT" if hit else "MISS"
        rank_str = f"rank={hit_rank}" if hit_rank else "-"
        top3 = [c.get("source", "?")[:30] for c in chunks[:3]]
        print(f"  [{i+1:2d}] {status} {rank_str} | {domain:15s} | top3: {top3}")

        details.append({
            "id": item["id"],
            "question": question[:80],
            "domain": domain,
            "hit": hit,
            "hit_rank": hit_rank,
            "rr": round(rr, 4),
            "relevant_found": relevant_found,
            "top5_sources": [c.get("source", "?")[:40] for c in chunks[:5]],
            "top5_similarities": [c.get("similarity", 0) for c in chunks[:5]],
            "elapsed_ms": round(elapsed * 1000),
        })

    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0
    hit_rate = hit_count / total_queries if total_queries else 0
    avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0
    avg_time = total_time / total_queries * 1000 if total_queries else 0

    summary = {
        "config": config_name,
        "config_label": label,
        "k": k,
        f"hit_rate@{k}": round(hit_rate, 4),
        "mrr": round(mrr, 4),
        f"avg_relevant@{k}": round(avg_recall, 2),
        "avg_latency_ms": round(avg_time, 1),
        "hit_count": hit_count,
        "total_queries": total_queries,
        "timestamp": datetime.now().isoformat(),
    }

    print(f"\n  Hit Rate@{k}:   {hit_rate:.2%} ({hit_count}/{total_queries})")
    print(f"  MRR:            {mrr:.4f}")
    print(f"  Avg Relevant@{k}: {avg_recall:.2f}")
    print(f"  Avg Latency:    {avg_time:.0f}ms")

    return {"summary": summary, "details": details, "config_name": config_name}


def auto_version_path():
    """自动递增版本号，返回 data/eval/rag_v{N}.json"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(OUTPUT_DIR.glob("rag_v*.json"))
    version = len(existing) + 1
    return OUTPUT_DIR / f"rag_v{version}.json"


def compare_configs(test_set, k=5, output_file=None):
    """运行所有搜索配置预设并输出对比表"""
    results = {}
    for name in SEARCH_CONFIGS:
        print(f"\n{'─'*60}")
        print(f"  运行配置: {name}")
        print(f"{'─'*60}")
        result = run_eval(test_set, k=k, config_name=name)
        results[name] = result

    # 输出对比表
    print(f"\n{'='*70}")
    print(f"  配置对比汇总  (k={k})")
    print(f"{'='*70}")
    header = f"  {'配置':<25s} {'Hit Rate':>8s} {'MRR':>8s} {'Avg Rel':>8s} {'Latency':>8s}"
    print(header)
    print(f"  {'─'*25} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")

    best_hit = ("", 0)
    best_mrr = ("", 0)
    for name, r in results.items():
        s = r["summary"]
        hr = s.get(f"hit_rate@{k}", 0)
        mrr = s.get("mrr", 0)
        ar = s.get(f"avg_relevant@{k}", 0)
        lat = s.get("avg_latency_ms", 0)
        print(f"  {s['config_label']:<25s} {hr:>7.2%} {mrr:>8.4f} {ar:>8.2f} {lat:>7.0f}ms")
        if hr > best_hit[1]:
            best_hit = (name, hr)
        if mrr > best_mrr[1]:
            best_mrr = (name, mrr)

    print(f"\n  最佳 Hit Rate: {best_hit[0]} ({best_hit[1]:.2%})")
    print(f"  最佳 MRR:      {best_mrr[0]} ({best_mrr[1]:.4f})")

    if output_file:
        out = OUTPUT_DIR / output_file if not Path(output_file).is_absolute() else Path(output_file)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {name: {"summary": r["summary"], "details": r["details"]} for name, r in results.items()}
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结果已写入: {out}")

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RAG 检索评测 — 可配置评估管道")
    parser.add_argument("--k", type=int, default=5, help="top-k (默认5)")
    parser.add_argument("--config", default="hybrid",
                       help=f"搜索配置: {', '.join(SEARCH_CONFIGS)} | compare (全对比)")
    parser.add_argument("--test-set", type=str, help="测试集路径 (默认 data/eval/rag_test_set.json)")
    parser.add_argument("--output", type=str, help="输出 JSON 文件路径 (不指定则自动版本化)")
    parser.add_argument("--ratio", type=float, default=0.85, help="动态阈值比例 (默认0.85)")
    args = parser.parse_args()

    test_set = load_test_set(args.test_set)

    if args.config == "compare":
        out = args.output or f"rag_comparison_v{len(sorted(OUTPUT_DIR.glob('rag_comparison*.json')))+1}.json"
        compare_configs(test_set, k=args.k, output_file=out)
        return

    if args.config not in SEARCH_CONFIGS:
        print(f"未知配置: {args.config}")
        print(f"可用: {', '.join(SEARCH_CONFIGS)}")
        return

    result = run_eval(test_set, k=args.k, config_name=args.config, dynamic_ratio=args.ratio)

    out = Path(args.output) if args.output else auto_version_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入: {out}")


if __name__ == "__main__":
    main()
