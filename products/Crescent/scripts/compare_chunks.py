"""
Chunk Size 对比实验脚本
自动化: 为每种 chunk_size 重建 ChromaDB → 运行 eval_rag → 汇总 → 输出对比表

用法:
  python scripts/compare_chunks.py                    # 默认 300,500,800,1000
  python scripts/compare_chunks.py --sizes 300,500    # 自定义
  python scripts/compare_chunks.py --output results/   # 输出目录
  python scripts/compare_chunks.py --dry-run          # 只估算，不实际构建
"""
import sys
import json
import time
import shutil
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from services.llm_service import get_embeddings


def run_experiment(chunk_size, chunk_overlap=None, test_set=None):
    """运行一次实验: 构建 DB + 评测。返回 {chunk_size, summary, details, elapsed_s}"""
    if chunk_overlap is None:
        chunk_overlap = max(10, chunk_size // 10)

    if test_set is None:
        test_set = load_test_set()

    tmp_dir = Path(tempfile.mkdtemp(prefix=f"chroma_cs{chunk_size}_"))
    t0 = time.time()

    try:
        # 1. Build ChromaDB to temp dir
        print(f"\n  [build] chunk_size={chunk_size}, overlap={chunk_overlap}")
        from scripts.build_vector_db import load_documents, chunk_documents, build_chroma
        docs = load_documents(config.KNOWLEDGE_SOURCES)
        print(f"    loaded {len(docs)} docs")
        chunks = chunk_documents(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        print(f"    produced {len(chunks)} chunks")

        collection = build_chroma(chunks, collection_name="eval_compare", persist_dir=tmp_dir)
        num_chunks = collection.count() if collection else len(chunks)

        # 2. Temporarily override config to point to temp DB for eval
        original_path = config.CHROMA_PATH
        config.CHROMA_PATH = str(tmp_dir)

        try:
            # Force re-import of chromadb client in rag_service (it's lazily loaded)
            from services.rag_service import invalidate_bm25_cache
            invalidate_bm25_cache()

            from scripts.eval_rag import evaluate
            result = evaluate(test_set, k=5)
        finally:
            config.CHROMA_PATH = original_path
            invalidate_bm25_cache()

        elapsed = time.time() - t0

        return {
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "num_chunks": num_chunks,
            "num_docs": len(docs),
            "elapsed_s": round(elapsed, 1),
            "summary": result["summary"],
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def load_test_set():
    path = Path(__file__).parent.parent / "data" / "eval" / "rag_test_set.json"
    return json.loads(path.read_text(encoding="utf-8"))


def compare_sizes(sizes, output_dir=None):
    """对比所有 chunk_size，输出汇总表。"""
    out_dir = Path(output_dir) if output_dir else Path(__file__).parent.parent / "data" / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)

    test_set = load_test_set()
    results = []

    print(f"\n{'='*70}")
    print(f"  Chunk Size 对比实验: {len(sizes)} 种参数 (overlap=size//10)")
    print(f"  评测集: {len(test_set)} 条查询")
    print(f"{'='*70}")

    total_start = time.time()
    for i, cs in enumerate(sizes, 1):
        print(f"\n--- 实验 {i}/{len(sizes)}: chunk_size={cs} ---")
        result = run_experiment(cs, test_set=test_set)
        results.append(result)
        print(f"  完成: Hit Rate@5={result['summary']['hit_rate@5']:.2%}, "
              f"MRR={result['summary']['mrr']:.4f}, "
              f"耗时 {result['elapsed_s']:.0f}s")

    total_elapsed = time.time() - total_start

    # 输出比较表
    _print_comparison(results)
    _print_recommendation(results)

    # 保存结果
    out_file = out_dir / f"chunk_comparison_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out_data = {
        "experiment": "chunk_size_comparison",
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_elapsed_s": round(total_elapsed, 1),
        "test_queries": len(test_set),
        "overlap_ratio": "chunk_size // 10",
        "results": results,
    }
    out_file.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已保存: {out_file}")

    # 更新 config 建议
    best = _best_result(results)
    print(f"\n建议: 将 config.py 的 CHUNK_SIZE 设为 {best['chunk_size']} "
          f"(Hit Rate@5={best['summary']['hit_rate@5']:.2%}, MRR={best['summary']['mrr']:.4f})")

    return results


def _print_comparison(results):
    """输出对比表格"""
    print(f"\n{'='*80}")
    print("  Chunk Size 对比表")
    print(f"{'='*80}")
    header = f"{'Chunk Size':<12} {'Overlap':<9} {'Chunks':<8} {'Hit@5':<10} {'MRR':<10} {'Rel@5':<8} {'Latency':<10}"
    print(header)
    print("-" * len(header))
    for r in results:
        s = r["summary"]
        print(f"{r['chunk_size']:<12} {r['chunk_overlap']:<9} {r['num_chunks']:<8} "
              f"{s['hit_rate@5']:<10.2%} {s['mrr']:<10.4f} {s['avg_relevant@5']:<8.2f} "
              f"{s['avg_latency_ms']:<8.0f}ms")

    # Markdown 表格
    print(f"\n| Chunk Size | Overlap | Chunks | Hit Rate@5 | MRR    | Rel@5 | Latency |")
    print(f"|-----------|---------|--------|------------|--------|-------|---------|")
    for r in results:
        s = r["summary"]
        print(f"| {r['chunk_size']:<9} | {r['chunk_overlap']:<7} | {r['num_chunks']:<6} | "
              f"{s['hit_rate@5']:<8.2%} | {s['mrr']:<6.4f} | {s['avg_relevant@5']:<5.2f} | "
              f"{s['avg_latency_ms']:<7.0f}ms |")


def _best_result(results):
    """选最佳参数: 优先 Hit Rate@5，平局按 MRR，再平局按 latency"""
    return max(results, key=lambda r: (
        r["summary"]["hit_rate@5"],
        r["summary"]["mrr"],
        -r["summary"]["avg_latency_ms"],
    ))


def _print_recommendation(results):
    best = _best_result(results)
    s = best["summary"]
    print(f"\n推荐参数: chunk_size={best['chunk_size']}, overlap={best['chunk_overlap']}")
    print(f"  Hit Rate@5: {s['hit_rate@5']:.2%}  MRR: {s['mrr']:.4f}  "
          f"Latency: {s['avg_latency_ms']:.0f}ms  Chunks: {best['num_chunks']}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Chunk Size 对比实验")
    parser.add_argument("--sizes", type=str, default="300,500,800,1000",
                        help="逗号分隔的 chunk sizes (default: 300,500,800,1000)")
    parser.add_argument("--output", type=str, default=None,
                        help="输出目录 (default: data/eval/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="只估算，不实际构建 ChromaDB")
    args = parser.parse_args()

    sizes = [int(s.strip()) for s in args.sizes.split(",")]

    if args.dry_run:
        test_set = load_test_set()
        print(f"Dry-run: 将对 {len(sizes)} 种 chunk_size 参数运行评测")
        print(f"  每种需重建 ChromaDB (读取所有文档 + re-embed)")
        print(f"  评测集: {len(test_set)} 条查询")
        print(f"  Embedding 模型: {config.EMBEDDING_MODEL}")
        print(f"  预计总耗时: ~{len(sizes) * 10}-{len(sizes) * 20} 分钟")
        return

    compare_sizes(sizes, args.output)


if __name__ == "__main__":
    main()
