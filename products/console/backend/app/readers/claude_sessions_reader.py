import json
import os
from pathlib import Path
from datetime import datetime, timezone


def _decode_project_name(dirname: str) -> str:
    if len(dirname) >= 3 and dirname[0].isalpha() and dirname[1:3] == "--":
        drive = dirname[0]
        rest = dirname[3:]
        return drive + ":\\" + rest.replace("-", "\\")
    if dirname.startswith("-"):
        return dirname.replace("-", "/")
    return dirname


def _extract_title(filepath: Path) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i > 80:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = d.get("message", {})
                if isinstance(msg, dict) and msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, str) and content.strip():
                        return content.strip()[:200]
    except (OSError, UnicodeDecodeError):
        pass
    return ""


def _short_project_label(dirname: str) -> str:
    decoded = _decode_project_name(dirname)
    parts = decoded.replace("\\", "/").rstrip("/").split("/")
    if len(parts) <= 1:
        return decoded
    if len(parts) == 2:
        return parts[-1]
    return "/".join(parts[-2:])


def read_claude_sessions(limit: int = 50) -> list[dict]:
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        return []

    sessions = []
    for proj_dir in sorted(base.iterdir()):
        if not proj_dir.is_dir():
            continue
        for f in sorted(proj_dir.glob("*.jsonl")):
            mtime = f.stat().st_mtime
            title = _extract_title(f)
            sessions.append({
                "session_id": f.stem,
                "project_dir": proj_dir.name,
                "project_label": _short_project_label(proj_dir.name),
                "project_path": _decode_project_name(proj_dir.name),
                "title": title,
                "time": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                "size_bytes": f.stat().st_size,
            })
        # also check for session dirs with matching .jsonl inside
        for session_dir in proj_dir.iterdir():
            if not session_dir.is_dir():
                continue
            jf = Path(str(session_dir) + ".jsonl")
            if jf.exists():
                continue  # already counted above
            mtime = session_dir.stat().st_mtime
            # try to read the first .jsonl file inside
            title = ""
            size = 0
            for inner in sorted(session_dir.glob("*.jsonl")):
                title = _extract_title(inner)
                size += inner.stat().st_size
                break
            if not title:
                title = _extract_title(session_dir / "transcript.jsonl") if (session_dir / "transcript.jsonl").exists() else ""
            sessions.append({
                "session_id": session_dir.name,
                "project_dir": proj_dir.name,
                "project_label": _short_project_label(proj_dir.name),
                "project_path": _decode_project_name(proj_dir.name),
                "title": title,
                "time": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                "size_bytes": size or session_dir.stat().st_size,
            })

    sessions.sort(key=lambda s: s["time"], reverse=True)
    return sessions[:limit]
