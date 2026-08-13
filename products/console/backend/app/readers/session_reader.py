from pathlib import Path
from ..config import config


def read_sessions(project_name: str, limit: int = 3) -> list[dict]:
    session_dir = config.PRODUCTS_DIR / project_name / ".context" / "sessions" / "archive"
    ws_session_dir = config.PORTFOLIO_ROOT / ".context" / "sessions" / "archive"

    results = []
    for base in [session_dir, ws_session_dir]:
        if not base.exists():
            continue
        for f in sorted(base.glob("*.md"), reverse=True):
            if f.name.endswith("-stub.md"):
                continue
            preview = _extract_preview(f)
            if preview:
                results.append({
                    "type": "session.record",
                    "time": _extract_date(f.name),
                    "summary": preview,
                })
            if len(results) >= limit:
                break

    return results[:limit]


def _extract_date(filename: str) -> str:
    if len(filename) >= 10 and filename[4] == "-" and filename[7] == "-":
        return filename[:10]
    return ""


def _extract_preview(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").split("\n")
        title = lines[0].lstrip("# ").strip() if lines else path.stem
        return title if title else path.stem
    except Exception:
        return ""
