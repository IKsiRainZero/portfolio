from ..readers.aggregator import aggregate_project, aggregate_workspace
from ..readers.constitution_reader import read_constitution_summary


def build_context(message: str, view: dict | None = None) -> dict:
    if view is None:
        view = {}

    hot = {
        "message": message,
        "current_view": view.get("current_view", "dashboard"),
        "active_project": view.get("active_project", ""),
        "viewport_summary": view.get("viewport_summary", {}),
    }

    warm = {}
    active = view.get("active_project", "")
    if active:
        warm["project_summary"] = read_constitution_summary(active)

    return {
        "hot": hot,
        "warm": warm,
        "cold": "[available via tool calls: read_project_status, search_knowledge, read_file]"
    }
