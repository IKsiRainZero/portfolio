"""知识库同步 API"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")


@router.get("/knowledge/sync/status")
async def get_sync_status(request: Request):
    """获取 JSON→ChromaDB 同步状态"""
    try:
        from services.knowledge_sync import sync_status  # lazy, needs chromadb
        status = sync_status()
        return status
    except Exception as e:
        return JSONResponse(content={"error": str(e), "needs_sync": False}, status_code=500)


@router.post("/knowledge/sync")
async def trigger_sync(request: Request):
    """手动触发增量同步"""
    try:
        from services.knowledge_sync import sync_knowledge_to_chroma  # lazy, needs chromadb
        result = sync_knowledge_to_chroma()
        return {"success": True, **result}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
