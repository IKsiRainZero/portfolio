# Knowledge Bridge: JSON↔ChromaDB 通道 + RAG 增强

> **For agentic workers:** Use `superpowers:subagent-driven-development` to implement task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通 `data/knowledge/*.json` → ChromaDB 向量库的自动同步通道，让 Agent 能检索到所有知识库内容，加上中文混合检索提升召回率。

**Architecture:** 新增 `services/knowledge_sync.py` 负责 JSON→文本提取→增量嵌入；修改 `services/rag_service.py` 加入 BM25 混合检索；`scripts/build_vector_db.py` 扩展支持 JSON 数据源。保持向后兼容，不破坏现有 ChromaDB 结构。

**Tech Stack:** Python, chromadb, jieba, rank_bm25, bge-m3 embedding

---

## 当前状态 (Baseline)

| 指标 | 值 |
|---|---|
| ChromaDB 文档数 | 3724 |
| RAG Hit Rate@5 | 76.67% (23/30) |
| RAG MRR | 0.7000 |
| Avg Latency | 2.86s |
| JSON 知识条目(未向量化) | 123 (agent-development 36 + ai-curriculum 35 + 其他 52) |
| JSON→ChromaDB 通道 | ❌ 不存在 |

## 目标状态

| 指标 | 目标 |
|---|---|
| ChromaDB 文档数 | ~4000+ (新增 ~200-300 chunks) |
| JSON→ChromaDB 同步 | ✅ 启动自动检测 + API手动触发 |
| RAG Hit Rate@5 | ≥80% |
| 中文检索命中率 | 提升 (当前 5/12) |
| 增量更新 | ✅ 只嵌入新增/修改的条目 |

---

### Task 1: JSON 知识提取器

**Files:**
- Create: `portfolio-app/services/knowledge_sync.py`

**Purpose:** 从 `data/knowledge/*.json` 中提取可向量化的文本块，生成与现有 `build_vector_db.py` 兼容的 doc 格式。

- [ ] **Step 1: 编写 knowledge_sync.py**

```python
"""JSON 知识库 → ChromaDB 同步服务
将 data/knowledge/*.json 的结构化知识提取为可向量化的文本块，
支持增量更新（只嵌入新增/修改的条目）。
"""
import json
import sys
import re
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
from config import CHROMA_PATH, CHROMA_COLLECTION, DATA_DIR
from services.llm_service import get_embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

KNOWLEDGE_DIR = DATA_DIR / "knowledge"
# insights.json 是方法论卡片，不做全文向量化（卡片数量多但每条短）
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
                        "source_type": "knowledge_json",
                    },
                })

    return docs


def chunk_docs(docs, chunk_size=500, chunk_overlap=50):
    """对提取的 docs 进行文本切分"""
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
        col = client.get_collection(CHROMA_COLLECTION)
        # 获取所有元数据
        result = col.get()
        existing = []
        for i, meta in enumerate(result["metadatas"]):
            if meta.get("source_type") == "knowledge_json":
                existing.append({
                    "id": result["ids"][i],
                    "item_id": meta.get("item_id", ""),
                    "filename": meta.get("filename", ""),
                })
        return existing
    except Exception:
        return []


def sync_knowledge_to_chroma(chunk_size=500, chunk_overlap=50):
    """增量同步: 只嵌入新的/修改过的 knowledge JSON 条目
    
    Returns:
        dict: {"added": int, "skipped": int, "total_chunks": int}
    """
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

    # 3. 过滤出新条目
    new_docs = []
    for doc in docs:
        item_id = doc["metadata"]["item_id"]
        if item_id not in existing_item_ids:
            new_docs.append(doc)
    print(f"  New/modified items: {len(new_docs)}")

    if not new_docs:
        print("\nNo new items to sync. Done.")
        return {"added": 0, "skipped": len(docs), "total_chunks": len(existing)}

    # 4. 切分 + 嵌入
    print(f"\n[3/4] Chunking new items (size={chunk_size}, overlap={chunk_overlap})...")
    chunks = chunk_docs(new_docs, chunk_size, chunk_overlap)
    print(f"  Produced {len(chunks)} chunks")

    print(f"\n[4/4] Embedding and storing...")
    emb = get_embeddings()
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    col = client.get_collection(CHROMA_COLLECTION)

    batch_size = 32
    current_count = col.count()
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["text"] for c in batch]
        ids = [f"kj_{current_count + j}" for j in range(i, i + len(batch))]
        metadatas = [{k: str(v) for k, v in c["metadata"].items()} for c in batch]

        vectors = emb.embed_documents(texts)
        col.add(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)

        pct = min(100, (i + batch_size) / len(chunks) * 100)
        print(f"  {min(i + batch_size, len(chunks))}/{len(chunks)} ({pct:.0f}%)")

    final_count = col.count()
    print(f"\nSync complete: {len(existing)} existing + {len(chunks)} new = {final_count} total")

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
```

