from fastapi.testclient import TestClient
from app.main import create_app


def test_health():
    client = TestClient(create_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_workspace_summary(tmp_path, monkeypatch):
    import app.config as cfg
    status_md = tmp_path / "STATUS.md"
    status_md.write_text("""## 进行中
| 项目 | 当前状态 | 下一步 | 阻塞 |
|------|----------|--------|------|
| **TestP** | P1 | next | 无 |
""", encoding="utf-8")
    monkeypatch.setattr(cfg.config, "STATUS_PATH", status_md)
    (tmp_path / "products" / "TestP" / ".context" / "constitution").mkdir(parents=True)
    monkeypatch.setattr(cfg.config, "PRODUCTS_DIR", tmp_path / "products")
    monkeypatch.setattr(cfg.config, "PORTFOLIO_ROOT", tmp_path)

    client = TestClient(create_app())
    r = client.get("/api/workspace/summary")
    assert r.status_code == 200
    data = r.json()
    assert "total_projects" in data


def test_project_not_found():
    client = TestClient(create_app())
    r = client.get("/api/projects/___nonexistent___")
    assert r.status_code == 404
