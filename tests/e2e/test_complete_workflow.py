"""
End-to-end test for complete workflow.
"""
import pytest
import time


def test_complete_workflow(client, db_session):
    """Test complete low value workflow from start to finish."""
    # Start the workflow
    response = client.post(
        "/api/workflows/low-value/run",
        json={
            "use_default_template": True,
            "batch_size": 3,
            "user_id": "test-user"
        }
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    
    # Wait for workflow to complete (polling)
    import time
    start_time = time.time()
    max_wait = 30  # seconds
    
    while time.time() - start_time < max_wait:
        response = client.get(f"/api/workflows/{run_id}")
        assert response.status_code == 200
        status = response.json()["data"]["run"]["status"]
        
        if status == "completed":
            break
        elif status == "failed":
            raise Exception(f"Workflow failed: {response.json()['data']['run'].get('error_message', 'No error message')}")
        
        time.sleep(1)
    
    # Verify workflow completed successfully
    assert status == "completed"
    
    # Check candidates
    response = client.get(f"/api/workflows/{run_id}/candidates")
    assert response.status_code == 200
    candidates = response.json()["data"]
    assert isinstance(candidates, list)
    
    # Check watchlist
    response = client.get("/api/watchlist")
    assert response.status_code == 200
    watchlist = response.json()["data"]
    assert isinstance(watchlist, list)
