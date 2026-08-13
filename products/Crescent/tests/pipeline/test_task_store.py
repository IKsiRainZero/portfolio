from __future__ import annotations
from services.pipeline.task_store import TaskStore


def test_task_store_create_and_get():
    store = TaskStore()
    task_id = store.create("test query", 5)
    assert task_id is not None
    assert len(task_id) > 0

    task = store.get(task_id)
    assert task is not None
    assert task["query"] == "test query"
    assert task["status"] in ("pending", "running")


def test_task_store_get_nonexistent():
    store = TaskStore()
    assert store.get("nonexistent") is None


def test_task_store_update():
    store = TaskStore()
    task_id = store.create("query", 3)
    store.update(task_id, status="running")
    assert store.get(task_id)["status"] == "running"

    store.update(task_id, status="ok", outputs={"S5": {"plan": {}}}, trace=[])
    task = store.get(task_id)
    assert task["status"] == "ok"
    assert "S5" in task["outputs"]


def test_task_store_ttl_expiry():
    import time

    store = TaskStore(ttl_seconds=0.01)
    task_id = store.create("ephemeral", 3)
    time.sleep(0.02)
    assert store.get(task_id) is None
