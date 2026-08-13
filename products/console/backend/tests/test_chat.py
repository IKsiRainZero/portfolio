from fastapi.testclient import TestClient
from app.main import create_app


def test_chat_stream_returns_sse():
    client = TestClient(create_app())
    r = client.post("/api/chat/stream", json={"message": "hello", "context": {}})
    # Without ANTHROPIC_API_KEY, it will error — but should still be SSE format
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")


def test_exec_confirm(tmp_path, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg.config, "PORTFOLIO_ROOT", tmp_path)
    monkeypatch.setattr(cfg.config, "PRODUCTS_DIR", tmp_path / "products")
    (tmp_path / "products").mkdir(exist_ok=True)

    client = TestClient(create_app())
    r = client.post("/api/exec/confirm", json={
        "tool": "read_file",
        "args": {"path": "nonexistent.txt"}
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "executed"
