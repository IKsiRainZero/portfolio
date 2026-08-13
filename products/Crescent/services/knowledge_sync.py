"""JSON 知识库 → ChromaDB 同步服务
将 data/knowledge/*.json 的结构化知识提取为可向量化的文本块，
支持增量更新（只嵌入新增/修改的条目）。
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
from config import CHROMA_PATH, CHROMA_COLLECTION, DATA_DIR, CHUNK_SIZE, CHUNK_OVERLAP
from services.llm_service import get_embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

KNOWLEDGE_DIR = DATA_DIR / "knowledge"
SKIP_FILES = {"insights.json"}


def _item_to_text(item):
    """将单个 knowledge item 转为可检索的文本表示"""
    item_type = item.get("type", "concept")
    parts = []

    if item_type == "concept":
        title = item.get("title", "")
        content = item.get("content", "")
        tags = ", ".join(item.get("tags", []))
        parts.append(f"标题: {title}")
        if content:
            parts.append(f"内容: {content}")
        if tags:
            parts.append(f"标签: {tags}")
        # 扩展字段 (v3)
        if item.get("prerequisites"):
            parts.append(f"前置知识: {'; '.join(item['prerequisites'])}")
        if item.get("learning_objectives"):
            parts.append(f"学习目标: {'; '.join(item['learning_objectives'])}")
        for ex in item.get("practical_exercises", []):
            parts.append(f"练习 - {ex.get('title', '')}: {ex.get('description', '')}")
        for sc in item.get("sub_concepts", []):
            parts.append(f"子概念 - {sc.get('title', '')}: {sc.get('content', '')}")

    elif item_type == "qa":
        parts.append(f"问题: {item.get('question', '')}")
        parts.append(f"答案: {item.get('answer', '')}")
        if item.get("tags"):
            parts.append(f"标签: {', '.join(item.get('tags', []))}")

    elif item_type == "table":
        title = item.get("title", "")
        headers = " | ".join(item.get("headers", []))
        parts.append(f"表格: {title}")
        parts.append(f"列: {headers}")
        for row in item.get("rows", []):
            parts.append(" | ".join(str(c) for c in row))

    elif item_type == "code":
        title = item.get("title", "")
        code = item.get("code", "")
        explanation = item.get("explanation", "")
        parts.append(f"代码: {title}")
        if code:
            parts.append(f"代码:\n{code}")
        if explanation:
            parts.append(f"说明: {explanation}")

    elif item_type == "code_example":
        title = item.get("title", "")
        language = item.get("language", "")
        code = item.get("code", "")
        explanation = item.get("explanation", "")
        parts.append(f"代码示例: {title} (语言: {language})")
        if code:
            parts.append(f"代码:\n{code}")
        if explanation:
            parts.append(f"说明: {explanation}")

    return "\n".join(parts)


def extract_docs():
    """扫描 data/knowledge/*.json，提取所有条目为 doc 列表

    Returns:
        list[dict]: [{"text": ..., "metadata": {...}}, ...]
    """
    docs = []
    for json_file in sorted(KNOWLEDGE_DIR.glob("*.json")):
        if json_file.name in SKIP_FILES:
            continue

        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            continue

        meta_info = data.get("meta", {})
        domain = meta_info.get("domain", json_file.stem)
        display_name = meta_info.get("display_name", domain)

        sections = data.get("sections", [])
        for section in sections:
            section_title = section.get("title", "")
            for item in section.get("items", []):
                text = _item_to_text(item)
                if not text.strip():
                    continue

                content_hash = hashlib.md5(text.encode()).hexdigest()[:8]
                docs.append({
                    "text": text,
                    "metadata": {
                        "source": str(json_file),
                        "filename": json_file.name,
                        "domain": domain,
                        "display_name": display_name,
                        "section": section_title,
                        "item_id": item.get("id", ""),
                        "item_type": item.get("type", "concept"),
                        "title": item.get("title", "")[:80],
                        "content_hash": content_hash,
                        "source_type": "knowledge_json",
                    },
                })

    return docs


def _extract_paper_docs():
    """从 papers.json 提取论文条目为可向量化的 doc 列表"""
    docs = []
    papers_file = KNOWLEDGE_DIR / "papers.json"
    if not papers_file.exists():
        return docs
    try:
        from services.paper_index import load as load_papers, paper_to_searchable_text
        papers_data = load_papers()
        for paper in papers_data.get("papers", []):
            text = paper_to_searchable_text(paper)
            if not text.strip():
                continue
            content_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            docs.append({
                "text": text,
                "metadata": {
                    "source": str(papers_file),
                    "filename": "papers.json",
                    "domain": "papers",
                    "display_name": "论文知识库",
                    "section": paper.get("core_problem", "")[:80],
                    "item_id": paper.get("canonical_id", ""),
                    "item_type": "paper",
                    "title": paper.get("title", "")[:80],
                    "content_hash": content_hash,
                    "source_type": "structured_paper",
                    "arxiv_id": paper.get("arxiv_id", ""),
                    "credibility_score": paper.get("credibility_score") or 0.0,
                    "categories": ", ".join(paper.get("categories", [])),
                },
            })
    except Exception:
        pass
    return docs


def chunk_docs(docs, chunk_size=None, chunk_overlap=None):
    """对提取的 docs 进行文本切分"""
    chunk_size = chunk_size or CHUNK_SIZE
    chunk_overlap = chunk_overlap or CHUNK_OVERLAP
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "。", " ", ""],
        length_function=len,
    )

    chunks = []
    for doc in docs:
        text = doc["text"]
        sub_chunks = splitter.split_text(text)
        for i, chunk_text in enumerate(sub_chunks):
            chunks.append({
                "text": chunk_text,
                "metadata": {**doc["metadata"], "chunk_index": i},
            })
    return chunks


def get_existing_ids():
    """从 ChromaDB 获取已存在的 knowledge_json 来源的 chunk ID 列表"""
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        col = client.get_or_create_collection(CHROMA_COLLECTION, metadata={"embedding_model": "bge-m3", "hnsw:space": "cosine"})
        result = col.get(where={"source_type": "knowledge_json"})
        existing = []
        for i, meta in enumerate(result["metadatas"]):
            if meta.get("source_type") == "knowledge_json":
                existing.append({
                    "id": result["ids"][i],
                    "item_id": meta.get("item_id", ""),
                    "filename": meta.get("filename", ""),
                    "content_hash": meta.get("content_hash", ""),
                })
        return existing
    except Exception:
        return []


def sync_knowledge_to_chroma(chunk_size=None, chunk_overlap=None):
    """增量同步: 只嵌入新的/修改过的 knowledge JSON 条目

    Returns:
        dict: {"added": int, "skipped": int, "total_chunks": int}
    """
    chunk_size = chunk_size or CHUNK_SIZE
    chunk_overlap = chunk_overlap or CHUNK_OVERLAP

    print("=" * 50)
    print("JSON 知识库 → ChromaDB 增量同步")
    print("=" * 50)

    # 1. 提取 JSON 知识条目
    print("\n[1/4] Extracting knowledge items from JSON...")
    docs = extract_docs()
    print(f"  Extracted {len(docs)} text docs from JSON files")

    # 2. 获取已存在的条目
    print("\n[2/4] Checking existing entries in ChromaDB...")
    existing = get_existing_ids()
    existing_item_ids = {e["item_id"] for e in existing}
    print(f"  Found {len(existing)} existing knowledge_json chunks")

    # 2b. Detect edited items via content_hash mismatch
    item_hash_map = {}
    existing_id_by_item = {}
    for e in existing:
        if e["item_id"] and e.get("content_hash"):
            item_hash_map[e["item_id"]] = e["content_hash"]
            existing_id_by_item.setdefault(e["item_id"], []).append(e["id"])

    edited_item_ids = set()
    for doc in docs:
        item_id = doc["metadata"]["item_id"]
        if item_id in item_hash_map:
            old_hash = item_hash_map[item_id]
            new_hash = doc["metadata"].get("content_hash", "")
            if old_hash and new_hash and old_hash != new_hash:
                edited_item_ids.add(item_id)

    if edited_item_ids:
        edit_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        edit_col = edit_client.get_or_create_collection(CHROMA_COLLECTION, metadata={"embedding_model": "bge-m3", "hnsw:space": "cosine"})
        ids_to_delete = []
        for item_id in edited_item_ids:
            ids_to_delete.extend(existing_id_by_item.get(item_id, []))
        if ids_to_delete:
            edit_col.delete(ids=ids_to_delete)
        print(f"  Deleted {len(ids_to_delete)} outdated chunks for {len(edited_item_ids)} edited items")
        for item_id in edited_item_ids:
            existing_item_ids.discard(item_id)

    # 3. 过滤出新条目
    new_docs = []
    for doc in docs:
        item_id = doc["metadata"]["item_id"]
        if item_id not in existing_item_ids:
            new_docs.append(doc)
    print(f"  New/modified items: {len(new_docs)}")

    # 3b. 同样提取论文条目
    paper_docs = _extract_paper_docs()
    paper_existing = []
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        col = client.get_or_create_collection(CHROMA_COLLECTION, metadata={"embedding_model": "bge-m3", "hnsw:space": "cosine"})
        paper_result = col.get(where={"source_type": "structured_paper"})
        for i, meta in enumerate(paper_result["metadatas"]):
            if meta.get("source_type") == "structured_paper":
                paper_existing.append(meta.get("item_id", ""))
    except Exception:
        pass

    new_paper_docs = [pd for pd in paper_docs if pd["metadata"]["item_id"] not in paper_existing]
    if new_paper_docs:
        print(f"  New paper items: {len(new_paper_docs)}")
        new_docs.extend(new_paper_docs)

    if not new_docs:
        print("\nNo new items to sync. Done.")
        return {"added": 0, "skipped": len(docs) + len(paper_docs), "total_chunks": len(existing) + len(paper_existing)}

    # 4. 切分 + 嵌入
    print(f"\n[3/4] Chunking new items (size={chunk_size}, overlap={chunk_overlap})...")
    chunks = chunk_docs(new_docs, chunk_size, chunk_overlap)
    print(f"  Produced {len(chunks)} chunks")

    print(f"\n[4/4] Embedding and storing...")
    emb = get_embeddings()
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    col = client.get_or_create_collection(CHROMA_COLLECTION, metadata={"embedding_model": "bge-m3", "hnsw:space": "cosine"})

    batch_size = 32
    current_count = col.count()
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["text"] for c in batch]
        ids = [f"kj_{current_count + j}" for j in range(i, i + len(batch))]
        metadatas = [{k: v if isinstance(v, (str, int, float, bool)) else str(v) for k, v in c["metadata"].items()} for c in batch]

        vectors = emb.embed_documents(texts)
        col.add(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)

        pct = min(100, (i + batch_size) / len(chunks) * 100)
        print(f"  {min(i + batch_size, len(chunks))}/{len(chunks)} ({pct:.0f}%)")

    final_count = col.count()
    print(f"\nSync complete: {len(existing)} existing + {len(chunks)} new = {final_count} total")

    # 清除 BM25 缓存以便下次检索使用新数据
    from services.rag_service import invalidate_bm25_cache
    invalidate_bm25_cache()

    return {
        "added": len(chunks),
        "skipped": len(docs) - len(new_docs),
        "total_chunks": final_count,
    }


def needs_sync():
    """检查是否有未被向量化的 JSON 条目

    Returns:
        bool: True 表示有新的 JSON 条目需要同步
    """
    docs = extract_docs()
    existing = get_existing_ids()
    existing_item_ids = {e["item_id"] for e in existing}
    new_count = sum(1 for d in docs if d["metadata"]["item_id"] not in existing_item_ids)
    return new_count > 0


def sync_status():
    """返回同步状态摘要"""
    docs = extract_docs()
    existing = get_existing_ids()
    existing_item_ids = {e["item_id"] for e in existing}
    new_items = [d for d in docs if d["metadata"]["item_id"] not in existing_item_ids]

    return {
        "json_total_items": len(docs),
        "chroma_knowledge_chunks": len(existing),
        "pending_items": len(new_items),
        "needs_sync": len(new_items) > 0,
        "pending_domains": list(set(d["metadata"]["domain"] for d in new_items)),
    }