- [ ] **Step 2: 验证提取逻辑**

```bash
cd portfolio-app && python -c "
from services.knowledge_sync import extract_docs, sync_status
docs = extract_docs()
print(f'Extracted {len(docs)} docs')
status = sync_status()
print(f'Status: {status}')
"
```

Expected: 显示提取了 ~123 个文档，pending_items > 0

- [ ] **Step 3: 执行首次同步**

```bash
cd portfolio-app && MODELS_DIR="D:/models" python -c "
from services.knowledge_sync import sync_knowledge_to_chroma
result = sync_knowledge_to_chroma()
print(result)
"
```

Expected: added > 0, total_chunks > 3724

- [ ] **Step 4: Commit**

```bash
git add portfolio-app/services/knowledge_sync.py
git commit -m "feat: JSON知识库→ChromaDB增量同步服务"
```

---

### Task 2: 构建脚本扩展 — 支持 JSON 数据源

**Files:**
- Modify: `portfolio-app/scripts/build_vector_db.py:28-55` (load_documents 函数)
- Modify: `portfolio-app/config.py:35-39` (KNOWLEDGE_SOURCES)

**Purpose:** 让 `build_vector_db.py` 的全量构建也能包含 JSON 知识库内容，新增 `--include-json` 参数。

- [ ] **Step 1: 扩展 load_documents 支持 JSON 源**

修改 `build_vector_db.py`，在 `load_documents` 函数末尾增加 JSON 处理逻辑：

在 `load_documents` 函数 `return docs` 之前添加：

```python
    # 也加载 data/knowledge/*.json (排除 insights.json)
    json_dir = Path(__file__).parent.parent / "data" / "knowledge"
    if json_dir.exists():
        from services.knowledge_sync import extract_docs, chunk_docs
        json_docs = extract_docs()
        for jd in json_docs:
            docs.append({
                "text": jd["text"],
                "metadata": {**jd["metadata"], "source_type": "knowledge_json"},
            })
        print(f"  [+] Loaded {len(json_docs)} items from data/knowledge/*.json")
```

- [ ] **Step 2: 验证全量构建包含 JSON**

```bash
cd portfolio-app && MODELS_DIR="D:/models" python scripts/build_vector_db.py --dry-run 2>&1 | grep "knowledge_json"
```

Expected: 显示加载了 JSON 条目数

- [ ] **Step 3: Commit**

```bash
git add portfolio-app/scripts/build_vector_db.py
git commit -m "feat: build_vector_db 支持 JSON 知识库数据源"
```

---

### Task 3: 服务器启动自动检测 + API 端点

**Files:**
- Create: `portfolio-app/routes/api_sync.py`
- Modify: `portfolio-app/server.py` (注册 blueprint)

**Purpose:** 服务器启动时检测未同步的 JSON 知识，提供 `POST /api/knowledge/sync` 手动触发端点。

- [ ] **Step 1: 创建 API 路由**

Create `routes/api_sync.py`:

```python
"""知识库同步 API"""
from flask import Blueprint, jsonify
from services.knowledge_sync import sync_knowledge_to_chroma, sync_status, needs_sync

sync_bp = Blueprint("sync", __name__, url_prefix="/api")


@sync_bp.route("/knowledge/sync/status", methods=["GET"])
def get_sync_status():
    """获取 JSON→ChromaDB 同步状态"""
    try:
        status = sync_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e), "needs_sync": False}), 500


@sync_bp.route("/knowledge/sync", methods=["POST"])
def trigger_sync():
    """手动触发增量同步"""
    try:
        result = sync_knowledge_to_chroma()
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
```

