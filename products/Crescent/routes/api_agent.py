"""Agent API 路由 — ReAct Agent 对话接口"""
import json as _json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
import config
from services.deepseek_client import chat, load_prompt

router = APIRouter(prefix="/api")


@router.post("/agent/chat")
async def chat(request: Request):
    """Agent 对话 — 单轮请求"""
    if config.LLM_PROVIDER != "local" and not config.API_KEY:
        return JSONResponse(content={"error": "请先配置 API Key"}, status_code=401)

    data = await request.json()
    message = (data.get("message") or "").strip()
    if not message:
        return JSONResponse(content={"error": "消息不能为空"}, status_code=400)

    session_id = data.get("session_id", "default")
    persona = data.get("persona", "")

    from services.agent_service import agent_chat

    try:
        result = agent_chat(message, session_id, persona)
        return {
            "reply": result["reply"],
            "tool_calls": result["tool_calls"],
            "steps": result["steps"],
            "harness": result.get("harness", {}),
            "session_id": session_id,
            "provider_used": result.get("provider_used", ""),
        }
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=401)
    except RuntimeError as e:
        return JSONResponse(content={"error": str(e)}, status_code=502)
    except Exception:
        from services.safe_error import safe_error
        return JSONResponse(content=safe_error(Exception("agent_chat 内部错误"), "agent_chat"), status_code=500)


@router.get("/agent/chat/stream")
async def chat_stream(request: Request):
    """SSE 流式 Agent 对话 — EventSource 兼容"""
    if config.LLM_PROVIDER != "local" and not config.API_KEY:
        return JSONResponse(content={"error": "请先配置 API Key"}, status_code=401)

    message = (request.query_params.get("message") or "").strip()
    if not message:
        return JSONResponse(content={"error": "消息不能为空"}, status_code=400)

    session_id = request.query_params.get("session_id", "default")
    persona = request.query_params.get("persona", "")
    force_tools = request.query_params.get("force_tools", "").lower() in ("1", "true", "yes")

    from services.agent_service import agent_chat_stream

    async def generate():
        try:
            async for event in agent_chat_stream(message, session_id, persona, force_tools=force_tools):
                if event.get("type") == "heartbeat":
                    yield ": heartbeat\n\n"
                else:
                    yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
        except ValueError as e:
            yield f"data: {_json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'content': f'Agent 请求失败: {str(e)}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/agent/sessions")
async def list_sessions(request: Request):
    """列出活跃 session 及其元数据"""
    import time as _time
    from services.agent_service import _SESSION_META
    now = _time.time()
    result = []
    for sid, data in list(_SESSION_META.items()):
        result.append({
            "session_id": sid,
            "age_seconds": round(now - data["created"]),
            "idle_seconds": round(now - data.get("last_accessed", data["created"])),
        })
    return {"count": len(result), "sessions": result}


@router.get("/agent/bubbles")
async def api_get_bubbles(request: Request):
    """获取跨角色上下文气泡 + 当前 session 的工具/计划状态。"""
    from services.session_store import get_bubbles
    from services.agent_service import _SESSION_META

    limit = int(request.query_params.get("limit", "5"))
    limit = max(1, min(limit, 20))
    exclude = request.query_params.get("exclude_persona", "")
    sid = request.query_params.get("session_id", "")

    bubbles = get_bubbles(exclude_persona=exclude, limit=limit,
                          max_age_seconds=86400)

    meta = _SESSION_META.get(sid, {}) if sid else {}
    tool_profile = meta.get("last_tool_profile")
    active_plan = meta.get("active_plan", [])

    pending_course = None
    if sid and sid in _SESSION_META:
        pending_course = _SESSION_META[sid].get("pending_course")

    return {
        "bubbles": bubbles,
        "tool_profile": tool_profile,
        "active_plan": active_plan,
        "course": pending_course,
    }


@router.post("/agent/generate-course")
async def api_generate_course(request: Request):
    """SSE endpoint: 生成结构化课程（备课工作台）"""
    from services.agent_service import generate_course_stream
    try:
        data = await request.json()
    except Exception:
        data = {}
    topic = (data.get("topic") or "").strip()
    if not topic:
        return JSONResponse(content={"error": "topic is required"}, status_code=400)

    sources = data.get("sources", [])
    persona = data.get("persona", "teacher")
    depth = data.get("depth", "standard")

    def _stream():
        try:
            for event in generate_course_stream(topic, sources, persona, depth):
                yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@router.post("/agent/send-course")
async def api_send_course(request: Request):
    """将办公室生成的课程推送到教室 session"""
    from services.agent_service import send_course_to_classroom
    try:
        data = await request.json()
    except Exception:
        data = {}
    course = data.get("course")
    sid = data.get("session_id", "teacher_active")
    if not course:
        return JSONResponse(content={"ok": False, "error": "course is required"}, status_code=400)
    send_course_to_classroom(course, sid)
    return {"ok": True}


