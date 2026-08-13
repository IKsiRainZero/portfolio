"""
ReviewAgent API routes — DEPRECATED (Phase 4)

所有审查功能已迁移到 eval 系统:
  - /api/review/run    → POST /api/eval/cross-validate
  - /api/review/list   → GET  /api/eval/suggestions
  - /api/review/apply  → POST /api/eval/suggestions/<id>/apply
  - /api/review/reject → POST /api/eval/suggestions/<id>/reject
  - /api/review/stats  → GET  /api/eval/summary

旧端点仍然可用但将在 Phase 5 中移除。
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")

_DEPRECATION = "X-Deprecated: 此端点已迁移到 /api/eval/*, 参见 API 文档"


@router.post("/review/run")
async def run(request: Request):
    from services.review_agent import run_review
    try:
        result = run_review()
        if result.get("error"):
            return JSONResponse(content=result, status_code=500)
        return JSONResponse(
            content=result,
            headers={
                "X-Deprecated": "true",
                "X-Migration-Target": "POST /api/eval/cross-validate",
            },
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/review/list")
async def list_all(request: Request):
    from services.review_store import list_reviews
    limit = int(request.query_params.get("limit", "20"))
    reviews = list_reviews(limit)
    return JSONResponse(
        content={"reviews": reviews, "count": len(reviews)},
        headers={
            "X-Deprecated": "true",
            "X-Migration-Target": "GET /api/eval/suggestions",
        },
    )


@router.get("/review/{review_id}")
async def get_one(review_id: str, request: Request):
    from services.review_store import get_review
    review = get_review(review_id)
    if review is None:
        return JSONResponse(content={"error": "review not found"}, status_code=404)
    return review


@router.post("/review/{review_id}/apply")
async def apply_sugg(review_id: str, request: Request):
    data = await request.json() or {}
    si = data.get("suggestion_index", 0)
    from services.review_agent import apply_suggestion
    result = apply_suggestion(review_id, si)
    if result.get("error"):
        return JSONResponse(content=result, status_code=400)
    return JSONResponse(
        content=result,
        headers={
            "X-Deprecated": "true",
            "X-Migration-Target": "POST /api/eval/suggestions/<id>/apply",
        },
    )


@router.post("/review/{review_id}/reject")
async def reject_sugg(review_id: str, request: Request):
    data = await request.json() or {}
    si = data.get("suggestion_index", 0)
    from services.review_store import update_suggestion_status
    update_suggestion_status(review_id, si, "rejected")
    return JSONResponse(
        content={"ok": True},
        headers={
            "X-Deprecated": "true",
            "X-Migration-Target": "POST /api/eval/suggestions/<id>/reject",
        },
    )


@router.post("/review/{review_id}/rollback")
async def rollback_sugg(review_id: str, request: Request):
    data = await request.json() or {}
    si = data.get("suggestion_index", 0)
    from services.review_agent import rollback_suggestion
    result = rollback_suggestion(review_id, si)
    if result.get("error"):
        return JSONResponse(content=result, status_code=400)
    return result


@router.get("/review/stats")
async def stats(request: Request):
    from services.review_store import get_stats
    from services.review_memory import get_memory_state
    return JSONResponse(
        content={"reviews": get_stats(), "memory": get_memory_state()},
        headers={
            "X-Deprecated": "true",
            "X-Migration-Target": "GET /api/eval/summary",
        },
    )


@router.post("/review/evaluate")
async def evaluate(request: Request):
    from services.review_agent import evaluate_past_suggestions
    return {"evaluations": evaluate_past_suggestions()}