- [ ] **Step 2: 在 server.py 注册**

在 `server.py` 添加：
```python
from routes.api_sync import sync_bp
# 在 blueprint 注册循环中加入 sync_bp
```

- [ ] **Step 3: 启动时检查**

在 `server.py` 的 `if __name__ == "__main__":` 之前或 `create_app()` 中，加一个非阻塞检查（仅打印日志，不阻塞启动）：

```python
def _check_knowledge_sync_on_startup():
    """启动时检查知识库同步状态（非阻塞）"""
    try:
        from services.knowledge_sync import sync_status
        status = sync_status()
        if status["needs_sync"]:
            print(f"[sync] 发现 {status['pending_items']} 个未向量化的 JSON 条目")
            print(f"[sync] 领域: {status['pending_domains']}")
            print(f"[sync] POST /api/knowledge/sync 可触发同步")
    except Exception:
        pass  # 静默失败，不阻塞启动
```

- [ ] **Step 4: 启动服务器验证**

```bash
cd portfolio-app && DEEPSEEK_API_KEY="<your-api-key>" MODELS_DIR="D:/models" python server.py
# 检查启动日志是否有 [sync] 提示
# curl http://localhost:5000/api/knowledge/sync/status
```

Expected: `{"needs_sync": true, "pending_items": >0}`

- [ ] **Step 5: Commit**

```bash
git add portfolio-app/routes/api_sync.py portfolio-app/server.py
git commit -m "feat: 知识库同步API + 启动自动检测"
```

---

### Task 4: 混合检索 (BM25 + 向量)

**Files:**
- Modify: `portfolio-app/services/rag_service.py`

**Purpose:** 在现有向量检索基础上加入 BM25 关键词检索，加权融合提升中文查询召回率。这是 roadmap 2.1 P1。

- [ ] **Step 1: 安装依赖**

```bash
pip install rank_bm25 jieba
```

- [ ] **Step 2: 在 rag_service.py 添加 BM25 检索函数**

在 `rag_service.py` 顶部添加 import：

```python
import jieba
from rank_bm25 import BM25Okapi
```

在 `_do_search` 函数之后、`search` 函数之前添加：

```python

# BM25 检索器缓存（按 collection 实例缓存）
_bm25_cache = {}


def _get_bm25(col):
    """构建或获取 BM25 检索器（缓存）"""
    col_id = id(col)
    if col_id not in _bm25_cache:
        all_docs = col.get()["documents"]
        tokenized = [list(jieba.cut(doc)) for doc in all_docs]
        _bm25_cache[col_id] = (BM25Okapi(tokenized), all_docs)
    return _bm25_cache[col_id]


def _bm25_search(col, query, k=10):
    """BM25 关键词检索"""
    bm25, all_docs = _get_bm25(col)
    tokenized_query = list(jieba.cut(query))
    scores = bm25.get_scores(tokenized_query)
    # 取 top-k
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    results = []
    for i in top_indices:
        meta = col.get(ids=[col.get()["ids"][i]])["metadatas"][0]
        results.append({
            "text": all_docs[i],
            "source": meta.get("filename", "?"),
            "title": meta.get("title", "?"),
            "arxiv_id": meta.get("arxiv_id", ""),
            "bm25_score": float(scores[i]),
            "similarity": 0.0,  # BM25 无向量相似度
        })
    return results


def _fusion_results(vector_results, bm25_results, vector_weight=0.6):
    """加权融合向量检索和 BM25 检索结果
    
    策略: RRF (Reciprocal Rank Fusion) 变体
    - 每个结果按其在不同检索器中的排名加权
    - 向量检索权重更高（语义理解），BM25 补充关键词匹配
    """
    combined = {}
    
    # 向量结果
    for rank, r in enumerate(vector_results):
        key = r["text"][:100]  # 用前100字符做去重key
        score = r["similarity"] * vector_weight + (1.0 / (rank + 1)) * 0.1
        combined[key] = {"rank": rank, "score": score, **r}
    
    # BM25 结果
    for rank, r in enumerate(bm25_results):
        key = r["text"][:100]
        score = (1.0 / (rank + 1)) * (1 - vector_weight)
        if key in combined:
            combined[key]["score"] += score
            combined[key].update({"bm25_score": r["bm25_score"]})
        else:
            r["score"] = score
            combined[key] = r
    
    # 按融合分数排序
    sorted_results = sorted(combined.values(), key=lambda x: x["score"], reverse=True)
    return sorted_results
```

