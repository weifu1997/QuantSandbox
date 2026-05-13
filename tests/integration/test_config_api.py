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
            "stock_pool": ["sh600901", "sz000883"],
            "strategy_name": "multi_factor_target_weight",
            "strategy_parameters": {"rsi_period": 7, "max_target_weight": 0.3, "rebalance_threshold": 0.03}
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
