from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from services.progress_tracker import record, get_summary, get_dashboard
from services.srs_scheduler import review_card, get_daily_queue, get_study_plan, get_stats as srs_stats
import json
from config import DATA_DIR

router = APIRouter(prefix="/api")


@router.post("/progress/record")
async def record_progress(request: Request):
    try:
        entry = await request.json()
        if not entry:
            return JSONResponse(content={"error": "数据为空"}, status_code=400)
        data = record(entry)
        return {"ok": True, "events_count": len(data.get("events", []))}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/progress/summary")
async def get_progress_summary(request: Request):
    try:
        summary = get_summary()
        return summary
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/progress/dashboard")
async def get_dashboard_data(request: Request):
    """仪表盘聚合数据：stats + weak_areas + streak + last_active"""
    try:
        return get_dashboard()
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ── SRS 间隔重复接口 ──────────────────────────────────

@router.post("/srs/review")
async def srs_review(request: Request):
    """记录闪卡复习: {card_id, concept, category, rating (1-5)}"""
    data = await request.json() or {}
    required = ["card_id", "concept", "category", "rating"]
    if any(k not in data for k in required):
        return JSONResponse(content={"error": "缺少必填字段: card_id, concept, category, rating"}, status_code=400)
    if not 1 <= data["rating"] <= 5:
        return JSONResponse(content={"error": "评分必须在1-5之间"}, status_code=400)
    result = review_card(data["card_id"], data["concept"], data["category"], data["rating"])
    return result


@router.get("/srs/due")
async def srs_due(request: Request):
    """获取今日待复习队列"""
    due = get_daily_queue()
    return {"due": due, "count": len(due), "date": __import__("datetime").datetime.now().strftime("%Y-%m-%d")}


@router.get("/srs/plan")
async def srs_plan(request: Request):
    """生成今日学习计划"""
    try:
        f = DATA_DIR / "exercises" / "flashcards.json"
        cards = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    except (json.JSONDecodeError, IOError):
        cards = []

    try:
        f2 = DATA_DIR / "user_data" / "progress.json"
        prog = json.loads(f2.read_text(encoding="utf-8")) if f2.exists() else {}
    except (json.JSONDecodeError, IOError):
        prog = {}

    plan = get_study_plan(cards, prog.get("topic_performance", {}))
    return plan


@router.get("/srs/stats")
async def srs_plan_stats(request: Request):
    """SRS统计"""
    return srs_stats()