@router.post("/agent/reset")
async def reset(request: Request):
    """重置指定 session 的记忆"""
    try:
        data = await request.json()
    except Exception:
        data = {}
    session_id = data.get("session_id", "default")
    from services.agent_service import _SESSION_META, _SESSION_HISTORY
    if session_id in _SESSION_META:
        del _SESSION_META[session_id]
        _SESSION_HISTORY.pop(session_id, None)
        return {"ok": True, "message": f"Session {session_id} 已重置"}
    return {"ok": True, "message": f"Session {session_id} 不存在或已清理"}


@router.post("/agent/chat/cancel")
async def cancel_chat(request: Request):
    """取消正在执行的 Agent 流 — 设置 cancel flag 中断 ReAct 循环"""
    try:
        data = await request.json()
    except Exception:
        data = {}
    session_id = data.get("session_id", "")
    if not session_id:
        return {"ok": False, "message": "session_id is required"}
    from services.agent_service import cancel_session
    ok = cancel_session(session_id)
    return {"ok": ok, "message": "取消信号已发送" if ok else "未找到活跃会话"}


@router.post("/agent/dashboard-insight")
async def dashboard_insight(request: Request):
    """仪表盘智能引导 — 对比上次快照，LLM 生成个性化行动建议"""
    try:
        data = await request.json()
    except Exception:
        data = {}
    last_snapshot = data.get("last_snapshot") or {}

    from services.progress_tracker import get_dashboard
    from services.srs_scheduler import get_stats as srs_stats
    current = get_dashboard()
    srs = srs_stats()

    prev_total = last_snapshot.get("total_exercises", 0)
    curr_total = current.get("total_exercises", 0)
    new_exercises = curr_total - prev_total
    prev_weak_count = last_snapshot.get("weak_count", 0)
    curr_weak = current.get("weak_areas", [])
    curr_due = srs.get("due_today", 0)
    prev_due = last_snapshot.get("due_today", 0)

    has_changes = (new_exercises > 0 or
                   len(curr_weak) != prev_weak_count or
                   curr_due != prev_due or
                   not last_snapshot)

    snapshot = {
        "total_exercises": curr_total,
        "mcq_total": current.get("mcq_total", 0),
        "code_total": current.get("code_total", 0),
        "flash_total": current.get("flash_total", 0),
        "interview_total": current.get("interview_total", 0),
        "streak_days": current.get("streak_days", 0),
        "due_today": curr_due,
        "weak_count": len(curr_weak),
        "weak_areas": [w["topic"] for w in curr_weak[:5]],
        "recent_types": list(set(
            e.get("type", "") for e in (current.get("recent") or [])[:5]
        )),
    }

    if not has_changes:
        return {
            "insight": (
                f"上次访问以来暂无新的学习活动。"
                f"你有 {curr_due} 张待复习闪卡"
                f"{'，' + str(len(curr_weak)) + ' 个薄弱领域需要关注' if curr_weak else ''}。"
                f"[去训练器复习](/trainer)"
            ),
            "snapshot": snapshot,
            "has_changes": False,
        }

    weak_lines = "\n".join(
        f"  - {w['topic']}: 正确率 {w['accuracy']}%, 练习 {w['attempts']} 次"
        for w in curr_weak[:5]
    ) or "  无"

    recent_lines = "\n".join(
        f"  - {e.get('type','')}: {e.get('topic','未分类')} {'✓' if e.get('correct') else '✗' if e.get('correct') is False else ''}"
        for e in (current.get("recent") or [])[:5]
    ) or "  无"

    data_text = (
        f"总练习: {curr_total} 题 (选择题 {current.get('mcq_total',0)}, "
        f"编程 {current.get('code_total',0)}, 闪卡 {current.get('flash_total',0)}, "
        f"面试 {current.get('interview_total',0)})\n"
        f"连续学习: {current.get('streak_days',0)} 天\n"
        f"今日待复习闪卡: {curr_due} 张\n"
        f"薄弱领域:\n{weak_lines}\n"
        f"新增练习(自上次): {new_exercises} 题\n"
        f"最近活动:\n{recent_lines}"
    )

    prompt = (
        "你是一个学习教练。分析以下数据，用 2-4 句话给出今日学习引导。\n\n"
        f"## 学习数据\n{data_text}\n\n"
        "## 格式要求\n"
        "1. 先指出最重要的变化或发现（1句话）\n"
        "2. 给出 1-2 条具体行动建议\n"
        "3. 每条建议必须使用 Markdown 链接格式: [链接文字](路径)\n"
        "   可用的链接目标:\n"
        "   - 训练器: /trainer\n"
        "   - 知识库: /knowledge\n"
        "   - 模拟面试: /interview\n"
        "4. 总字数 80-150，不要问候语，不要 emoji，直接说结论\n"
        "5. 链接文字要具体，不要只说'去训练器'，要说'去训练器复习 XXX 知识点'"
    )

    try:
        if config.LLM_PROVIDER != "local" and not config.API_KEY:
            raise ValueError("API Key 未配置")

        system = "你是一个有洞察力的学习教练。回复简洁、具体、可执行。只输出引导文本，不要加前缀标题。"
        reply, _usage = chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system,
            temperature=0.6,
            max_tokens=250,
            timeout=15,
        )
        insight = reply.strip()
    except Exception:
        parts = []
        if new_exercises > 0:
            parts.append(f"新增 {new_exercises} 次练习")
        if curr_weak:
            weak_names = ", ".join(w["topic"] for w in curr_weak[:3])
            parts.append(f"薄弱领域: {weak_names}")
        if curr_due > 0:
            parts.append(f"{curr_due} 张闪卡待复习")
        if parts:
            insight = f"{'；'.join(parts)}。"
        else:
            insight = "开始你的学习之旅。"
        insight += f"[去训练器练习](/trainer)"
        if curr_weak:
            insight += f" [浏览知识库补充基础](/knowledge)"

    return {
        "insight": insight,
        "snapshot": snapshot,
        "has_changes": True,
    }


