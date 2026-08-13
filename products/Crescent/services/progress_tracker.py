"""学习进度追踪服务"""
import json
from datetime import datetime
from config import USER_DATA_DIR

PROGRESS_FILE = USER_DATA_DIR / "progress.json"


def _load():
    """加载进度数据，如果文件不存在则返回空结构"""
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "version": 1,
        "updated": "",
        "stats": {},
        "topic_performance": {},
        "events": [],
        "flashcard_ratings": {},
        "mock_interviews": [],
    }


def _save(data):
    """保存进度数据"""
    data["updated"] = datetime.now().isoformat()
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record(entry):
    """记录一次答题/练习事件
    entry: { type, item_id, topic, correct?, user_answer?, ... }
    """
    data = _load()

    # 添加事件
    event = {
        "timestamp": datetime.now().isoformat(),
        **entry,
    }
    data["events"].append(event)

    # 更新 topic 统计
    topic = entry.get("topic", "general")
    if topic not in data["topic_performance"]:
        data["topic_performance"][topic] = {"attempts": 0, "correct": 0, "accuracy": 0, "last_practiced": ""}

    tp = data["topic_performance"][topic]
    tp["attempts"] += 1
    if entry.get("correct"):
        tp["correct"] += 1
    tp["accuracy"] = round(tp["correct"] / tp["attempts"], 2) if tp["attempts"] > 0 else 0
    tp["last_practiced"] = datetime.now().strftime("%Y-%m-%d")

    # 更新统计
    stats = data["stats"]
    etype = entry.get("type", "")
    if etype == "mcq":
        stats["total_mcq_attempted"] = stats.get("total_mcq_attempted", 0) + 1
        if entry.get("correct"):
            stats["total_mcq_correct"] = stats.get("total_mcq_correct", 0) + 1
    elif etype == "code":
        stats["total_coding_attempts"] = stats.get("total_coding_attempts", 0) + 1
        if entry.get("passed"):
            stats["total_coding_passed"] = stats.get("total_coding_passed", 0) + 1
    elif etype == "flashcard":
        stats["total_flashcards_reviewed"] = stats.get("total_flashcards_reviewed", 0) + 1
    elif etype == "mock_interview":
        stats["total_mock_interviews"] = stats.get("total_mock_interviews", 0) + 1
    elif etype == "short_answer":
        stats["total_short_answers"] = stats.get("total_short_answers", 0) + 1
        if entry.get("score") is not None:
            prev_total = stats.get("total_short_score", 0)
            prev_count = stats.get("total_short_answers", 1)
            stats["total_short_score"] = prev_total + entry["score"]
    elif etype == "feynman":
        stats["total_feynman_rounds"] = stats.get("total_feynman_rounds", 0) + 1

    _save(data)
    return data


def get_summary():
    """获取进度摘要：统计数据 + 薄弱点分析"""
    data = _load()
    stats = data.get("stats", {})

    # 计算薄弱点（正确率 < 70% 且至少尝试过 3 次）
    weak_areas = []
    for topic, perf in data.get("topic_performance", {}).items():
        if perf["attempts"] >= 3 and perf["accuracy"] < 0.7:
            weak_areas.append({
                "topic": topic,
                "accuracy": int(perf["accuracy"] * 100),
                "attempts": perf["attempts"],
                "last_practiced": perf["last_practiced"],
            })

    # 按正确率排序（最弱的排前面）
    weak_areas.sort(key=lambda x: x["accuracy"])

    # 闪卡薄弱项（评分 < 3）
    weak_flashcards = []
    for concept, fr in data.get("flashcard_ratings", {}).items():
        if fr.get("avg_rating", 5) < 3 and fr.get("reviews", 0) >= 2:
            weak_flashcards.append({"concept": concept, "rating": fr["avg_rating"]})

    # 错因统计
    mistake_reasons = {"guess": 0, "knowledge_gap": 0, "careless": 0}
    for ev in data.get("events", []):
        reason = ev.get("mistake_reason")
        if reason in mistake_reasons:
            mistake_reasons[reason] += 1

    return {
        "mcq_total": stats.get("total_mcq_attempted", 0),
        "mcq_correct": stats.get("total_mcq_correct", 0),
        "code_total": stats.get("total_coding_attempts", 0),
        "code_passed": stats.get("total_coding_passed", 0),
        "flash_total": stats.get("total_flashcards_reviewed", 0),
        "interview_total": stats.get("total_mock_interviews", 0),
        "short_total": stats.get("total_short_answers", 0),
        "feynman_total": stats.get("total_feynman_rounds", 0),
        "weak_areas": weak_areas,
        "weak_flashcards": weak_flashcards,
        "mistake_reasons": mistake_reasons,
        "last_updated": data.get("updated", ""),
    }


