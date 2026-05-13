from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Task:
    def __init__(self, task_id: str, payload: dict[str, Any] | None = None):
        self.task_id = task_id
        self.status = TaskStatus.PENDING
        self.progress: dict[str, Any] = {"current": 0, "total": 0, "message": ""}
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at: str | None = None
        self.completed_at: str | None = None
        self.payload = payload or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "progress": dict(self.progress),
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class TaskStore:
    """进程内任务存储，单例。"""

    _instance: TaskStore | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    @classmethod
    def get_instance(cls) -> TaskStore:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create_task(self, payload: dict[str, Any] | None = None) -> Task:
        task_id = str(uuid.uuid4())
        task = Task(task_id, payload)
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def update_task(self, task_id: str, **kwargs: Any) -> Task | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        return task

    def remove_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False
