from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from backend.core.task_store import TaskStore, TaskStatus
from backend.services.mx.xuangu_service import XuanguService

CACHE_DIR = Path("/root/project/QuantSandbox/data/mx_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SECONDS = 30 * 60
CACHE_MAX_FILES = 200


def _normalize_query(query: str) -> str:
    text = " ".join(str(query or "").strip().split())
    return text.replace("：", ":")


def _query_hash(query: str) -> str:
    return hashlib.sha256(_normalize_query(query).encode("utf-8")).hexdigest()[:24]


class XuanguAsyncService:
    tool_name = "mx-xuangu"

    def __init__(self) -> None:
        self.service = XuanguService()
        self.store = TaskStore.get_instance()

    def _cache_path(self, query: str) -> Path:
        return CACHE_DIR / f"xuangu_{_query_hash(query)}.json"

    def cleanup_cache(self) -> dict[str, int]:
        removed = 0
        files = sorted(CACHE_DIR.glob("xuangu_*.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0)
        now = time.time()
        for path in files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                created_at = float(payload.get("created_at", 0) or 0)
                if not created_at or now - created_at > CACHE_TTL_SECONDS:
                    path.unlink(missing_ok=True)
                    removed += 1
            except Exception:
                path.unlink(missing_ok=True)
                removed += 1
        files = sorted(CACHE_DIR.glob("xuangu_*.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0)
        overflow = max(0, len(files) - CACHE_MAX_FILES)
        for path in files[:overflow]:
            path.unlink(missing_ok=True)
            removed += 1
        return {"removed": removed, "remaining": len(list(CACHE_DIR.glob('xuangu_*.json')))}

    def get_cached(self, query: str) -> dict[str, Any] | None:
        path = self._cache_path(query)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        created_at = float(payload.get("created_at", 0) or 0)
        if not created_at or time.time() - created_at > CACHE_TTL_SECONDS:
            return None
        payload["cache_age_ms"] = int((time.time() - created_at) * 1000)
        return payload

    def set_cached(self, query: str, result: dict[str, Any], elapsed_ms: int) -> None:
        path = self._cache_path(query)
        payload = {
            "query": query,
            "normalized_query": _normalize_query(query),
            "query_hash": _query_hash(query),
            "created_at": time.time(),
            "elapsed_ms": elapsed_ms,
            "source": "fresh",
            "result": result,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def submit(self, query: str, timeout: int = 180) -> dict[str, Any]:
        cleanup = self.cleanup_cache()
        cached = self.get_cached(query)
        if cached:
            task = self.store.create_task(payload={"tool": self.tool_name, "query": query, "cache_hit": True})
            task.status = TaskStatus.COMPLETED
            task.started_at = task.created_at
            task.completed_at = task.created_at
            task.progress = {"current": 5, "total": 5, "stage": "done", "message": "命中缓存"}
            task.result = {
                "status": "success",
                "tool": self.tool_name,
                "query": query,
                "elapsed_ms": int(cached.get("elapsed_ms", 0) or 0),
                "cache_age_ms": int(cached.get("cache_age_ms", 0) or 0),
                "timings": dict((cached.get("result") or {}).get("timings") or {}),
                **dict(cached.get("result") or {}),
                "source": "cache",
            }
            return {"task_id": task.task_id, "cache_hit": True, "cache_cleanup": cleanup}

        task = self.store.create_task(payload={"tool": self.tool_name, "query": query, "cache_hit": False})
        thread = threading.Thread(target=self._run_task, args=(task.task_id, query, timeout), daemon=True)
        thread.start()
        return {"task_id": task.task_id, "cache_hit": False, "cache_cleanup": cleanup}

    def _run_task(self, task_id: str, query: str, timeout: int) -> None:
        task = self.store.get_task(task_id)
        if task is None:
            return
        task.status = TaskStatus.RUNNING
        task.started_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        started = time.time()
        try:
            task.progress = {"current": 0, "total": 5, "stage": "starting", "message": "开始处理查询"}
            task.progress = {"current": 1, "total": 5, "stage": "running_remote_query", "message": "正在执行妙想选股"}
            remote_started = time.time()
            raw = self.service.run_raw(query, timeout=timeout)
            remote_elapsed_ms = int((time.time() - remote_started) * 1000)

            task.progress = {"current": 2, "total": 5, "stage": "parsing_core", "message": "正在解析主结果"}
            core_started = time.time()
            parsed = self.service.parse_core(raw)
            core_elapsed_ms = int((time.time() - core_started) * 1000)

            task.progress = {"current": 3, "total": 5, "stage": "enriching_candidates", "message": "正在补充增强字段"}
            enrich_started = time.time()
            enriched = self.service.enrich_candidates(parsed, raw)
            enrich_elapsed_ms = int((time.time() - enrich_started) * 1000)

            task.progress = {"current": 4, "total": 5, "stage": "writing_cache", "message": "正在写入缓存"}
            timings = {
                "remote_elapsed_ms": remote_elapsed_ms,
                "core_parse_elapsed_ms": core_elapsed_ms,
                "enrich_elapsed_ms": enrich_elapsed_ms,
            }
            result = {
                "status": "success",
                "tool": self.tool_name,
                "query": query,
                "source": "fresh",
                **raw,
                "parsed": enriched,
                "timings": timings,
            }
            elapsed_ms = int((time.time() - started) * 1000)
            self.set_cached(query, result, elapsed_ms)
            task.result = {**result, "elapsed_ms": elapsed_ms}
            task.status = TaskStatus.COMPLETED
            task.progress = {"current": 5, "total": 5, "stage": "done", "message": f"完成，耗时 {elapsed_ms}ms"}
            task.completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.progress = {"current": 5, "total": 5, "stage": "failed", "message": str(e)}
            task.completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

    def get_task_result(self, task_id: str) -> dict[str, Any] | None:
        task = self.store.get_task(task_id)
        if task is None:
            return None
        return {
            "task_id": task.task_id,
            "task_status": task.status,
            "progress": dict(task.progress),
            "result": task.result,
            "error": task.error,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
        }
