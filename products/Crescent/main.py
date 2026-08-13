"""
Crescent FastAPI 入口 (Phase 3: 全栈 FastAPI async)
启动: uvicorn main:app --port 5000 --reload
"""
import os
import sys
import time
import json
from pathlib import Path
from contextlib import asynccontextmanager

sys.path.insert(0, str(Path(__file__).parent))

import config
from config import HOST, PORT, DEBUG, BASE_DIR, USER_DATA_DIR

USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── FastAPI ──
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.cache_size = 0  # 禁用 Jinja2 内存缓存，避免 Python 3.14 兼容性问题
templates.env.cache = None   # create_cache(0) = None, 但 __init__ 已创建 LRUCache(400), 需显式覆盖

# ══════════════════════════════════════════════
# ASGI 中间件
# ══════════════════════════════════════════════

class EvalTraceMiddleware(BaseHTTPMiddleware):
    """评估 Trace 钩子 — ASGI 中间件，等价于 @app.middleware"""
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/static"):
            return await call_next(request)
        try:
            from services.eval.trace_logger import start_trace, _trace_id_ctx
            trace_id = start_trace(
                name=request.url.path,
                kind="http_request",
                metadata={"method": request.method, "path": request.url.path},
            )
            request.state.eval_trace_id = trace_id
            request.state.eval_trace_start = time.time()
            _trace_id_ctx.set(trace_id)
        except Exception:
            pass

        response = await call_next(request)

        if hasattr(request.state, "eval_trace_id"):
            try:
                from services.eval.trace_logger import end_trace
                duration_ms = int((time.time() - request.state.eval_trace_start) * 1000)
                span_count = getattr(request.state, "eval_span_count", 0)
                end_trace(
                    trace_id=request.state.eval_trace_id,
                    duration_ms=duration_ms,
                    span_count=span_count,
                    status_code=response.status_code,
                )
            except Exception:
                pass
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口速率限制 — 委托 services.rate_limiter 共享状态"""
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")

        from services.rate_limiter import check_rate_limit
        allowed, retry_after = check_rate_limit(client_ip, path)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "请求过于频繁，请稍后重试", "retry_after": retry_after},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)


# ══════════════════════════════════════════════
# Lifespan
# ══════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — 轻量操作同步完成，重操作交后台线程
    from services.model_config import load_model_config
    mc = load_model_config()
    config.LLM_PROVIDER = mc.get("active_provider", config.LLM_PROVIDER)
    if config.LLM_PROVIDER == "local":
        config.LOCAL_MODEL_NAME = mc.get("active_model", config.LOCAL_MODEL_NAME)
    else:
        config.MODEL = mc.get("active_model", config.MODEL)

    key_file = config.USER_DATA_DIR / ".api_key"
    if key_file.exists():
        config.API_KEY = key_file.read_text().strip()

    from services.rate_limiter import apply_user_rate_limits as _apply_limits
    _apply_limits()

    import threading

    def _warmup_and_checks():
        import time as _time
        # RAG 预热（阻塞模型加载，在后台线程执行）
        try:
            from services.rag_service import _get_chroma
            _get_chroma()
            from services.llm_service import embeddings
            embeddings()
            print("  [OK] RAG 预热完成 (embedding + ChromaDB)")
        except Exception:
            pass
        try:
            from services.knowledge_sync import sync_status as _check_status
            status = _check_status()
            if status["needs_sync"]:
                print(f"[sync] 未向量化的 JSON 条目: {status['pending_items']}")
        except Exception:
            pass

        from services.eval import eval_engine
        try:
            eval_engine._seed_score_configs()
        except Exception:
            pass

        _time.sleep(5)
        try:
            from services.eval.llm_judge import start_worker
            start_worker()
        except Exception:
            pass

        _cycle = 0
        while True:
            _cycle += 1
            try:
                from services.review_agent import check_auto_trigger
                check_auto_trigger()
            except Exception:
                pass
            try:
                from services.eval.trace_logger import TraceContext
                from services.eval import eval_engine as ee
                with TraceContext(name="eval_orphan_cleanup", kind="scheduled_task"):
                    ee._cleanup_orphan_spans()
                with TraceContext(name="eval_effect_tracking", kind="scheduled_task"):
                    ee._effect_tracking_loop()
                with TraceContext(name="eval_data_completeness", kind="scheduled_task"):
                    ee._compute_data_completeness(window_hours=24)
                with TraceContext(name="eval_knowledge_health", kind="scheduled_task"):
                    ee._knowledge_health_check()
                with TraceContext(name="eval_error_patterns", kind="scheduled_task"):
                    ee._check_error_patterns(days=30)
                with TraceContext(name="eval_ingest_findings", kind="scheduled_task"):
                    ee._ingest_review_findings(window_hours=24)
                ee._daemon_heartbeat({})
            except Exception:
                pass
            if _cycle % 24 == 0:
                try:
                    from services.eval import eval_engine as ee2
                    ee2._run_prospective_detectors()
                except Exception:
                    pass
            if _cycle % 6 == 0:
                try:
                    from services.eval.meta_evaluator import run_all as run_meta
                    run_meta()
                except Exception:
                    pass
            _time.sleep(3600)

    threading.Thread(target=_warmup_and_checks, daemon=True).start()

    # L2 timer
    def _l2_loop():
        import json as _json
        from datetime import datetime
        log_file = Path(__file__).parent / "data" / "eval" / "meta_eval_l2.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        while True:
            time.sleep(7200)
            try:
                try:
                    from services.eval.meta_evaluator import run_l2_self_check
                    result = run_l2_self_check()
                except ImportError:
                    result = {"status": "pending"}
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(_json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, ensure_ascii=False) + "\n")
            except Exception:
                pass

    threading.Thread(target=_l2_loop, daemon=True).start()

    yield  # Server running

    # Shutdown — daemon threads die with process


# ══════════════════════════════════════════════
# App
# ══════════════════════════════════════════════

app = FastAPI(lifespan=lifespan)
app.add_middleware(EvalTraceMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

# Register DataSources
from services.data_sources.news_source import NewsSource as _NewsSource
from services.data_sources.local_file_source import LocalFileSource as _LocalFileSource
from services.data_sources import get_manager as _get_mgr
_get_mgr().register(_NewsSource())
_get_mgr().register(_LocalFileSource())

# Register routers
from routes.pages import router as pages_router
from routes.api_config import router as config_router
# ── deprecated (see archive/routes/) ──
# from routes.api_code import router as code_router
from routes.api_knowledge import router as knowledge_router
from routes.api_progress import router as progress_router
from routes.api_ai import router as ai_router
# from routes.api_exercises import router as exercises_router
# from routes.api_resume import router as resume_router
from routes.api_agent import router as agent_router
# from routes.api_interview import router as interview_router
from routes.api_import import router as import_router
from routes.api_sync import router as sync_router
from routes.api_source_trace import router as st_router
from routes.api_tokens import router as tokens_router
from routes.api_papers import router as papers_router
from routes.api_review import router as review_router
# from routes.api_eval import router as eval_router
# from routes.api_impressions import router as imp_router
from routes.api_workbench import router as workbench_router

app.include_router(pages_router)
app.include_router(config_router)
# ── deprecated (see archive/routes/) ──
# app.include_router(code_router)
app.include_router(knowledge_router)
app.include_router(progress_router)
app.include_router(ai_router)
# app.include_router(exercises_router)
# app.include_router(resume_router)
app.include_router(agent_router)
# app.include_router(interview_router)
app.include_router(import_router)
app.include_router(sync_router)
app.include_router(st_router)
app.include_router(tokens_router)
app.include_router(papers_router)
app.include_router(review_router)
# app.include_router(eval_router)
# app.include_router(imp_router)
app.include_router(workbench_router)

app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    print(r"""
  +====================================================+
  |    Portfolio App — 个人作品集 (FastAPI)              |
  |    求职备战工作台 v1.0                               |
  +====================================================+
  |  仪表盘:     http://localhost:5000                  |
  |  CV-Lab:     http://localhost:5001                   |
  +====================================================+
""")
    uvicorn.run("main:app", host=HOST, port=5000, reload=DEBUG)
