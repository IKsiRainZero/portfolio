"""Collect traces from Claude Code sessions (Stop hook stubs + git log)."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from ..config import config
from .trace import Trace, get_tracer


def collect_session_traces() -> list[Trace]:
    session_dir = config.PORTFOLIO_ROOT / ".context" / "sessions" / "archive"
    if not session_dir.exists():
        return []

    traces = []
    for f in sorted(session_dir.glob("*-stub.md"), reverse=True)[:5]:
        date = f.stem.replace("-stub", "")
        trace = Trace(
            id=f"trace-claude-{date}",
            timestamp=f"{date}T00:00:00.000Z",
            source="claude-code",
            session_id=date,
            operation="session.complete",
            target="workspace",
            input_summary=f"Session on {date}",
            output_summary="",
            duration_ms=0,
            status="ok",
        )
        traces.append(trace)

    return traces


def collect_git_traces() -> list[Trace]:
    try:
        r = subprocess.run(
            ["git", "log", "-5", "--format=%H|%aI|%s"],
            capture_output=True, text=True, timeout=5,
            cwd=str(config.PORTFOLIO_ROOT)
        )
        if r.returncode != 0:
            return []
        traces = []
        for line in r.stdout.strip().split("\n"):
            if "|" not in line:
                continue
            h, ts, msg = line.split("|", 2)
            traces.append(Trace(
                id=f"trace-git-{h[:12]}",
                timestamp=ts,
                source="claude-code",
                session_id="git",
                operation="git.commit",
                target="workspace",
                input_summary="",
                output_summary=msg.strip(),
                duration_ms=0,
                status="ok",
            ))
        return traces
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def sync_collected_traces() -> int:
    tracer = get_tracer()
    count = 0
    for t in collect_session_traces():
        tracer.write(t)
        count += 1
    for t in collect_git_traces():
        tracer.write(t)
        count += 1
    return count
