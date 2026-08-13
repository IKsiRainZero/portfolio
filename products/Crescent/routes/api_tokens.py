"""Token usage API routes"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")


@router.get("/tokens/dashboard")
async def token_dashboard(request: Request):
    try:
        days = int(request.query_params.get("days", "7"))
        days = max(1, min(days, 90))
    except (ValueError, TypeError):
        days = 7

    from services.token_tracker import get_dashboard_stats
    try:
        stats = get_dashboard_stats(days=days)
        return stats
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/tokens/refresh")
async def token_refresh(request: Request):
    from services.token_tracker import invalidate_cache
    invalidate_cache()
    return {"ok": True, "message": "缓存已清除，下次请求将重新扫描"}


@router.get("/tokens/config")
async def token_config(request: Request):
    from pathlib import Path
    from config import USER_DATA_DIR
    token_dir = Path(USER_DATA_DIR) / "token_logs"
    has_data = token_dir.exists() and any(token_dir.glob("*.jsonl"))
    return {
        "available": has_data,
        "token_log_path": str(token_dir) if has_data else None,
    }
