import subprocess
import re
from pathlib import Path
from ..config import config


def read_tests(project_name: str) -> dict:
    project_dir = config.PRODUCTS_DIR / project_name
    if not project_dir.exists():
        return _empty()

    backend_test_dir = project_dir / "backend" / "tests"
    if backend_test_dir.exists():
        return _run_pytest(project_dir / "backend", project_name)
    return _empty()


def _run_pytest(cwd: Path, project_name: str) -> dict:
    try:
        r = subprocess.run(
            ["python", "-m", "pytest", "--tb=no", "-q"],
            capture_output=True, text=True, timeout=30,
            cwd=str(cwd)
        )
        output = r.stdout + r.stderr
        passed = 0
        failed = 0
        for line in output.split("\n"):
            if "passed" in line:
                m = re.search(r"(\d+)\s+passed", line)
                if m:
                    passed = int(m.group(1))
                m = re.search(r"(\d+)\s+failed", line)
                if m:
                    failed = int(m.group(1))
        return {
            "total": passed + failed,
            "passed": passed,
            "failed": failed,
            "last_run": "",
        }
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return _empty()


def _empty() -> dict:
    return {"total": 0, "passed": 0, "failed": 0, "last_run": ""}
