"""知识摄取管道 — 搜索→抓取→清洗→切分→嵌入→入库，SSE 流式推送每阶段进度"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import re
import hashlib
import threading
from typing import Generator, List, Dict, Any
from config import CHUNK_SIZE as _CFG_CHUNK_SIZE, CHUNK_OVERLAP as _CFG_CHUNK_OVERLAP

# 模块级取消事件 — key 为 session_id
_ingest_cancel_events: Dict[str, threading.Event] = {}


def cancel_ingest(session_id: str) -> bool:
    """设置取消信号，返回是否找到对应事件"""
    ev = _ingest_cancel_events.get(session_id)
    if ev:
        ev.set()
        return True
    return False


def _clean_text(text: str) -> str:
    """清洗：去页眉页脚、图表描述、过短段落"""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 过滤 arXiv 页眉
        if re.match(r'^arXiv:\d+\.\d+v\d+', line):
            continue
        # 过滤图表描述
        if re.match(r'^(Figure|Table|Fig\.)\s*\d+', line):
            continue
        # 过短行（< 15 chars）可能是导航/页脚
        if len(line) < 15:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _chunk_text(text: str, chunk_size: int = _CFG_CHUNK_SIZE, overlap: int = _CFG_CHUNK_OVERLAP) -> List[str]:
    """固定长度切分（与 build_vector_db.py 保持一致）"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if len(chunk) >= 100:  # 最少 100 字才算有效 chunk
            chunks.append(chunk)
        start = end - overlap
    return chunks


def ingest_pipeline(urls: List[str], query: str = "",
                    cancel_event: threading.Event = None) -> Generator[Dict[str, Any], None, None]:
    """
    SSE event generator for the ingest pipeline.
    Yields: {"type": "stage", "stage": "...", ...} or {"type": "done", ...}
    """
    if cancel_event is None:
        cancel_event = threading.Event()  # dummy — never set
    # Stage 1: Fetch
    from scrapling.fetchers import Fetcher
    from markitdown import MarkItDown

    fetched = []
    total = len(urls)
    for i, url in enumerate(urls):
        yield {"type": "stage", "stage": "fetching", "url": url, "progress": f"{i+1}/{total}"}
        try:
            resp = Fetcher.get(url, timeout=20)
            md = MarkItDown()
            result = md.convert(io.BytesIO(resp.body))
            text = result.text_content
            title = resp.css('title::text').get() or result.title or url
            fetched.append({"url": url, "title": title, "text": text or ""})
        except Exception as e:
            fetched.append({"url": url, "title": url, "text": "", "error": str(e)})

    if not fetched or all(not f["text"] for f in fetched):
        yield {"type": "error", "message": "所有 URL 抓取失败，请检查链接是否可访问"}
        return

    # Stage 2: Clean
    yield {"type": "stage", "stage": "cleaning", "chunks_raw": len(fetched)}
    filtered_count = 0
    for f in fetched:
        raw_len = len(f["text"])
        f["text"] = _clean_text(f["text"])
        if len(f["text"]) < raw_len * 0.3:
            filtered_count += 1

    # Stage 3: Chunk
    all_chunks = []
    for f in fetched:
        if f["text"]:
            chunks = _chunk_text(f["text"])
            for c in chunks:
                all_chunks.append({"text": c, "source": f["url"], "title": f["title"]})
    yield {"type": "stage", "stage": "chunking", "total_chunks": len(all_chunks), "filtered": filtered_count}

    if not all_chunks:
        yield {"type": "error", "message": "清洗后无有效内容"}
        return

    # Stage 4: Embed + Stage 5: Store
    import chromadb
    from sentence_transformers import SentenceTransformer
    from config import CHROMA_PATH, CHROMA_COLLECTION, EMBEDDING_MODEL

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    col = client.get_collection(CHROMA_COLLECTION)

    emb = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True, device="cpu")

    batch_size = 10
    saved = 0
    preview = []

    for batch_start in range(0, len(all_chunks), batch_size):
        if cancel_event.is_set():
            yield {"type": "cancelled", "saved": saved, "total": len(all_chunks)}
            return
        batch = all_chunks[batch_start:batch_start + batch_size]
        yield {"type": "stage", "stage": "embedding", "current": saved, "total": len(all_chunks)}

        ids = []
        docs = []
        metas = []
        texts = []
        for chunk in batch:
            cid = hashlib.md5(chunk["text"].encode()).hexdigest()[:16]
            ids.append(f"ingest_{cid}")
            docs.append(chunk["text"])
            metas.append({"title": chunk["title"], "filename": chunk["source"], "source": "ingested"})
            texts.append(chunk["text"])

        vectors = emb.encode(texts, normalize_embeddings=True).tolist()
        col.add(ids=ids, documents=docs, metadatas=metas, embeddings=vectors)
        saved += len(batch)

        if len(preview) < 5:
            for chunk in batch[:5 - len(preview)]:
                preview.append({"text": chunk["text"][:200], "source": chunk["source"]})

    # Persist
    try:
        client._system.stop()
    except Exception:
        pass

    yield {"type": "stage", "stage": "storing", "saved": saved}

    # Stage 6: Verify
    yield {"type": "stage", "stage": "verifying", "retrievable": saved > 0}

    yield {"type": "done", "added": saved, "preview": preview[:5], "query": query}