- [ ] **Step 3: 修改 search 函数启用混合检索**

在 `search` 函数末尾 `return _dynamic_filter(chunks, ratio=dynamic_ratio)` 之前，添加混合检索逻辑。添加 `use_hybrid` 参数：

```python
def search(query, k=10, dynamic_ratio=0.85, use_hybrid=True):
```

在 `_dynamic_filter` 调用之前：

```python
    # 混合检索: 向量 + BM25
    if use_hybrid:
        try:
            bm25_results = _bm25_search(col, query, k=k)
            chunks = _fusion_results(chunks, bm25_results, vector_weight=0.6)
        except Exception:
            pass  # BM25 失败时回退到纯向量结果
```

- [ ] **Step 4: 清除 BM25 缓存机制**

为了避免 ChromaDB 更新后 BM25 缓存过期，在 `sync_knowledge_to_chroma` 末尾添加缓存失效：

在 `knowledge_sync.py` 中：
```python
def invalidate_bm25_cache():
    """清除 BM25 缓存（ChromaDB 更新后调用）"""
    from services.rag_service import _bm25_cache
    _bm25_cache.clear()
```

- [ ] **Step 5: 验证混合检索效果**

```bash
cd portfolio-app && MODELS_DIR="D:/models" python -c "
from services.rag_service import search
# 测试中文查询
results = search('什么是自注意力机制？', k=5, use_hybrid=True)
for i, r in enumerate(results):
    print(f'[{i+1}] {r[\"title\"][:50]} | sim={r.get(\"similarity\",0):.3f} bm25={r.get(\"bm25_score\",0):.1f} score={r[\"score\"]:.3f}')
"
```

- [ ] **Step 6: Commit**

```bash
git add portfolio-app/services/rag_service.py portfolio-app/services/knowledge_sync.py
git commit -m "feat: BM25+向量混合检索 提升中文召回"
```

---

### Task 5: RAG 评测对比 (Before/After)

**Files:**
- No code changes, just run evals and record results

**Purpose:** 量化改进效果，生成版本对比数据。

- [ ] **Step 1: 重新运行 RAG 评测**

```bash
cd portfolio-app && MODELS_DIR="D:/models" python scripts/eval_rag.py --output data/eval/rag_v2.json 2>&1
```

- [ ] **Step 2: 对比 v1 vs v2**

```bash
cd portfolio-app && python -c "
import json
v1 = json.load(open('data/eval/rag_baseline.json'))
v2 = json.load(open('data/eval/rag_v2.json'))
s1 = v1['summary']
s2 = v2['summary']
print(f'指标           |  v1(before)  |  v2(after)  |  变化')
print(f'{"-"*55}')
h1 = s1['hit_rate@5']; h2 = s2['hit_rate@5']
print(f'Hit Rate@5     |  {h1:.2%}      |  {h2:.2%}      |  {h2-h1:+.2%}')
m1 = s1['mrr']; m2 = s2['mrr']
print(f'MRR            |  {m1:.4f}     |  {m2:.4f}     |  {m2-m1:+.4f}')
r1 = s1['avg_relevant@5']; r2 = s2['avg_relevant@5']
print(f'Avg Relevant@5 |  {r1:.2f}      |  {r2:.2f}      |  {r2-r1:+.2f}')
t1 = s1['avg_latency_ms']; t2 = s2['avg_latency_ms']
print(f'Avg Latency    |  {t1:.0f}ms     |  {t2:.0f}ms     |  {t2-t1:+.0f}ms')
"
```

- [ ] **Step 3: Commit eval results**

```bash
git add portfolio-app/data/eval/rag_v2.json
git commit -m "eval: RAG v2 混合检索评测结果"
```

---

### Task 6: 文档更新 — 版本对比

**Files:**
- Modify: `portfolio-app/docs/optimization-roadmap.md`
- Modify: `portfolio-app/docs/dataset-doc.md`
- Modify: `portfolio-app/docs/debug-report.md`

