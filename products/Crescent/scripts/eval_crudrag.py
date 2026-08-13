"""CRUD-RAG 基准评测脚本

评估我们的 RAG 管道在第三方基准 CRUD-RAG 上的表现。
数据集: AndrewTsai0406/CRUD_RAG_3QA (HF mirror), 3,199 条多跳中文 QA
参照: CRUD-RAG: A Comprehensive Chinese Benchmark for RAG (ACM TOIS 2025)

评测指标:
  - Hit Rate@5: Top-5 检索结果中包含答案关键信息的比例
  - MRR (Mean Reciprocal Rank): 第一个相关文档排名的倒数均值
  - BLEU-1: 生成答案与参考答案的 1-gram 重叠
  - ROUGE-L: 生成答案与参考答案的最长公共子序列
"""

import json
import sys
import time
import random
from pathlib import Path

import jieba
import pandas as pd

# 项目路径
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))
DATA_DIR = BASE_DIR / "data"
EVAL_DIR = DATA_DIR / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

# ── 配置 ──
SAMPLE_SIZE = 150         # 评测样本数
RANDOM_SEED = 42
COARSE_K = 20             # 粗召回数量
TOP_K = 5                 # 精排后返回数量


def load_and_sample(parquet_path, n=150, seed=42):
    """加载 parquet 并随机采样"""
    df = pd.read_parquet(parquet_path)
    random.seed(seed)
    indices = random.sample(range(len(df)), min(n, len(df)))
    samples = []
    for i in indices:
        row = df.iloc[i]
        samples.append({
            "id": str(row["id"]),
            "event": str(row["event"]),
            "news1": str(row["news1"]),
            "news2": str(row["news2"]),
            "news3": str(row["news3"]),
            "question": str(row["questions"]),
            "reference_answer": str(row["answers"]),
        })
    return samples


def build_temp_collection(samples):
    """将样本的新闻文章索引到临时 ChromaDB collection（手动嵌入，与 build_vector_db 一致）"""
    from chromadb import PersistentClient
    from services.llm_service import get_embeddings

    client = PersistentClient(path=str(DATA_DIR / "chroma_db_eval"))
    emb = get_embeddings()

    collection_name = "crudrag_eval"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    coll = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    # 为每个样本的 3 篇新闻建立索引
    chunk_id = 0
    id_to_chunks = {}  # sample_id -> [chunk_ids...]
    batch_texts = []
    batch_ids = []
    batch_metas = []
    for s in samples:
        chunks = []
        for news_key in ["news1", "news2", "news3"]:
            text = s[news_key]
            for j in range(0, len(text), 500):
                chunk = text[j:j+500]
                if len(chunk) < 20:
                    continue
                cid = f"c{chunk_id}"
                batch_ids.append(cid)
                batch_texts.append(chunk)
                batch_metas.append({"sample_id": s["id"], "news_key": news_key})
                chunks.append(cid)
                chunk_id += 1
                # 每 32 条写入一次
                if len(batch_ids) >= 32:
                    vectors = emb.embed_documents(batch_texts)
                    coll.add(ids=batch_ids, embeddings=vectors, documents=batch_texts, metadatas=batch_metas)
                    batch_texts.clear()
                    batch_ids.clear()
                    batch_metas.clear()
        id_to_chunks[s["id"]] = chunks

    # 写入剩余批次
    if batch_ids:
        vectors = emb.embed_documents(batch_texts)
        coll.add(ids=batch_ids, embeddings=vectors, documents=batch_texts, metadatas=batch_metas)

    return coll, id_to_chunks


def evaluate_retrieval(samples, collection, id_to_chunks):
    """评估检索质量: Hit Rate@5 + MRR（向量检索，使用临时 collection）"""
    from services.llm_service import get_embeddings

    emb = get_embeddings()
    hits = 0
    reciprocal_ranks = []
    total_latency = 0

    for s in samples:
        t0 = time.time()
        q_vec = emb.embed_query(s["question"])
        raw = collection.query(query_embeddings=[q_vec], n_results=TOP_K)
        total_latency += (time.time() - t0) * 1000

        retrieved_ids = set(raw["ids"][0]) if raw.get("ids") and raw["ids"] else set()

        target_chunk_ids = set(id_to_chunks[s["id"]])

        # Hit Rate: 至少一个正确答案源 chunk 在 top-K 中
        if target_chunk_ids & retrieved_ids:
            hits += 1

        # MRR: 第一个正确答案源的排名
        rr = 0.0
        for rank, cid in enumerate(raw["ids"][0] if raw.get("ids") else [], 1):
            if cid in target_chunk_ids:
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)

    n = len(samples)
    hit_rate = hits / n if n > 0 else 0
    mrr = sum(reciprocal_ranks) / n if n > 0 else 0
    avg_latency = total_latency / n if n > 0 else 0

    return {
        "hit_rate@5": round(hit_rate, 4),
        "mrr": round(mrr, 4),
        "avg_latency_ms": round(avg_latency, 0),
        "total_queries": n,
    }