@router.post("/exercises/save-generated")
async def save_generated_question(request: Request):
    """将 Agent 生成的题目保存到临时题库（前端按钮调用，不走 LLM）"""
    data = await request.json()
    item = data.get("item", {})
    if not item:
        return JSONResponse(content={"error": "缺少题目数据"}, status_code=400)

    required = ["type", "question", "answer"]
    missing = [f for f in required if f not in item]
    if missing:
        return JSONResponse(content={"error": f"缺少必填字段: {', '.join(missing)}"}, status_code=400)

    ex_type = item["type"]
    if ex_type not in ("mcq", "coding", "flashcards"):
        return JSONResponse(content={"error": f"type 必须是 mcq/coding/flashcards 之一"}, status_code=400)

    from services.exercise_store import add as store_add, load as store_load
    item["_source"] = "ui_saved"
    saved = store_add(item)
    total = sum(len(v) for v in store_load().values())

    return {
        "ok": True,
        "item_id": saved["id"],
        "total_temp": total,
    }


# ── Session 管理 ──

@router.get("/session-history")
async def api_list_session_history(request: Request):
    """列出所有磁盘持久化的会话历史"""
    from services.session_store import list_sessions
    return list_sessions()


@router.get("/session-history/{session_id}")
async def api_get_session_history(session_id: str, request: Request):
    """返回指定会话的消息列表"""
    from services.session_store import load as load_session
    data = load_session(session_id)
    if not data:
        return JSONResponse(content={"error": "session not found"}, status_code=404)
    return {
        "session_id": data.get("session_id", session_id),
        "persona": data.get("persona", ""),
        "messages": data.get("messages", []),
    }


@router.delete("/session-history/{session_id}")
async def api_delete_session_history(session_id: str, request: Request):
    """删除指定会话"""
    from services.session_store import delete_session as delete_fn
    ok = delete_fn(session_id)
    if ok:
        return {"ok": True}
    return JSONResponse(content={"error": "session not found"}, status_code=404)


# ══════════════════════════════════════════════════════════════
# Review Agent — 用户可调用的元认知审查
# ══════════════════════════════════════════════════════════════

@router.post("/agent/review")
async def api_run_review(request: Request):
    """触发一次审查 Agent 运行，返回发现的问题和建议。"""
    from services.review_agent import run_review
    try:
        result = run_review()
    except Exception as e:
        return JSONResponse(content={"error": f"review failed: {str(e)}"}, status_code=500)

    if result.get("error"):
        return JSONResponse(content=result, status_code=500)

    try:
        from services.session_store import save_bubble
        findings = result.get("suggestions", [])[:5]
        for f in findings:
            desc = f.get("description", "")
            dim = f.get("dimension", "")
            severity = f.get("severity", "P2")
            if desc:
                save_bubble(
                    session_id="review-agent",
                    persona="reviewer",
                    topic=f"审查发现: {dim}",
                    question=f"审查 Agent 在{dim}维度发现的问题",
                    insight=f"[{severity}] {desc[:180]}",
                    key_terms=[dim, severity],
                )
    except Exception:
        pass

    return {
        "review_id": result.get("review_id", ""),
        "suggestions": result.get("suggestions", []),
        "duration_ms": result.get("duration_ms", 0),
        "session_count": result.get("session_count", 0),
    }


@router.get("/agent/review/status")
async def api_review_status(request: Request):
    """获取审查 Agent 的当前状态（记忆层级、最近审查结果等）。"""
    try:
        from services.review_memory import get_memory_state
        state = get_memory_state()
    except Exception:
        state = {}
    try:
        from services.review_store import get_session_count
        sc = get_session_count()
    except Exception:
        sc = 0

    return {
        "session_count": sc,
        "memory": state,
    }
