from __future__ import annotations

import importlib
import time


def test_submit_xuangu_task_and_poll_completed(client, monkeypatch):
    mx_endpoints = importlib.import_module("backend.api.mx_endpoints")
    async_service_mod = importlib.import_module("backend.services.mx.xuangu_async_service")

    # ensure clean singleton store cache behavior for test readability
    svc = async_service_mod.XuanguAsyncService()

    class FakeXuanguService:
        def run_raw(self, query: str, timeout: int = 180):
            return {
                "stdout": "ok",
                "stderr": "",
                "raw_json": {
                    "data": {
                        "data": {
                            "securityCount": 1,
                            "totalCondition": "cond",
                            "responseConditionList": [{"describe": "A", "stockCount": 1}],
                            "allResults": {
                                "result": {
                                    "columns": [
                                        {"title": "代码", "key": "SECURITY_CODE"},
                                        {"title": "名称", "key": "SECURITY_SHORT_NAME"},
                                    ],
                                    "dataList": [
                                        {"SECURITY_CODE": "600519", "SECURITY_SHORT_NAME": "贵州茅台"}
                                    ],
                                    "total": 1,
                                }
                            },
                        }
                    }
                },
                "csv_path": "",
                "description_path": "",
                "output_dir": "/tmp",
                "returncode": 0,
            }

        def parse_core(self, raw):
            return {
                "hit_count": 1,
                "candidates": [{"symbol": "600519", "name": "贵州茅台"}],
                "excluded_checks": {"ST": True, "科创板": True, "创业板": True, "北交所": True},
                "csv_path": "",
                "description_path": "",
            }

        def enrich_candidates(self, parsed, raw):
            enriched = dict(parsed)
            enriched["candidates"] = [{**parsed["candidates"][0], "board": "上交所主板", "risk_flags": []}]
            return enriched

    monkeypatch.setattr(svc, "service", FakeXuanguService())
    monkeypatch.setattr(svc, "get_cached", lambda query: None)
    monkeypatch.setattr(mx_endpoints, "XuanguAsyncService", lambda: svc)

    submit = client.post("/api/mx/xuangu/tasks", json={"query": "测试选股-fresh"})
    assert submit.status_code == 200
    submit_body = submit.json()
    assert submit_body["status"] == "accepted"
    task_id = submit_body["data"]["task_id"]

    # poll until completed
    final = None
    for _ in range(20):
        resp = client.get(f"/api/mx/xuangu/tasks/{task_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["data"]["task_id"] == task_id
        if body["data"]["task_status"] == "completed":
            final = body["data"]
            break
        time.sleep(0.05)

    assert final is not None
    assert final["result"]["source"] == "fresh"
    assert final["result"]["parsed"]["hit_count"] == 1
    assert final["progress"]["stage"] == "done"


def test_submit_xuangu_task_cache_hit_returns_completed_task(client, monkeypatch):
    mx_endpoints = importlib.import_module("backend.api.mx_endpoints")
    async_service_mod = importlib.import_module("backend.services.mx.xuangu_async_service")
    svc = async_service_mod.XuanguAsyncService()

    monkeypatch.setattr(
        svc,
        "get_cached",
        lambda query: {
            "elapsed_ms": 321,
            "result": {
                "raw_json": {"data": {"data": {"securityCount": 0, "responseConditionList": [], "allResults": {"result": {"columns": [], "dataList": [], "total": 0}}}}},
                "parsed": {"hit_count": 0, "candidates": [], "excluded_checks": {"ST": True, "科创板": True, "创业板": True, "北交所": True}},
            },
        },
    )
    monkeypatch.setattr(mx_endpoints, "XuanguAsyncService", lambda: svc)

    submit = client.post("/api/mx/xuangu/tasks", json={"query": "缓存命中选股"})
    assert submit.status_code == 200
    task_id = submit.json()["data"]["task_id"]

    poll = client.get(f"/api/mx/xuangu/tasks/{task_id}")
    assert poll.status_code == 200
    body = poll.json()["data"]
    assert body["task_status"] == "completed"
    assert body["result"]["source"] == "cache"
    assert body["result"]["elapsed_ms"] == 321
    assert body["progress"]["message"] == "命中缓存"


def test_submit_xuangu_task_failure_exposes_error(client, monkeypatch):
    mx_endpoints = importlib.import_module("backend.api.mx_endpoints")
    async_service_mod = importlib.import_module("backend.services.mx.xuangu_async_service")
    svc = async_service_mod.XuanguAsyncService()

    class FakeFailXuanguService:
        def run_raw(self, query: str, timeout: int = 180):
            raise RuntimeError("远端超时")

        def parse_core(self, raw):
            return {}

        def enrich_candidates(self, parsed, raw):
            return parsed

    monkeypatch.setattr(svc, "service", FakeFailXuanguService())
    monkeypatch.setattr(mx_endpoints, "XuanguAsyncService", lambda: svc)

    submit = client.post("/api/mx/xuangu/tasks", json={"query": "失败选股"})
    assert submit.status_code == 200
    task_id = submit.json()["data"]["task_id"]

    final = None
    for _ in range(20):
        resp = client.get(f"/api/mx/xuangu/tasks/{task_id}")
        assert resp.status_code == 200
        body = resp.json()["data"]
        if body["task_status"] == "failed":
            final = body
            break
        time.sleep(0.05)

    assert final is not None
    assert "远端超时" in final["error"]
    assert final["progress"]["stage"] == "failed"