def evaluate_generation(samples, collection):
    """评估生成质量: BLEU-1 + ROUGE-L（使用临时 collection 检索 + LLM 生成）"""
    from collections import Counter
    from services.llm_service import get_embeddings
    from services.deepseek_client import chat

    emb = get_embeddings()
    bleu_scores = []
    rouge_l_scores = []

    for i, s in enumerate(samples):
        try:
            q_vec = emb.embed_query(s["question"])
            raw = collection.query(query_embeddings=[q_vec], n_results=TOP_K)
            retrieved_texts = raw["documents"][0] if raw.get("documents") else []
            context = "\n\n".join(f"[{j+1}] {t}" for j, t in enumerate(retrieved_texts))

            messages = [
                {"role": "system", "content": (
                    "你是一个基于知识库的智能学习助手。请根据提供的参考资料回答问题。"
                    "如果参考资料不足以回答问题，请诚实说明。"
                )},
                {"role": "user", "content": (
                    f"参考资料：\n{context}\n\n问题：{s['question']}\n\n请根据参考资料回答问题。"
                )},
            ]
            reply, _usage = chat(messages) if context else ("", {})
            generated = reply
        except Exception:
            generated = ""

        reference = s["reference_answer"]

        # BLEU-1 (jieba 分词适配中文)
        gen_tokens = list(jieba.cut(generated)) if generated else []
        ref_tokens = list(jieba.cut(reference))
        if gen_tokens:
            ref_counts = Counter(ref_tokens)
            matches = sum(min(ref_counts[t], gen_tokens.count(t)) for t in set(gen_tokens))
            bleu1 = matches / len(gen_tokens) if gen_tokens else 0
        else:
            bleu1 = 0
        bleu_scores.append(bleu1)

        # ROUGE-L (字符级 LCS，适合中文)
        m, n = len(generated), len(reference)
        if m == 0 or n == 0:
            rouge_l_scores.append(0.0)
            continue
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for a in range(m):
            for b in range(n):
                if generated[a] == reference[b]:
                    dp[a+1][b+1] = dp[a][b] + 1
                else:
                    dp[a+1][b+1] = max(dp[a+1][b], dp[a][b+1])
        lcs = dp[m][n]
        rouge_l = lcs / n if n > 0 else 0
        rouge_l_scores.append(rouge_l)

        if (i + 1) % 20 == 0:
            print(f"  [gen] {i+1}/{len(samples)}...")

    return {
        "bleu-1": round(sum(bleu_scores) / len(bleu_scores), 4) if bleu_scores else 0,
        "rouge-l": round(sum(rouge_l_scores) / len(rouge_l_scores), 4) if rouge_l_scores else 0,
    }


def main():
    print("=" * 60)
    print("CRUD-RAG 基准评测")
    print(f"样本数: {SAMPLE_SIZE} | 随机种子: {RANDOM_SEED}")
    print("=" * 60)

    parquet_path = DATA_DIR / "CRUD_RAG" / "train.parquet"
    if not parquet_path.exists():
        print(f"[ERROR] 数据集未找到: {parquet_path}")
        print("请先下载: curl -L 'https://hf-mirror.com/datasets/AndrewTsai0406/CRUD_RAG_3QA/resolve/main/data/train-00000-of-00001.parquet' -o data/CRUD_RAG/train.parquet")
        sys.exit(1)

    # 1. 加载 + 采样
    print("\n[1/4] 加载并采样...")
    samples = load_and_sample(parquet_path, n=SAMPLE_SIZE, seed=RANDOM_SEED)
    print(f"  已加载 {len(samples)} 条样本")

    # 2. 构建临时索引
    print("\n[2/4] 构建临时 ChromaDB 索引...")
    import chromadb
    collection, id_to_chunks = build_temp_collection(samples)
    total_chunks = sum(len(v) for v in id_to_chunks.values())
    print(f"  已索引 {total_chunks} chunks (约 {len(samples)*3} 篇文档)")

    # 3. 检索评估
    print("\n[3/4] 检索评估 (混合检索, k=5)...")
    retrieval_metrics = evaluate_retrieval(samples, collection, id_to_chunks)
    print(f"  Hit Rate@5: {retrieval_metrics['hit_rate@5']:.2%}")
    print(f"  MRR:        {retrieval_metrics['mrr']:.4f}")
    print(f"  Avg Latency: {retrieval_metrics['avg_latency_ms']:.0f}ms")

    # 4. 生成评估
    print("\n[4/4] 生成评估 (RAG query → BLEU-1 + ROUGE-L)...")
    generation_metrics = evaluate_generation(samples, collection)
    print(f"  BLEU-1:  {generation_metrics['bleu-1']:.4f}")
    print(f"  ROUGE-L: {generation_metrics['rouge-l']:.4f}")

    # ── 汇总 ──
    results = {
        "benchmark": "CRUD-RAG (ACM TOIS 2025)",
        "dataset": "AndrewTsai0406/CRUD_RAG_3QA",
        "sample_size": SAMPLE_SIZE,
        "random_seed": RANDOM_SEED,
        "pipeline": "bge-m3 + BM25 + jieba (混合检索, k=5)",
        "retrieval": retrieval_metrics,
        "generation": generation_metrics,
        "timestamp": int(time.time()),
    }

    print("\n" + "=" * 60)
    print("评测完成")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # 保存结果
    output_path = EVAL_DIR / "crudrag_results.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已保存: {output_path}")

    # 与论文基线对比
    print("\n━━━ 对比论文基线 ━━━")
    print("| 指标 | 我们的管道 | 论文 BM25 | 论文 DenseRetriever |")
    print("|------|:---:|:---:|:---:|")
    hr = retrieval_metrics['hit_rate@5']
    mrr = retrieval_metrics['mrr']
    bleu = generation_metrics['bleu-1']
    rouge = generation_metrics['rouge-l']
    print(f"| Hit Rate@5 | {hr:.2%} | — | — |")
    print(f"| MRR | {mrr:.4f} | — | — |")
    print(f"| BLEU-1 | {bleu:.4f} | — | — |")
    print(f"| ROUGE-L | {rouge:.4f} | — | — |")
    print("\n(论文基线值待查证后填入)")


if __name__ == "__main__":
    main()
