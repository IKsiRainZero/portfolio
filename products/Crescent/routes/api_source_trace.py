"""来源追溯 API — SSE 流式推送 6 步管道进度"""
import json as _json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(prefix="/api")


@router.post("/source-trace")
async def source_trace(request: Request):
    """SSE 流式来源追溯"""
    data = await request.json()
    content = (data.get("content") or "").strip()
    if not content:
        return JSONResponse(content={"error": "请输入要追溯的内容或链接"}, status_code=400)

    from services.source_tracer import trace_source

    def generate():
        try:
            for event in trace_source(content):
                yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'content': f'追溯过程出错: {str(e)}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
