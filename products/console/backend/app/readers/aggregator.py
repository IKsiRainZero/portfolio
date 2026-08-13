from .status_reader import read_status
from .git_reader import read_git_log, read_git_status
from .session_reader import read_sessions
from .test_reader import read_tests
from .constitution_reader import read_constitution


def aggregate_project(name: str) -> dict:
    status_entries = read_status()
    status_entry = next((e for e in status_entries if e["name"] == name), {})

    activity = read_git_log(name, limit=3) + read_sessions(name, limit=3)
    activity.sort(key=lambda a: a.get("time", ""), reverse=True)

    return {
        "name": name,
        "status": status_entry.get("status", "unknown"),
        "phase": status_entry.get("phase", ""),
        "description": status_entry.get("description", ""),
        "tests": read_tests(name),
        "activity": activity[:5],
        "risks": status_entry.get("risks", []),
        "constitution_files": read_constitution(name),
        "git_status": read_git_status(name),
    }


def aggregate_workspace() -> dict:
    projects = read_status()
    active_count = sum(1 for p in projects if p["status"] == "active")
    dormant_count = sum(1 for p in projects if p["status"] == "dormant")
    total_risks = sum(len(p.get("risks", [])) for p in projects)

    return {
        "total_projects": len(projects),
        "active": active_count,
        "dormant": dormant_count,
        "total_risks": total_risks,
        "projects": [aggregate_project(p["name"]) for p in projects],
    }
