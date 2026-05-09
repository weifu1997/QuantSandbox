"""
Integration tests for config API endpoints.
"""
import pytest


def test_get_config(client):
    """Test getting config."""
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_update_config(client):
    """Test updating config."""
    response = client.post(
        "/api/config",
        json={
            "stock_pool": ["AAPL", "MSFT"],
            "strategy": {"name": "momentum", "parameters": {"window": 20}}
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