**Purpose:** 记录改进过程，形成可见的版本演进。

- [ ] **Step 1: 更新 optimization-roadmap.md**

将 Task 1-5 涉及的项目标注为完成：
```markdown
- [x] **P1** 混合检索 (BM25 + 向量) — (2026-06-04)
- [x] **P3** 增量更新 — (2026-06-04) knowledge_sync.py 实现
- [x] **新增** JSON→ChromaDB 通道 — knowledge_sync.py + API 端点 (2026-06-04)
```

- [ ] **Step 2: 更新 dataset-doc.md — 添加向量化状态表**

```markdown
## JSON 知识库向量化状态

| 文件 | 条目数 | 向量化状态 | 同步时间 |
|------|--------|-----------|----------|
| agent-development.json | 36 | ✅ | 2026-06-04 |
| ai-curriculum.json | 35 | ✅ | 2026-06-04 |
| python-basics.json | 17 | ✅ | 2026-06-04 |
| finance-basics.json | 14 | ✅ | 2026-06-04 |
| edge-detection.json | 18 | ✅ | 2026-06-04 |
| imported.json | 8 | ✅ | 2026-06-04 |
| insights.json | 55 | ❌ (方法论卡片，不向量化) | - |
```

- [ ] **Step 3: 更新 debug-report.md — 记录已解决问题**

在文件末尾添加：
```markdown
## 11. JSON 知识库无法被 Agent 检索 (2026-06-04 已解决)

**现象:** Agent 调用 search_knowledge 只能搜到 知识库/导出/ 和 精炼笔记/ 的内容，data/knowledge/*.json 的 123 个条目完全不可检索。

**根因:** 两套独立系统 — JSON 文件供 knowledge_loader.py 做浏览器展示，ChromaDB 向量库独立由 build_vector_db.py 从 MD/PDF 构建。缺少同步通道。

**解决方案:**
1. 新增 services/knowledge_sync.py: 从 JSON 提取条目文本 → 增量嵌入 ChromaDB
2. 服务器启动自动检测，API 端点手动触发
3. build_vector_db.py 全量构建也包含 JSON 源

**效果:** Agent 现在可以检索所有 JSON 知识库内容。
```

- [ ] **Step 4: Commit docs update**

```bash
git add portfolio-app/docs/
git commit -m "docs: 更新路线图/数据集/排错文档 — JSON→ChromaDB通道完成"
```

---

### Task 7: 端到端验证

**Files:** No code changes

**Purpose:** 验证完整链路：JSON 知识 → ChromaDB → Agent 检索。

- [ ] **Step 1: 启动服务器**

```bash
cd portfolio-app && DEEPSEEK_API_KEY="<your-api-key>" MODELS_DIR="D:/models" python server.py
```

- [ ] **Step 2: 测试 Agent 检索新的 JSON 知识**

```bash
curl -X POST http://localhost:5000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"请搜索知识库，解释一下ReAct循环的核心原理是什么？", "session_id":"test_sync"}'
```

Expected: Agent 调用 search_knowledge，返回包含 agent-development.json 内容的回复。

- [ ] **Step 3: 测试中文混合检索**

```bash
curl -X POST http://localhost:5000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Transformer中的自注意力机制是什么？", "session_id":"test_sync2"}'
```

Expected: 比之前更好的中文检索结果。

- [ ] **Step 4: 测试同步 API**

```bash
curl http://localhost:5000/api/knowledge/sync/status
# 应返回 needs_sync: false (已全部同步)
```

---

## Execution Order

```
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7
```

Tasks 1-2 可并行（不同文件），Tasks 5-6 在 4 完成后做。

## Success Criteria

- [ ] Agent 搜索 "ReAct循环原理" 能命中 agent-development.json 内容
- [ ] Agent 搜索 "AI学习路线" 能命中 ai-curriculum.json 内容
- [ ] RAG Hit Rate@5 ≥ 80% (vs baseline 76.67%)
- [ ] 中文查询 (如"自注意力机制") 命中率提升
- [ ] `POST /api/knowledge/sync` 端点可用
- [ ] 服务器启动日志显示同步状态
- [ ] 文档已更新为 before/after 对比格式
