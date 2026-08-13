"""向量知识库构建 — 文档切分 + Embedding + Chroma 入库"""
import sys
import io
import re
from pathlib import Path

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb
from config import (
    CHROMA_PATH, CHROMA_COLLECTION, CHUNK_SIZE, CHUNK_OVERLAP,
    EMBEDDING_MODEL, KNOWLEDGE_SOURCES,
)
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).parent.parent.parent
NOTES_DIR = ROOT / "知识库" / "精炼笔记"
CLEANED_DIR = NOTES_DIR / "cleaned"
EXPORT_DIR = ROOT / "知识库" / "导出"


def load_documents(source_dirs):
    """加载所有 Markdown 文档，返回 (text, metadata) 列表"""
    docs = []
    for src_dir in source_dirs:
        src_path = Path(src_dir)
        if not src_path.exists():
            print(f"  [skip] {src_path} not found")
            continue
        for md_file in sorted(src_path.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            # 提取 arXiv ID
            arxiv_match = re.search(r"arXiv:\s*`?(\d+\.\d+(?:v\d+)?)`?", text)
            arxiv_id = arxiv_match.group(1) if arxiv_match else md_file.stem
            # 提取标题
            title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else md_file.stem

            docs.append({
                "text": text,
                "metadata": {
                    "source": str(md_file),
                    "filename": md_file.name,
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "source_dir": str(src_path),
                },
            })
    # 也加载 data/knowledge/*.json (排除 insights.json)
    json_dir = Path(__file__).parent.parent / "data" / "knowledge"
    if json_dir.exists():
        from services.knowledge_sync import extract_docs
        json_docs = extract_docs()
        for jd in json_docs:
            docs.append({
                "text": jd["text"],
                "metadata": {**jd["metadata"], "source_type": jd["metadata"].get("source_type", "knowledge_json")},
            })
        print(f"  [+] Loaded {len(json_docs)} items from data/knowledge/*.json")
    # 也加载论文知识库 papers.json
    papers_json = Path(__file__).parent.parent / "data" / "knowledge" / "papers.json"
    if papers_json.exists():
        try:
            from services.knowledge_sync import _extract_paper_docs
            paper_docs = _extract_paper_docs()
            for pd in paper_docs:
                docs.append({
                    "text": pd["text"],
                    "metadata": {**pd["metadata"], "source_type": "structured_paper"},
                })
            print(f"  [+] Loaded {len(paper_docs)} papers from data/knowledge/papers.json")
        except Exception as e:
            print(f"  [!] Failed to load papers: {e}")
    return docs


def chunk_documents(docs, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    """切分文档为 chunks，保留元数据"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "。", " ", ""],
        length_function=len,
    )

    all_chunks = []
    for doc in docs:
        chunks = splitter.split_text(doc["text"])
        for i, chunk in enumerate(chunks):
            all_chunks.append({
                "text": chunk,
                "metadata": {**doc["metadata"], "chunk_index": i},
            })
    return all_chunks


def build_chroma(chunks, collection_name=CHROMA_COLLECTION, persist_dir=None):
    """构建 Chroma 向量库"""
    persist_dir = str(persist_dir) if persist_dir else str(CHROMA_PATH)

    print(f"Loading embeddings: {EMBEDDING_MODEL}")
    emb = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True, device="cpu")

    print(f"Initializing Chroma at: {persist_dir}")
    client = chromadb.PersistentClient(path=persist_dir)

    # 删除旧 collection（如果存在）
    try:
        client.delete_collection(collection_name)
        print(f"  Dropped existing collection: {collection_name}")
    except Exception:
        pass

    collection = client.create_collection(
        name=collection_name,
        metadata={"embedding_model": EMBEDDING_MODEL, "hnsw:space": "cosine"},
    )

    print(f"Embedding {len(chunks)} chunks ...")
    batch_size = 32
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["text"] for c in batch]
        ids = [f"chunk_{j}" for j in range(i, i + len(batch))]
        metadatas = [{k: v if isinstance(v, (str, int, float, bool)) else str(v)
                      for k, v in c["metadata"].items()} for c in batch]

        vectors = emb.encode(texts, normalize_embeddings=True).tolist()
        collection.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )

        pct = min(100, (i + batch_size) / len(chunks) * 100)
        print(f"  {min(i + batch_size, len(chunks))}/{len(chunks)} ({pct:.0f}%)")

    print(f"Collection '{collection_name}': {collection.count()} documents")
    return collection


def main(source_dirs=None, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    if source_dirs is None:
        source_dirs = [CLEANED_DIR, EXPORT_DIR]

    print("=" * 50)
    print("向量知识库构建管线")
    print(f"  chunk_size={chunk_size}, overlap={chunk_overlap}")
    print("=" * 50)

    # Step 1: Load
    print("\n[1/3] Loading documents ...")
    docs = load_documents(source_dirs)
    print(f"  Loaded {len(docs)} documents")
    for d in docs:
        print(f"    - {d['metadata']['filename']} ({len(d['text'])} chars)")

    if not docs:
        print("No documents found. Aborting.")
        return

    # Step 2: Chunk
    print(f"\n[2/3] Chunking documents (size={chunk_size}, overlap={chunk_overlap}) ...")
    chunks = chunk_documents(docs, chunk_size, chunk_overlap)
    print(f"  Produced {len(chunks)} chunks")
    avg_len = sum(len(c["text"]) for c in chunks) / len(chunks) if chunks else 0
    print(f"  Average chunk length: {avg_len:.0f} chars")

    # Step 3: Embed + Store
    print(f"\n[3/3] Building Chroma vector database ...")
    collection = build_chroma(chunks)
    print(f"\nDone. Vector DB ready at: {CHROMA_PATH}")

    # Quick stats
    print(f"\nStats:")
    print(f"  Documents: {len(docs)}")
    print(f"  Chunks: {len(chunks)}")
    print(f"  Collection size: {collection.count()}")
    return collection


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="构建向量知识库")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=CHUNK_OVERLAP)
    parser.add_argument("--dry-run", action="store_true", help="只切分，不入库")
    parser.add_argument("--stats-only", action="store_true", help="只显示现有库统计")
    args = parser.parse_args()

    if args.stats_only:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        try:
            col = client.get_collection(CHROMA_COLLECTION)
            print(f"Collection: {CHROMA_COLLECTION}")
            print(f"  Documents: {col.count()}")
            print(f"  Metadata: {col.metadata}")
        except Exception as e:
            print(f"No collection found: {e}")
    elif args.dry_run:
        docs = load_documents([CLEANED_DIR, EXPORT_DIR])
        print(f"Loaded {len(docs)} documents")
        chunks = chunk_documents(docs, args.chunk_size, args.chunk_overlap)
        print(f"Would produce {len(chunks)} chunks")
        for i, c in enumerate(chunks[:5]):
            print(f"\n--- Chunk {i} ---")
            print(c["text"][:200])
    else:
        main(chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)
