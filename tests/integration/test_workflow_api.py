"""
Integration tests for workflow API endpoints.
"""
import pytest


def test_run_low_value_workflow(client):
    """Test running a low value workflow."""
    response = client.post(
        "/api/workflows/low-value/run",
        json={
            "use_default_template": True,
            "batch_size": 5,
            "user_id": "test-user"
        }
    )
    assert response.status_code == 200
    assert "run_id" in response.json()


def test_get_workflow_run(client):
    """Test getting workflow run details."""
    response = client.post(
        "/api/workflows/low-value/run",
        json={
            "use_default_template": True,
            "batch_size": 5,
            "user_id": "test-user"
        }
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    response = client.get(f"/api/workflows/{run_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["data"]["run"]["id"] == run_id


def test_list_workflow_runs_returns_recent_runs(client):
    """Test listing recent workflow runs."""
    for idx in range(2):
        response = client.post(
            "/api/workflows/low-value/run",
            json={
                "use_default_template": True,
                "batch_size": 5,
                "user_id": f"test-user-{idx}",
            },
        )
        assert response.status_code == 200

    response = client.get("/api/workflows", params={"limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 2
    first = body["data"][0]
    assert set(first.keys()) >= {
        "id",
        "user_id",
        "status",
        "started_at",
        "completed_at",
        "total_steps",
        "created_at",
    }


def test_update_watchlist_entry(client):
    """Test updating a watchlist entry."""
    response = client.post(
        "/api/workflows/low-value/run",
        json={
            "use_default_template": True,
            "batch_size": 5,
            "user_id": "test-user"
        }
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    workflow = client.get(f"/api/workflows/{run_id}")
    assert workflow.status_code == 200
    watchlist = workflow.json()["data"]["watchlist"]
    if not watchlist:
        pytest.skip("workflow produced no watchlist entries in this environment")

    entry = watchlist[0]
    response = client.patch(
        f"/api/watchlist/{entry['id']}",
        json={
            "entry_reason": "更新后的入池理由",
            "risk_level": "high",
            "catalyst_factors": ["业绩改善", "高分红"],
            "watch_price_zone": "10.00~12.00 元",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["entry_reason"] == "更新后的入池理由"
    assert payload["data"]["risk_level"] == "high"
    assert payload["data"]["watch_price_zone"] == "10.00~12.00 元"
    assert payload["data"]["catalyst_factors"] == ["业绩改善", "高分红"]
