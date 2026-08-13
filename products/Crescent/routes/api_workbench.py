# routes/api_workbench.py — Workbench API routes + SSE event stream
from __future__ import annotations
import uuid
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.requests import Request

from config import USER_DATA_DIR

router = APIRouter(prefix="/api/workbench")

_sessions: dict[str, "SessionState"] = {}


class SessionState:
    def __init__(self, engine, event_queue: asyncio.Queue):
        self.engine = engine
        self.event_queue = event_queue
        self.session_id = str(uuid.uuid4())[:12]


def _get_engine():
    from services.workbench.profile_store import ProfileStore
    from services.workbench.industry_scanner import IndustryScanner
    from services.workbench.skill_matcher import SkillMatcher
    from services.workbench.gap_analyzer import GapAnalyzer
    from services.workbench.learning_path import LearningPathGenerator
    from services.workbench.next_action import NextActionGenerator
    from services.workbench.engine import WorkbenchEngine

    import os
    data_dir = Path(os.environ.get("CRESCENT_TEST_DATA", str(USER_DATA_DIR)))
    wb_pw = os.environ.get("WB_PASSWORD", "crescent-wb")
    store = ProfileStore(data_dir=data_dir, password=wb_pw)
    return WorkbenchEngine(
        profile_store=store,
        scanner=IndustryScanner(),
        matcher=SkillMatcher(),
        analyzer=GapAnalyzer(),
        path_gen=LearningPathGenerator(),
        action_gen=NextActionGenerator(),
    )


@router.post("/start")
async def start_session():
    engine = _get_engine()
    queue = asyncio.Queue()
    sid = str(uuid.uuid4())[:12]
    _sessions[sid] = SessionState(engine=engine, event_queue=queue)
    return JSONResponse(content={"session_id": sid})


@router.post("/{session_id}/message")
async def send_message(session_id: str, request: Request):
    session = _sessions.get(session_id)
    if not session:
        return JSONResponse(content={"error": "Session not found"}, status_code=404)

    data = await request.json()
    text = (data.get("text") or "").strip()
    if not text:
        return JSONResponse(content={"error": "Empty message"}, status_code=400)

    events = session.engine.handle_input(session_id, text)
    for e in events:
        await session.event_queue.put({
            "event_type": e.event_type,
            "panel_id": e.panel_id,
            "payload": e.payload,
            "timestamp": e.timestamp,
        })

    return JSONResponse(content={"events": _serialize_events(events)})


@router.get("/{session_id}/events")
async def event_stream(session_id: str, request: Request):
    session = _sessions.get(session_id)
    if not session:
        return JSONResponse(content={"error": "Session not found"}, status_code=404)

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(
                        session.event_queue.get(), timeout=15.0
                    )
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/{session_id}/confirm")
async def confirm_panel(session_id: str, request: Request):
    session = _sessions.get(session_id)
    if not session:
        return JSONResponse(content={"error": "Session not found"}, status_code=404)

    data = await request.json()
    panel_id = data.get("panel_id", "")

    if not session.engine.can_confirm(panel_id):
        return JSONResponse(
            content={"error": f"Cannot confirm '{panel_id}': upstream panels not confirmed"},
            status_code=400,
        )

    await session.event_queue.put({
        "event_type": "system.processing",
        "panel_id": panel_id,
        "payload": {"message": f"正在处理 {panel_id}...", "step": panel_id},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    events = session.engine.confirm_panel(session_id, panel_id)
    for e in events:
        await session.event_queue.put({
            "event_type": e.event_type,
            "panel_id": e.panel_id,
            "payload": e.payload,
            "timestamp": e.timestamp,
        })

    return JSONResponse(content={"events": _serialize_events(events)})


@router.post("/{session_id}/revoke")
async def revoke_panel(session_id: str, request: Request):
    session = _sessions.get(session_id)
    if not session:
        return JSONResponse(content={"error": "Session not found"}, status_code=404)

    data = await request.json()
    panel_id = data.get("panel_id", "")
    reason = data.get("reason", "")
    events = session.engine.revoke_panel(session_id, panel_id, reason)
    for e in events:
        await session.event_queue.put({
            "event_type": e.event_type,
            "panel_id": e.panel_id,
            "payload": e.payload,
            "timestamp": e.timestamp,
        })

    return JSONResponse(content={"events": _serialize_events(events)})


@router.get("/{session_id}/export")
async def export_profile(session_id: str):
    session = _sessions.get(session_id)
    if not session:
        return JSONResponse(content={"error": "Session not found"}, status_code=404)

    profile = session.engine._profile_store.load()
    if not profile.skills and not profile.experiences:
        return JSONResponse(content={"error": "No profile data"}, status_code=400)

    return JSONResponse(content=profile.to_dict())


@router.get("/sessions")
async def list_sessions():
    return JSONResponse(content={"sessions": list(_sessions.keys())})


def _serialize_events(events) -> list[dict]:
    return [
        {
            "event_type": e.event_type,
            "panel_id": e.panel_id,
            "payload": e.payload,
            "timestamp": e.timestamp,
        }
        for e in events
    ]
