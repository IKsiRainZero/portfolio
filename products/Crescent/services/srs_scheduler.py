"""
间隔重复调度引擎 (Spaced Repetition Scheduler)
基于认知天性原则：1/3/7/30天间隔，低分短间隔，高分长间隔
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from config import USER_DATA_DIR

SRS_FILE = USER_DATA_DIR / "srs_schedule.json"

# 评分→间隔(天) 映射
INTERVALS = {1: 0, 2: 1, 3: 3, 4: 7, 5: 30}


def _load():
    if SRS_FILE.exists():
        try:
            return json.loads(SRS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {"cards": {}, "stats": {"total_reviews": 0, "streak_days": 0, "last_review_date": ""}}


def _save(data):
    SRS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SRS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def review_card(card_id: str, concept: str, category: str, rating: int) -> dict:
    """记录一次闪卡复习，返回下次复习日期和建议"""
    data = _load()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    interval = INTERVALS.get(rating, 1)
    next_date = (now + timedelta(days=interval)).strftime("%Y-%m-%d")

    if card_id not in data["cards"]:
        data["cards"][card_id] = {
            "concept": concept,
            "category": category,
            "reviews": 0,
            "ratings": [],
            "avg_rating": 0,
            "interval": 0,
            "next_review": today,
            "created": today,
        }

    card = data["cards"][card_id]
    card["reviews"] += 1
    card["ratings"].append({"date": today, "rating": rating})
    card["avg_rating"] = round(sum(r["rating"] for r in card["ratings"]) / len(card["ratings"]), 1)
    card["interval"] = interval
    card["next_review"] = next_date

    data["stats"]["total_reviews"] += 1
    data["stats"]["last_review_date"] = today

    _save(data)
    return {"next_review": next_date, "interval_days": interval, "reviews": card["reviews"]}


def get_daily_queue() -> list[dict]:
    """获取今日待复习队列（next_review <= today）"""
    data = _load()
    today = datetime.now().strftime("%Y-%m-%d")
    due = []
    for cid, card in data["cards"].items():
        if card["next_review"] <= today:
            due.append({"card_id": cid, **card})
    # 低分优先
    due.sort(key=lambda c: (c["avg_rating"], -c["reviews"]))
    return due


def get_study_plan(flashcard_pool: list[dict], mcq_topics: dict) -> dict:
    """生成今日学习计划"""
    due = get_daily_queue()
    due_ids = {d["card_id"] for d in due}

    # 待复习卡片
    review_today = due[:15]  # 最多15张

    # 新卡片推荐（未学的，优先弱项相关类别）
    reviewed_ids = set(_load()["cards"].keys())
    new_cards = [c for c in flashcard_pool if c.get("id", c.get("concept", "")) not in reviewed_ids]

    # 弱项类别优先
    weak_categories = set()
    for d in due:
        if d["avg_rating"] < 3:
            weak_categories.add(d["category"])

    new_cards.sort(key=lambda c: 0 if c.get("category", "") in weak_categories else 1)
    new_today = new_cards[:5]  # 每天最多5张新卡

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "review_due": len(due),
        "review_today": review_today,
        "new_today": new_today[:5],
        "total_cards": len(flashcard_pool),
        "reviewed_cards": len(reviewed_ids),
        "weak_categories": list(weak_categories),
    }


def get_stats() -> dict:
    """获取SRS统计"""
    data = _load()
    cards = data["cards"]
    if not cards:
        return {"total_cards_tracked": 0, "avg_rating": 0, "due_today": 0}

    ratings = [c["avg_rating"] for c in cards.values()]
    return {
        "total_cards_tracked": len(cards),
        "total_reviews": data["stats"]["total_reviews"],
        "avg_rating": round(sum(ratings) / len(ratings), 1),
        "due_today": len(get_daily_queue()),
        "last_review": data["stats"]["last_review_date"],
    }
