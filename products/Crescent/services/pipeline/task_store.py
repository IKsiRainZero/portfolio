from __future__ import annotations
import uuid
import time
import threading


class TaskStore:
    """内存中的管道任务状态存储。生产环境可替换为 Redis。"""

    def __init__(self, ttl_seconds: int = 3600):
        self._tasks: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def create(self, query: str, max_results: int) -> str:
        task_id = str(uuid.uuid4())[:12]
        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "query": query,
                "max_results": max_results,
                "status": "pending",
                "outputs": None,
                "trace": None,
                "created_at": time.time(),
                "error": None,
            }
        return task_id

    def get(self, task_id: str) -> dict | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if time.time() - task["created_at"] > self._ttl:
                del self._tasks[task_id]
                return None
            return dict(task)

    def update(self, task_id: str, status: str, outputs=None, trace=None, error=None):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["status"] = status
                if outputs is not None:
                    self._tasks[task_id]["outputs"] = outputs
                if trace is not None:
                    self._tasks[task_id]["trace"] = trace
                if error is not None:
                    self._tasks[task_id]["error"] = error

    def _cleanup_expired(self):
        now = time.time()
        with self._lock:
            expired = [
                tid for tid, t in self._tasks.items()
                if now - t["created_at"] > self._ttl
            ]
            for tid in expired:
                del self._tasks[tid]


# 模块级单例
_task_store: TaskStore | None = None


def get_task_store() -> TaskStore:
    global _task_store
    if _task_store is None:
        _task_store = TaskStore()
    return _task_store
