import subprocess
from ..config import config

_SUBPROCESS_KW = {"capture_output": True, "text": True, "encoding": "utf-8"}


def _run_git(args: list[str], timeout: int = 5) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git"] + args, **_SUBPROCESS_KW, timeout=timeout,
            cwd=str(config.PORTFOLIO_ROOT)
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def read_git_log(project_name: str, limit: int = 5) -> list[dict]:
    project_dir = config.PRODUCTS_DIR / project_name
    if not project_dir.exists():
        return []

    r = _run_git(["log", f"-{limit}", "--format=%H|%aI|%s"])
    if r is None or r.returncode != 0 or not r.stdout:
        return []
    commits = []
    for line in r.stdout.strip().split("\n"):
        if line:
            parts = line.split("|", 2)
            commits.append({
                "type": "git.commit",
                "time": parts[1] if len(parts) > 1 else "",
                "summary": parts[2] if len(parts) > 2 else line,
                "hash": parts[0] if parts else "",
            })
    return commits


def read_git_status(project_name: str) -> dict | None:
    project_dir = config.PRODUCTS_DIR / project_name
    if not project_dir.exists():
        return None

    r = _run_git(["status", "--porcelain"])
    if r is None or r.returncode != 0:
        return None
    uncommitted = len([l for l in r.stdout.strip().split("\n") if l])
    br = _run_git(["branch", "--show-current"], timeout=3)
    lc = _run_git(["log", "-1", "--format=%H|%aI|%s"], timeout=3)
    return {
        "uncommitted": uncommitted,
        "branch": br.stdout.strip() if br else "",
        "last_commit": lc.stdout.strip() if lc else "",
    }
