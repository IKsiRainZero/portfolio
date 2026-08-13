# tests/workbench/test_api_workbench.py
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import os
import sys

# Ensure Crescent is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Use a temp dir to isolate test data
tmp = tempfile.mkdtemp()
os.environ["CRESCENT_TEST_DATA"] = tmp


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


class TestWorkbenchAPI:
    def test_start_session(self, client):
        resp = client.post("/api/workbench/start")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data

    def test_send_message(self, client):
        start = client.post("/api/workbench/start")
        sid = start.json()["session_id"]
        resp = client.post(f"/api/workbench/{sid}/message",
                           json={"text": "我做了三年Python后端开发"})
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert len(data["events"]) > 0

    def test_send_empty_message(self, client):
        start = client.post("/api/workbench/start")
        sid = start.json()["session_id"]
        resp = client.post(f"/api/workbench/{sid}/message",
                           json={"text": ""})
        assert resp.status_code == 400

    def test_confirm_panel(self, client):
        start = client.post("/api/workbench/start")
        sid = start.json()["session_id"]
        client.post(f"/api/workbench/{sid}/message",
                    json={"text": "我是Python后端三年经验"})
        resp = client.post(f"/api/workbench/{sid}/confirm",
                           json={"panel_id": "profile"})
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data

    def test_revoke_panel(self, client):
        start = client.post("/api/workbench/start")
        sid = start.json()["session_id"]
        resp = client.post(f"/api/workbench/{sid}/revoke",
                           json={"panel_id": "direction", "reason": "方向不对"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) > 0

    def test_nonexistent_session(self, client):
        resp = client.post("/api/workbench/fake-id/message",
                           json={"text": "hello"})
        assert resp.status_code == 404

    def test_list_sessions(self, client):
        client.post("/api/workbench/start")
        resp = client.get("/api/workbench/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data

    def test_export(self, client):
        start = client.post("/api/workbench/start")
        sid = start.json()["session_id"]
        client.post(f"/api/workbench/{sid}/message",
                    json={"text": "我用Python开发后端三年"})
        resp = client.get(f"/api/workbench/{sid}/export")
        assert resp.status_code == 200
