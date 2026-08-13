from fastapi import APIRouter, HTTPException, Query
from ..readers.aggregator import aggregate_workspace, aggregate_project
from ..readers.status_reader import read_status
from ..readers.claude_sessions_reader import read_claude_sessions
from ..tracer import traced
from ..tracer.collector import sync_collected_traces

router = APIRouter(prefix="/api", tags=["projects"])


@router.get("/workspace/summary")
@traced("workspace.summary")
async def workspace_summary():
    ws = aggregate_workspace()
    return {
        "total_projects": ws["total_projects"],
        "active": ws["active"],
        "dormant": ws["dormant"],
        "total_risks": ws["total_risks"],
    }


@router.get("/projects")
@traced("projects.list")
async def list_projects():
    ws = aggregate_workspace()
    return ws["projects"]


@router.get("/projects/{name}")
@traced("projects.detail")
async def project_detail(name: str):
    entries = read_status()
    if not any(e["name"] == name for e in entries):
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    return aggregate_project(name)


@router.get("/claude-sessions")
@traced("claude_sessions.list")
async def list_claude_sessions(limit: int = Query(default=50, ge=1, le=200)):
    return {"sessions": read_claude_sessions(limit=limit)}


@router.post("/observability/sync")
@traced("observability.sync")
async def sync_observability():
    count = sync_collected_traces()
    return {"status": "synced", "traces_collected": count}