def _search_web(query: str, max_results: int = 10) -> list:
    """多后端联网搜索 — cn.bing.com 主 + ddgs 辅，适配中国网络环境"""
    import re
    import requests

    urls = []
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    # 后端 1: cn.bing.com (中国可达, 英文+中文结果)
    try:
        r = requests.get("https://cn.bing.com/search",
                         params={"q": query, "count": max_results},
                         headers={"User-Agent": ua}, timeout=15)
        r.encoding = "utf-8"
        # 提取含路径的完整 URL (>= 4 个 / 即 https://domain/path)
        hrefs = re.findall(r'href="(https?://[^"]+)"', r.text)
        for url in hrefs:
            url = url.strip()
            keep = ("bing.com" not in url and "microsoft.com" not in url
                    and url.startswith("http") and url.count("/") >= 4)
            if keep and url not in urls:
                urls.append(url)
            if len(urls) >= max_results:
                break
    except Exception:
        pass

    # 后端 2: 搜狗 (备用)
    if not urls:
        try:
            r = requests.get("https://www.sogou.com/web",
                             params={"query": query},
                             headers={"User-Agent": ua}, timeout=15)
            r.encoding = "utf-8"
            found = re.findall(r'<a[^>]*href="(https?://[^"]+)"[^>]*id="[^"]*result', r.text)
            for url in found:
                url = url.strip()
                if url.startswith("http") and "sogou.com" not in url:
                    if url not in urls:
                        urls.append(url)
                    if len(urls) >= max_results:
                        break
        except Exception:
            pass

    return urls


def _search_web_with_titles(query: str, max_results: int = 10) -> list:
    """搜索 + 轻量抓取标题，返回 [{url, title}]，不进入 ingest 管道"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import requests as _requests

    urls = _search_web(query, max_results)
    if not urls:
        return []

    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    def _fetch_title(url):
        try:
            r = _requests.get(url, headers={"User-Agent": ua}, timeout=8)
            r.encoding = r.apparent_encoding or "utf-8"
            match = re.search(r'<title[^>]*>(.*?)</title>', r.text, re.IGNORECASE | re.DOTALL)
            title = match.group(1).strip() if match else url
            # 清理 HTML 实体 & 多余空白
            title = re.sub(r'<[^>]+>', '', title)
            title = re.sub(r'\s+', ' ', title).strip()
            return {"url": url, "title": title[:200]}
        except Exception:
            return {"url": url, "title": url}

    results = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(_fetch_title, u): u for u in urls}
        for f in as_completed(futures):
            results.append(f.result())

    # 保持原始顺序
    url_order = {u: i for i, u in enumerate(urls)}
    results.sort(key=lambda x: url_order.get(x["url"], 999))
    return results


def search_and_ingest(query: str) -> Generator[Dict[str, Any], None, None]:
    """Search web first, then feed results into ingest pipeline"""
    yield {"type": "stage", "stage": "searching", "query": query}

    urls = _search_web(query)

    if not urls:
        yield {"type": "error", "message": "搜索失败: 搜索引擎(cn.bing/搜狗)均不可达，请直接粘贴URL。"}
        return

    yield {"type": "stage", "stage": "search_done", "results": urls}

    # Feed into ingest pipeline
    yield from ingest_pipeline(urls, query)