def _compute_streak(data):
    """从 events 计算连续学习天数"""
    from datetime import date as dt_date, timedelta
    events = data.get("events", [])
    if not events:
        return 0
    # 收集所有有练习的日期
    days = set()
    for e in events:
        ts = e.get("timestamp", "")
        if ts:
            try:
                d = ts[:10]  # YYYY-MM-DD
                days.add(d)
            except (IndexError, TypeError):
                pass
    if not days:
        return 0
    today = dt_date.today().isoformat()
    if today not in days:
        # 今天还没练习，检查昨天
        yesterday = (dt_date.today() - timedelta(days=1)).isoformat()
        if yesterday not in days:
            return 0
        # 从昨天开始往前数
        streak = 0
        check = dt_date.today() - timedelta(days=1)
    else:
        streak = 0
        check = dt_date.today()

    while check.isoformat() in days:
        streak += 1
        check -= timedelta(days=1)
    return streak


def _get_last_active(data):
    """获取最近一次活动信息"""
    events = data.get("events", [])
    if not events:
        return None
    last = events[-1]
    etype = last.get("type", "")
    # 映射类型到页面
    type_page = {
        "mcq": ["/trainer", "选择题"],
        "code": ["/trainer", "编程实战"],
        "flashcard": ["/trainer", "闪卡"],
        "short_answer": ["/trainer", "简答题"],
        "mock_interview": ["/interview", "模拟面试"],
        "feynman": ["/feynman", "费曼教练"],
    }
    page, label = type_page.get(etype, ["/trainer", "训练器"])
    return {
        "type": etype,
        "topic": last.get("topic", ""),
        "page": page,
        "label": label,
        "timestamp": last.get("timestamp", ""),
    }


def _compute_daily_activity(data, days=14):
    """计算最近 N 天每日各类练习数量"""
    from datetime import date as dt_date, timedelta
    events = data.get("events", [])
    today = dt_date.today()
    # Build lookup: date → {type: count}
    daily = {}
    for e in events:
        ts = e.get("timestamp", "")
        if not ts: continue
        d = ts[:10]
        if d not in daily:
            daily[d] = {}
        etype = e.get("type", "other")
        daily[d][etype] = daily[d].get(etype, 0) + 1
    # Fill last N days
    result = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        counts = daily.get(d, {})
        result.append({
            "date": d[5:],  # MM-DD
            "mcq": counts.get("mcq", 0),
            "code": counts.get("code", 0),
            "flashcard": counts.get("flashcard", 0),
            "short_answer": counts.get("short_answer", 0),
            "mock_interview": counts.get("mock_interview", 0),
            "feynman": counts.get("feynman", 0),
        })
    return result


def get_dashboard():
    """仪表盘聚合数据：stats + weak_areas + streak + last_active + daily_activity"""
    summary = get_summary()
    data = _load()
    summary["streak_days"] = _compute_streak(data)
    summary["last_active"] = _get_last_active(data)
    summary["total_exercises"] = (
        summary.get("mcq_total", 0) +
        summary.get("code_total", 0) +
        summary.get("flash_total", 0) +
        summary.get("interview_total", 0) +
        summary.get("short_total", 0) +
        summary.get("feynman_total", 0)
    )
    # Daily activity time-series (last 14 days)
    summary["daily_activity"] = _compute_daily_activity(data, 14)
    # Recent events (last 10, for activity feed)
    events = data.get("events", [])
    summary["recent"] = events[-10:][::-1] if events else []
    return summary


def load_progress():
    """直接加载原始 progress.json 数据（给 Agent tool 用）"""
    return _load()


def get_weak_areas():
    """返回薄弱领域列表（给 Agent tool 用）"""
    summary = get_summary()
    return summary.get("weak_areas", [])
