from fastapi.testclient import TestClient
from app.main import create_app


def test_full_workspace_flow(portfolio_root):
    client = TestClient(create_app())

    # -- workspace summary --
    r = client.get("/api/workspace/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["total_projects"] == 2
    assert data["active"] == 1          # TestProject is in "进行中"
    assert data["dormant"] == 1         # DoneProject is in "休眠"

    # -- list all projects --
    r = client.get("/api/projects")
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) == 2

    # -- single project detail --
    r = client.get("/api/projects/TestProject")
    assert r.status_code == 200
    detail = r.json()
    assert detail["name"] == "TestProject"
    assert detail["phase"] == "Phase 1"
    assert len(detail["risks"]) == 1
    assert detail["risks"][0]["text"] == "pytest not configured"
    assert len(detail["constitution_files"]) == 2

    # -- nonexistent project returns 404 --
    r = client.get("/api/projects/___nonexistent___")
    assert r.status_code == 404


def test_project_init_integration(portfolio_root):
    client = TestClient(create_app())
    r = client.post("/api/exec/confirm", json={
        "tool": "create_project",
        "args": {"name": "NewProject", "type": "product", "description": "a fresh project"}
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "executed"
    assert data["result"]["status"] == "created"

    new_dir = portfolio_root / "products" / "NewProject"
    assert new_dir.exists()
    assert (new_dir / ".context" / "constitution" / "architecture.md").exists()
    assert (new_dir / ".context" / "constitution" / "decisions.md").exists()
    assert (new_dir / ".context" / "constitution" / "tech-stack.md").exists()


def test_tracer_writes_on_api_call(portfolio_root):
    client = TestClient(create_app())
    client.get("/api/projects/TestProject")

    traces_dir = portfolio_root / ".context" / "observability" / "traces"
    files = list(traces_dir.glob("*.jsonl"))
    assert len(files) > 0

    import json
    lines = files[0].read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) > 0
    trace = json.loads(lines[0])
    assert trace["operation"] == "projects.detail"
    assert trace["source"] == "console"
