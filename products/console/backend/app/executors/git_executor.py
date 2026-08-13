import subprocess
from pathlib import Path
from ..config import config
from ..tracer import traced


@traced("git.commit")
def commit_changes(project_name: str, message: str, files: list[str]) -> dict:
    root = config.PORTFOLIO_ROOT
    try:
        for f in files:
            fpath = (root / f).resolve()
            if not fpath.is_relative_to(root.resolve()):
                return {"status": "error", "output": f"path not allowed: {f}"}
            subprocess.run(
                ["git", "add", f], capture_output=True, text=True, timeout=10,
                cwd=str(root)
            )
        r = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True, text=True, timeout=10,
            cwd=str(root)
        )
        if r.returncode != 0:
            return {"status": "error", "output": r.stderr.strip()}
        return {"status": "committed", "output": r.stdout.strip()}
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return {"status": "error", "output": str(e)}
