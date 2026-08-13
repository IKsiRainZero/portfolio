import re
from pathlib import Path
from ..config import config


def read_status() -> list[dict]:
    path = config.STATUS_PATH
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    projects = []
    current_section = None
    in_table = False

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("## "):
            current_section = line.lstrip("# ").strip()
            in_table = False
        elif line.startswith("|---"):
            # Table separator line — signals that a table follows
            in_table = True
            continue
        elif in_table and line.startswith("| **"):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 3:
                name = parts[0].strip("*").strip()
                status = parts[1].strip() if len(parts) > 1 else ""
                next_step = parts[2].strip() if len(parts) > 2 else ""
                blocking = parts[3].strip() if len(parts) > 3 else ""
                projects.append({
                    "name": name,
                    "status": "active" if current_section and "进行" in current_section
                              else "dormant" if current_section and "休眠" in current_section
                              else "ready" if current_section and "框架" in current_section
                              else "archived",
                    "phase": status,
                    "description": f"下一步: {next_step}" if next_step else "",
                    "risks": [{"level": "warning", "text": blocking, "source": "STATUS.md"}]
                           if blocking and blocking != "无" and blocking != "-" else [],
                })

    return projects
