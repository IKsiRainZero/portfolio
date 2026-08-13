from pathlib import Path
from ..config import config
from ..tracer import traced


@traced("file.read")
def read_file(path: str) -> str:
    full = config.PORTFOLIO_ROOT / path
    if not full.resolve().is_relative_to(config.PORTFOLIO_ROOT.resolve()):
        return "[error: path outside portfolio]"
    if not full.exists():
        return "[file not found]"
    return full.read_text(encoding="utf-8")[:5000]


@traced("file.write")
def write_file(path: str, content: str) -> dict:
    full = config.PORTFOLIO_ROOT / path
    if not full.resolve().is_relative_to(config.PORTFOLIO_ROOT.resolve()):
        return {"status": "error", "reason": "path outside portfolio"}
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return {"status": "written", "path": str(full)}
