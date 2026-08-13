"""Knowledge API routes"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from services.knowledge_loader import list_sets, load_set, search
import json
import re

router = APIRouter(prefix="/api")

# CWE-22 防护: set_id 仅允许字母数字、连字符、下划线、中文
_SET_ID_PATTERN = re.compile(r'^[\w一-鿿-]+$')


def _validate_set_id(set_id):
    """CWE-22: 路径遍历防护 — 拒绝含 ../ ..\\ / \\ 的输入"""
    if not set_id or len(set_id) > 64:
        return False
    if '..' in set_id or '/' in set_id or '\\' in set_id:
        return False
    return bool(_SET_ID_PATTERN.match(set_id))


@router.post("/knowledge/ingest")
async def knowledge_ingest(request: Request):
    """SSE 流式知识摄取 — 支持取消"""
    data = await request.json()
    urls = data.get("urls", [])
    query = data.get("query", "").strip()
    session_id = data.get("session_id", "ingest_default")

    if not urls:
        return JSONResponse(content={"error": "请提供至少一个 URL"}, status_code=400)

    from services.knowledge_ingest import ingest_pipeline, _ingest_cancel_events
    import threading

    # 创建取消事件
    cancel_ev = threading.Event()
    _ingest_cancel_events[session_id] = cancel_ev

    def generate():
        try:
            for event in ingest_pipeline(urls, query, cancel_event=cancel_ev):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            _ingest_cancel_events.pop(session_id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/knowledge/ingest/search")
async def knowledge_ingest_search(request: Request):
    """搜索 + 摄取 SSE — 先联网搜索，再自动摄取结果"""
    data = await request.json()
    query = data.get("query", "").strip()

    if not query:
        return JSONResponse(content={"error": "请输入搜索关键词"}, status_code=400)

    from services.knowledge_ingest import search_and_ingest

    def generate():
        try:
            for event in search_and_ingest(query):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/knowledge/search/web")
async def knowledge_search_web(request: Request):
    """轻量联网搜索 — 仅返回 URL+标题，不进入摄入管道"""
    data = await request.json()
    query = data.get("query", "").strip()
    if not query or len(query) < 2:
        return JSONResponse(content={"error": "请输入至少 2 个字符的搜索词"}, status_code=400)

    from services.knowledge_ingest import _search_web_with_titles
    try:
        results = _search_web_with_titles(query)
        return {"query": query, "results": results, "count": len(results)}
    except Exception as e:
        return JSONResponse(content={"error": f"搜索失败: {str(e)}"}, status_code=502)


@router.post("/knowledge/ingest/cancel")
async def knowledge_ingest_cancel(request: Request):
    """取消正在进行的摄入管道"""
    try:
        data = await request.json()
    except Exception:
        data = {}
    session_id = data.get("session_id", "ingest_default")
    from services.knowledge_ingest import cancel_ingest
    ok = cancel_ingest(session_id)
    return {"ok": ok, "message": "取消信号已发送" if ok else "未找到活跃的摄入会话"}


@router.get("/knowledge/sets")
async def get_sets(request: Request):
    try:
        sets = list_sets()
        return {"sets": sets}
    except Exception as e:
        return JSONResponse(content={"error": str(e), "sets": []}, status_code=500)


@router.get("/knowledge/search")
async def search_knowledge(request: Request):
    q = request.query_params.get("q", "")
    if not q or len(q) < 2:
        return {"results": []}
    results = search(q)
    return {"results": results}


@router.get("/knowledge/source/{name:path}")
async def knowledge_source(name: str, request: Request):
    """Return chunks from a specific source file"""
    import chromadb
    from config import CHROMA_PATH, CHROMA_COLLECTION
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        col = client.get_collection(CHROMA_COLLECTION)
        results = col.get(where={"filename": name}, limit=5,
                         include=["documents", "metadatas"])
    except Exception:
        return {"title": name, "type": "未知", "text": "向量库查询失败", "chunks": 0}

    if not results["ids"]:
        return {"title": name, "type": "未知", "text": "未找到该来源的详细内容", "chunks": 0}

    return {
        "title": results["metadatas"][0].get("title", name) if results["metadatas"] else name,
        "type": results["metadatas"][0].get("source", "未知") if results["metadatas"] else "未知",
        "text": results["documents"][0][:600] if results["documents"] else "",
        "chunks": len(results["ids"]),
    }


@router.get("/knowledge/{set_id}")
async def get_set(set_id: str, request: Request):
    if not _validate_set_id(set_id):
        return JSONResponse(content={"error": "无效的知识库 ID"}, status_code=400)
    data = load_set(set_id)
    if data is None:
        return JSONResponse(content={"error": "知识库未找到", "items": []}, status_code=404)
    return data


@router.get("/knowledge/pipeline/status")
async def pipeline_status(request: Request):
    """返回知识管道各阶段状态和统计数据"""
    from pathlib import Path
    import chromadb, os
    from config import CHROMA_PATH, CHROMA_COLLECTION, BASE_DIR

    stages = {
        "documents": {"count": 0, "last_import": None},
        "cleaning": {"filtered": 0, "last_run": None},
        "chunking": {"total_chunks": 0, "avg_size": 0, "chunk_size": 500, "overlap": 150},
        "embedding": {"model": "bge-m3", "dim": 1024},
        "vector_db": {"collection": CHROMA_COLLECTION, "total_vectors": 0, "disk_mb": 0},
        "retrieval": {"hybrid": True, "reranker": "bge-reranker-large", "hit_rate_7d": 0.0},
        "generation": {"model": "deepseek-chat", "avg_latency_ms": 0},
    }

    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        col = client.get_collection(CHROMA_COLLECTION)
        count = col.count()
        stages["vector_db"]["total_vectors"] = count
        stages["chunking"]["total_chunks"] = count
        if count > 0:
            all_docs = col.get()["documents"]
            total_len = sum(len(d) for d in all_docs)
            stages["chunking"]["avg_size"] = total_len // count
    except Exception:
        pass

    try:
        chroma_dir = Path(CHROMA_PATH)
        total_size = sum(f.stat().st_size for f in chroma_dir.rglob("*") if f.is_file())
        stages["vector_db"]["disk_mb"] = round(total_size / (1024*1024), 1)
    except Exception:
        pass

    kb_root = BASE_DIR.parent / "知识库"
    if kb_root.exists():
        md_count = len(list(kb_root.rglob("*.md")))
        stages["documents"]["count"] = md_count

    sync_log = BASE_DIR / "data" / "user_data" / "sync_log.json"
    last_sync = None
    try:
        if sync_log.exists():
            log_data = json.loads(sync_log.read_text(encoding="utf-8"))
            entries = log_data.get("entries", [])
            if entries:
                last_sync = entries[-1].get("time")
    except Exception:
        pass

    try:
        from services.agent_logger import list_recent_events
        recent = list_recent_events(days=7)
        searches = [e for e in recent if e.get("event_type") == "search"]
        if searches:
            hits = sum(1 for s in searches if s.get("hit"))
            stages["retrieval"]["hit_rate_7d"] = round(hits / len(searches), 2)
    except Exception:
        pass

    return {
        "stages": stages,
        "last_sync": last_sync,
        "health": "ok" if stages["vector_db"]["total_vectors"] > 0 else "empty",
    }


# ── v4 调研管道端点 ──

import threading
from services.pipeline.task_store import get_task_store


@router.post("/pipeline/research")
async def pipeline_research_start(req: Request):
    """启动调研管道。POST body: {query, max_results?} 返回 task_id 用于轮询。"""
    body = await req.json()
    query = body.get("query", "")
    max_results = max(1, min(int(body.get("max_results", 10)), 20))
    if not query:
        return {"status": "error", "error": "query is required"}

    store = get_task_store()
    task_id = store.create(query, max_results)

    def _run_pipeline():
        from services.pipeline.e2e import build_research_pipeline
        from services.pipeline.types import PipelineSpec, StepSpec
        from dataclasses import asdict

        store.update(task_id, status="running")
        try:
            orch = build_research_pipeline()
            spec = PipelineSpec(steps=[
                StepSpec(step_name="S1", enabled=True),
                StepSpec(step_name="S2", enabled=True),
                StepSpec(step_name="S3_search", enabled=True, config={"max_results": max_results}),
                StepSpec(step_name="S3_fetch", enabled=True),
                StepSpec(step_name="S4", enabled=True, config={"operators": ["relation", "sufficiency"]}),
                StepSpec(step_name="S5", enabled=True),
            ])
            result = orch.run(query=query, spec=spec)

            def _serialize(obj):
                if hasattr(obj, "__dataclass_fields__"):
                    return asdict(obj)
                if isinstance(obj, dict):
                    return {k: _serialize(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_serialize(item) for item in obj]
                return obj

            store.update(
                task_id,
                status=result["status"],
                outputs=_serialize(result.get("outputs", {})),
                trace=result.get("trace", []),
            )
            if result["status"] == "needs_human":
                store.update(task_id, status="needs_human",
                             outputs={"question": result.get("question")})
        except Exception as e:
            store.update(task_id, status="error", error=str(e))

    threading.Thread(target=_run_pipeline, daemon=True).start()
    return {"task_id": task_id, "status": "started"}


@router.get("/pipeline/research/{task_id}")
async def pipeline_research_status(task_id: str):
    """轮询管道状态。返回 {status, outputs?, trace?, error?}"""
    store = get_task_store()
    task = store.get(task_id)
    if task is None:
        return {"status": "error", "error": "task not found or expired"}
    return {
        "status": task["status"],
        "outputs": task.get("outputs"),
        "trace": task.get("trace"),
        "error": task.get("error"),
    }
