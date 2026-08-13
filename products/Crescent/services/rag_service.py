"""RAG 检索增强生成服务 — Chroma 检索 + DeepSeek 生成"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
from config import CHROMA_PATH, CHROMA_COLLECTION
from services.llm_service import embeddings
from services.deepseek_client import chat, load_prompt
import jieba
import re
from rank_bm25 import BM25Okapi


def _do_search(col, emb, query, k):
    """执行一次向量检索（不做过滤，返回 top-k 原始结果）"""
    query_vec = emb.embed_query(query)
    results = col.query(query_embeddings=[query_vec], n_results=k)

    chunks = []
    for i in range(len(results["ids"][0])):
        dist = results["distances"][0][i]
        sim = 1 - dist
        meta = results["metadatas"][0][i]
        chunks.append({
            "text": results["documents"][0][i],
            "source": meta.get("filename", "?"),
            "title": meta.get("title", "?"),
            "arxiv_id": meta.get("arxiv_id", ""),
            "similarity": round(sim, 4),
        })

    return chunks


# BM25 检索器缓存
_bm25_cache = {}

# ChromaDB 客户端缓存 — 避免每次检索重新打开
_chroma_client = None
_chroma_collection = None


def _get_chroma():
    """获取缓存的 ChromaDB client + collection"""
    global _chroma_client, _chroma_collection
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _chroma_collection = _chroma_client.get_collection(CHROMA_COLLECTION)
    return _chroma_client, _chroma_collection


def _get_bm25(col):
    """构建或获取 BM25 检索器（带缓存）"""
    col_id = id(col)
    if col_id not in _bm25_cache:
        all_docs = col.get()["documents"]
        if not all_docs:
            _bm25_cache[col_id] = (None, [])
            return _bm25_cache[col_id]
        tokenized = [list(jieba.cut(doc)) for doc in all_docs]
        _bm25_cache[col_id] = (BM25Okapi(tokenized), all_docs)
    return _bm25_cache[col_id]


def _bm25_search(col, query, k=10):
    """BM25 关键词检索"""
    bm25, all_docs = _get_bm25(col)
    if bm25 is None:
        return []
    tokenized_query = list(jieba.cut(query))
    scores = bm25.get_scores(tokenized_query)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    results = []
    all_ids = col.get()["ids"]
    all_metadatas = col.get()["metadatas"]
    for i in top_indices:
        results.append({
            "text": all_docs[i],
            "source": all_metadatas[i].get("filename", "?"),
            "title": all_metadatas[i].get("title", "?"),
            "arxiv_id": all_metadatas[i].get("arxiv_id", ""),
            "bm25_score": float(scores[i]),
            "similarity": 0.0,
        })
    return results


def _fusion_results(vector_results, bm25_results, vector_weight=0.6):
    """加权融合向量检索和 BM25 检索结果 (RRF 变体)"""
    combined = {}

    for rank, r in enumerate(vector_results):
        key = r["text"][:100]
        score = r["similarity"] * vector_weight + (1.0 / (rank + 1)) * 0.1
        combined[key] = {"rank": rank, "score": score, **r}

    for rank, r in enumerate(bm25_results):
        key = r["text"][:100]
        score = (1.0 / (rank + 1)) * (1 - vector_weight)
        if key in combined:
            combined[key]["score"] += score
            combined[key]["bm25_score"] = r.get("bm25_score", 0)
        else:
            r["score"] = score
            combined[key] = r

    sorted_results = sorted(combined.values(), key=lambda x: x["score"], reverse=True)
    return sorted_results


def _dynamic_filter(chunks, ratio=0.8, min_results=2):
    """动态阈值：以 top-1 为锚点，保留相似度 >= top_sim * ratio 的结果"""
    if not chunks:
        return []
    top_sim = chunks[0]["similarity"]
    threshold = top_sim * ratio
    filtered = [c for c in chunks if c["similarity"] >= threshold]
    # 至少保留 min_results 条（除非原始结果就少于这个数）
    if len(filtered) < min_results and len(chunks) >= min_results:
        filtered = chunks[:min_results]
    return filtered


# ── Reranker ──

_reranker = None


def _get_reranker():
    """懒加载 cross-encoder reranker 模型 (~1.3GB)"""
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        import config as _cfg
        _reranker = CrossEncoder(_cfg.RERANKER_MODEL, max_length=512)
    return _reranker


def rerank(query, chunks, top_k=None):
    """Cross-encoder 精排: 对 (query, chunk_text) 打分重排。

    Returns:
        Re-ranked chunks with added 'rerank_score' field.
    """
    import config as _cfg
    if not chunks or len(chunks) <= 1:
        return chunks

    top_k = top_k or _cfg.RERANKER_TOP_K
    if len(chunks) <= top_k:
        return chunks

    model = _get_reranker()
    pairs = [(query, c["text"]) for c in chunks]
    scores = model.predict(pairs)

    for i, score in enumerate(scores):
        chunks[i]["rerank_score"] = round(float(score), 4)

    chunks.sort(key=lambda c: c.get("rerank_score", 0), reverse=True)
    return chunks[:top_k]


def _search_bm25_only(col, query, k=10):
    """纯 BM25 检索（向量不可用时的降级路径）"""
    bm25_results = _bm25_search(col, query, k=k)
    for r in bm25_results:
        r["similarity"] = 0.0
    return bm25_results


# ── Search ──

_QUERY_REWRITE_CACHE: dict[str, str] = {}
_QUERY_REWRITE_CACHE_MAX = 100

_REWRITE_TRIGGERS = [
    "那篇论文", "这个", "那个", "它", "他", "她", "他们", "她们",
    "这篇文章", "上面那个", "前面那个", "刚才", "之前那个",
    "this", "that", "it", "they", "the above", "the previous",
]

_NEVER_REWRITE = re.compile(r"^(你好|hi|hello|谢谢|bye|再见|好的|ok|嗯|哦|是的|对的|不是)$", re.IGNORECASE)


def _needs_rewrite(query: str) -> bool:
    if _NEVER_REWRITE.match(query.strip()):
        return False
    query_lower = query.lower()
    return any(trigger in query_lower for trigger in _REWRITE_TRIGGERS)


def _rewrite_query(original_query: str, history: list = None) -> str:
    key = original_query.strip()
    if key in _QUERY_REWRITE_CACHE:
        return _QUERY_REWRITE_CACHE[key]
    if not _needs_rewrite(original_query):
        return original_query
    history_context = ""
    if history and len(history) > 0:
        recent = history[-3:]
        history_context = "\n".join([
            f"用户: {h.get('question', '')}\n助手: {h.get('answer', '')}"
            for h in recent
        ])
    system_prompt = (
        "你是一个查询改写助手。你的任务是将包含代词或模糊指代的查询改写为明确、具体的查询。"
        "规则：1) 将代词替换为上下文中的具体实体；2) 添加同义词以增加召回；3) 保留原始语言（中文/英文）；"
        "4) 只输出改写后的查询，不要任何解释。"
    )
    user_msg = f"原始查询: {original_query}"
    if history_context:
        user_msg = f"对话历史:\n{history_context}\n\n{user_msg}"
    try:
        rewritten, _ = chat(
            messages=[{"role": "user", "content": user_msg}],
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=200,
            timeout=15,
        )
        rewritten = rewritten.strip()
        if not rewritten or len(rewritten) > len(original_query) * 5:
            return original_query
    except Exception:
        return original_query
    if len(_QUERY_REWRITE_CACHE) >= _QUERY_REWRITE_CACHE_MAX:
        _QUERY_REWRITE_CACHE.pop(next(iter(_QUERY_REWRITE_CACHE)))
    _QUERY_REWRITE_CACHE[key] = rewritten
    return rewritten


def _expand_query(query: str) -> list[str]:
    """短查询展开：提取名词/动词作为独立搜索短语，与原文合并去重"""
    if len(query) > 15:
        return [query]
    tokens = list(jieba.cut(query))
    # 过滤停用词和单字
    stop = {"的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
            "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好"}
    keywords = [t for t in tokens if len(t) > 1 and t not in stop]
    if not keywords:
        return [query]
    # 2-gram 组合 + 单关键词
    variants = [query]
    for i, kw in enumerate(keywords):
        variants.append(kw)
        if i < len(keywords) - 1:
            variants.append(keywords[i] + keywords[i + 1])
    return list(dict.fromkeys(variants))[:4]  # 最多 4 个去重变体


def search(query, k=10, dynamic_ratio=0.85, use_hybrid=True, use_reranker=None):
    """向量检索 — 动态阈值 + 英文回退 + 可选混合检索 + 可选精排。
    关键路径降级：embedding 不可用 → 纯 BM25；ChromaDB 不可用 → 返回空。
    """
    import re
    import config as _cfg

    if use_reranker is None:
        use_reranker = _cfg.USE_RERANKER

    retrieval_k = _cfg.RERANKER_COARSE_K if use_reranker else k
    query = _rewrite_query(query)
    expanded = _expand_query(query)

    # ── 关键路径降级: 向量检索 ──
    try:
        emb = embeddings()
        _vector_available = True
    except Exception:
        emb = None
        _vector_available = False

    try:
        client, col = _get_chroma()
    except Exception:
        return []

    # ── 向量检索 (主路径，多 query 变体 RRF 归并) ──
    chunks = []
    if _vector_available:
        if len(expanded) > 1:
            # 多 query 变体：各搜一次，按 ID 去重取最高分
            seen = {}
            for q in expanded:
                for c in _do_search(col, emb, q, retrieval_k):
                    cid = c.get("id", c.get("text", ""))
                    if cid not in seen or c["similarity"] > seen[cid]["similarity"]:
                        seen[cid] = c
            chunks = sorted(seen.values(), key=lambda x: x.get("similarity", 0), reverse=True)[:retrieval_k]
        else:
            chunks = _do_search(col, emb, query, retrieval_k)

        # 英文回退
        if not chunks or chunks[0]["similarity"] < 0.35:
            chinese_chars = re.findall(r"[一-鿿]+", query)
            if chinese_chars:
                fallback_query = " ".join(chinese_chars)
                if fallback_query != query:
                    chunks = _do_search(col, emb, fallback_query, retrieval_k)

    # ── 混合检索: 向量 + BM25 ──
    if use_hybrid or not _vector_available:
        try:
            bm25_results = _bm25_search(col, query, k=retrieval_k)
            if not _vector_available:
                chunks = _search_bm25_only(col, query, k=retrieval_k)
            else:
                chunks = _fusion_results(chunks, bm25_results, vector_weight=0.6)
        except Exception:
            pass

    # Reranker 精排
    if use_reranker and len(chunks) > k:
        chunks = rerank(query, chunks, top_k=k)
    else:
        chunks = _dynamic_filter(chunks, ratio=dynamic_ratio)

    return chunks


def format_context(chunks):
    """将检索结果拼接为 LLM 可用的上下文"""
    if not chunks:
        return ""

    parts = []
    for i, c in enumerate(chunks, 1):
        src = c["title"] if len(c["title"]) < 80 else c["source"]
        parts.append(f"[{i}] 来源: {src}\n{c['text']}")
    return "\n\n".join(parts)


def search_iterative(query, k=5, topn=2):
    """迭代检索：先给 top-N chunk，LLM 判断充足性，不足则扩展到 k。

    与 search() 的区别：
    - search(): 一次性返回 top-k（噪声多，浪费 Agent 上下文窗口）
    - 本函数: 先返回 topn → LLM 快速判断是否充足 → 不足才返回全部 k 条

    成本: 多一个短 LLM 调用（~10 tokens，只回复 YES/NO）。
    返回: chunks 列表（dict 格式，同 search()）。
    """
    chunks = search(query, k=k)
    if not chunks or len(chunks) <= topn:
        return chunks

    top_chunks = chunks[:topn]
    top_context = format_context(top_chunks)

    sufficiency_msg = (
        f"参考资料:\n{top_context}\n\n"
        f"用户问题: {query}\n\n"
        f"以上参考资料是否足以回答用户问题？只回复 YES 或 NO。"
    )
    try:
        sufficiency_reply, _ = chat(
            messages=[{"role": "user", "content": sufficiency_msg}],
            system_prompt="你是一个参考资料充足性判断器。只回复 YES 或 NO，不要解释。",
            temperature=0,
            max_tokens=10,
        )
        sufficient = "YES" in sufficiency_reply.strip().upper()
    except Exception:
        sufficient = False

    if sufficient:
        return top_chunks
    return chunks


def rag_query(question, history=None, k=5):
    """完整的 RAG 流程：检索 → 拼接 → 生成 → 返回答案+来源"""
    chunks = search(question, k=k)
    context = format_context(chunks)

    system_prompt = load_prompt("rag") or (
        "你是一个基于知识库的智能学习助手。请根据提供的参考资料回答问题。"
        "如果参考资料不足以回答问题，请诚实说明'参考资料中没有相关信息'，"
        "然后基于你的知识给出回答并明确标注。"
        "回答时请引用来源编号，例如 [1] [2]。"
        "用中文回答，简明扼要，控制在300字以内。"
    )

    history_str = ""
    if history:
        history_str = "\n".join([
            f"用户: {h.get('question', '')}\n助手: {h.get('answer', '')}"
            for h in history[-3:]  # 最近 3 轮
        ])

    user_msg = ""
    if context:
        user_msg += f"参考资料:\n{context}\n\n"
    else:
        user_msg += "（未找到相关参考资料）\n\n"
    if history_str:
        user_msg += f"对话历史:\n{history_str}\n\n"
    user_msg += f"问题: {question}"

    reply, usage = chat(
        messages=[{"role": "user", "content": user_msg}],
        system_prompt=system_prompt,
        max_tokens=800,
    )

    sources = []
    for c in chunks:
        sources.append({
            "title": c["title"],
            "source": c["source"],
            "arxiv_id": c.get("arxiv_id", ""),
            "similarity": c["similarity"],
            "snippet": c["text"][:150],
        })

    return {
        "answer": reply,
        "sources": sources,
        "context_found": len(chunks) > 0,
        "usage": usage,
    }


def rag_query_iterative(question, history=None, k=5, topn=2):
    """迭代检索 + 渐进式披露：先给 top-N chunk，LLM 判断够不够，不够再加。

    与 rag_query 的区别：
    - rag_query: 一次性把 k 条 chunk 全塞给 LLM（噪声多）
    - 本函数: 先给 topn 条 → LLM 判断充足性 → 不足则追加到 k 条

    成本: 多一个短 LLM 调用（~200 tokens）做充足性判断。
    """
    chunks = search(question, k=k)
    if not chunks:
        return {
            "answer": "参考资料中没有相关信息。",
            "sources": [],
            "context_found": False,
            "iterative_rounds": 0,
        }

    top_chunks = chunks[:topn]
    top_context = format_context(top_chunks)

    # Round 1: 充足性判断
    sufficiency_prompt = (
        "你是一个参考资料充足性判断器。请根据提供的参考资料，判断是否足以回答用户问题。"
        "只回复 YES 或 NO，不要解释。"
    )
    sufficiency_msg = (
        f"参考资料:\n{top_context}\n\n"
        f"用户问题: {question}\n\n"
        f"以上参考资料是否足以回答问题？(YES/NO)"
    )
    try:
        sufficiency_reply, _ = chat(
            messages=[{"role": "user", "content": sufficiency_msg}],
            system_prompt=sufficiency_prompt,
            temperature=0,
            max_tokens=10,
        )
        sufficient = "YES" in sufficiency_reply.strip().upper()
    except Exception:
        sufficient = False

    # Round 2: 如果不足，追加剩余 chunk
    if sufficient:
        final_context = top_context
        used_chunks = top_chunks
        rounds = 1
    else:
        final_context = format_context(chunks)
        used_chunks = chunks
        rounds = 2

    system_prompt = load_prompt("rag") or (
        "你是一个基于知识库的智能学习助手。请根据提供的参考资料回答问题。"
        "如果参考资料不足以回答问题，请诚实说明。"
        "回答时请引用来源编号，例如 [1] [2]。"
        "用中文回答，简明扼要，控制在300字以内。"
    )

    history_str = ""
    if history:
        history_str = "\n".join([
            f"用户: {h.get('question', '')}\n助手: {h.get('answer', '')}"
            for h in history[-3:]
        ])

    user_msg = f"参考资料:\n{final_context}\n\n"
    if history_str:
        user_msg += f"对话历史:\n{history_str}\n\n"
    user_msg += f"问题: {question}"

    reply, usage = chat(
        messages=[{"role": "user", "content": user_msg}],
        system_prompt=system_prompt,
        max_tokens=800,
    )

    sources = []
    for c in used_chunks:
        sources.append({
            "title": c["title"],
            "source": c["source"],
            "arxiv_id": c.get("arxiv_id", ""),
            "similarity": c["similarity"],
            "snippet": c["text"][:150],
        })

    return {
        "answer": reply,
        "sources": sources,
        "context_found": True,
        "iterative_rounds": rounds,
        "usage": usage,
    }


def invalidate_bm25_cache():
    """清除 BM25 缓存（ChromaDB 更新后调用）"""
    _bm25_cache.clear()
