from ..readers.aggregator import aggregate_project, aggregate_workspace
from ..readers.constitution_reader import read_constitution_summary
from ..executors.project_init import init_project
from ..executors.git_executor import commit_changes
from ..executors.file_executor import read_file, write_file
from ..readers.test_reader import read_tests
from ..tracer import traced
import subprocess
from ..config import config

TOOLS = [
    {
        "name": "read_project_status",
        "description": "Get a project's current status: phase, tests, recent activity, risks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "description": "Project directory name under products/"}
            },
            "required": ["project_name"]
        }
    },
    {
        "name": "read_file",
        "description": "Read a file's contents within the portfolio workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from portfolio root"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "run_tests",
        "description": "Run pytest for a project and stream results back.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "target": {"type": "string", "description": "Optional: specific test file or function"}
            },
            "required": ["project_name"]
        }
    },
    {
        "name": "git_diff",
        "description": "Get git status and diff summary for a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"}
            },
            "required": ["project_name"]
        }
    },
    {
        "name": "create_project",
        "description": "Create a new project with .context/ skeleton and constitution files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "type": {"type": "string", "enum": ["product", "experiment", "archive"]},
                "description": {"type": "string"}
            },
            "required": ["name", "type"]
        }
    },
    {
        "name": "commit_changes",
        "description": "Git add and commit specified files. REQUIRES user confirmation before execution.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "message": {"type": "string"},
                "files": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["project_name", "message", "files"]
        }
    },
    {
        "name": "search_knowledge",
        "description": "Search portfolio knowledge base.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_observability",
        "description": "Query operation traces for a project or time range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "operation": {"type": "string"},
                "from": {"type": "string"},
                "to": {"type": "string"}
            },
            "required": []
        }
    },
]


def execute_tool(name: str, args: dict) -> dict:
    if name == "read_project_status":
        return aggregate_project(args["project_name"])

    if name == "read_file":
        return {"content": read_file(args["path"])}

    if name == "run_tests":
        return _run_pytest(args["project_name"], args.get("target"))

    if name == "git_diff":
        from ..readers.git_reader import read_git_log, read_git_status
        return {
            "commits": read_git_log(args["project_name"], 5),
            "status": read_git_status(args["project_name"]),
        }

    if name == "create_project":
        return init_project(
            name=args["name"],
            proj_type=args.get("type", "product"),
            description=args.get("description", ""),
        )

    if name == "commit_changes":
        return commit_changes(
            project_name=args["project_name"],
            message=args["message"],
            files=args["files"],
        )

    if name == "search_knowledge":
        return _search_knowledge(args["query"])

    if name == "get_observability":
        return _query_traces(args.get("project"), args.get("operation"), args.get("from"), args.get("to"))

    return {"error": f"Unknown tool: {name}"}


@traced("tool.execute")
def _run_pytest(project_name: str, target: str | None = None) -> dict:
    project_dir = config.PRODUCTS_DIR / project_name / "backend"
    if not project_dir.exists():
        return {"status": "error", "output": f"No backend dir for {project_name}"}
    cmd = ["python", "-m", "pytest", "--tb=short", "-q"]
    if target:
        cmd.append(target)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(project_dir))
        return {"status": "ok" if r.returncode == 0 else "failed", "output": (r.stdout + r.stderr)[:2000]}
    except subprocess.TimeoutExpired:
        return {"status": "error", "output": "Tests timed out after 60s"}
    except FileNotFoundError:
        return {"status": "error", "output": "pytest not found"}


def _search_knowledge(query: str) -> dict:
    knowledge_dir = config.PORTFOLIO_ROOT / ".context" / "reference"
    results = []
    if knowledge_dir.exists():
        for f in knowledge_dir.rglob("*.md"):
            try:
                text = f.read_text(encoding="utf-8")
                if query.lower() in text.lower():
                    results.append({"path": str(f.relative_to(config.PORTFOLIO_ROOT)), "excerpt": text[:200]})
            except Exception:
                pass
    return {"results": results[:5]}


def _query_traces(project: str | None = None, operation: str | None = None,
                  from_date: str | None = None, to_date: str | None = None) -> dict:
    import json
    from datetime import datetime, timezone
    traces_dir = config.TRACES_DIR
    if not traces_dir.exists():
        return {"traces": [], "total": 0}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    results = []
    for f in sorted(traces_dir.glob("*.jsonl"), reverse=True):
        try:
            for line in f.read_text(encoding="utf-8").split("\n"):
                if not line.strip():
                    continue
                try:
                    t = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if project and t.get("target") != project:
                    continue
                if operation and t.get("operation") != operation:
                    continue
                results.append(t)
                if len(results) >= 50:
                    break
        except Exception:
            continue
        if len(results) >= 50:
            break

    return {"traces": results, "total": len(results)}
