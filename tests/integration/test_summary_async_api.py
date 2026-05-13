from __future__ import annotations

import importlib
import time


def test_submit_summary_task_and_poll_completed(client, monkeypatch):
    backtest_endpoints = importlib.import_module("backend.api.backtest_endpoints")
    summary_service_mod = importlib.import_module("backend.services.summary_async_service")
    svc = summary_service_mod.SummaryAsyncService()

    async def fake_build_summary(start_date: str, end_date: str, task=None):
        if task is not None:
            task.progress = {
                'current': 1,
                'total': 2,
                'stage': 'processing_ticker',
                'message': '正在处理 1/2: AAA',
                'ticker': 'AAA',
                'completed_tickers': 0,
                'total_tickers': 2,
            }
        return {
            'status': 'success',
            'data': [{'ticker': 'AAA', 'display_name': 'Alpha', 'final_equity': 10000, 'return_rate': 1.23, 'trade_count': 1, 'today_trades': []}],
            'data_source': 'cache_partial',
            'fetch_note': '缓存未覆盖区间，自动拉远端',
            'errors': [],
        }

    monkeypatch.setattr(svc, 'build_summary', fake_build_summary)
    monkeypatch.setattr(svc, 'get_cached', lambda s, e: None)
    monkeypatch.setattr(backtest_endpoints, 'SummaryAsyncService', lambda: svc)

    submit = client.post('/api/summary/tasks', params={'start_date': '20240101', 'end_date': '20240131'})
    assert submit.status_code == 200
    body = submit.json()
    assert body['status'] == 'accepted'
    task_id = body['data']['task_id']

    final = None
    for _ in range(20):
        resp = client.get(f'/api/summary/tasks/{task_id}')
        assert resp.status_code == 200
        payload = resp.json()['data']
        if payload['task_status'] == 'completed':
            final = payload
            break
        time.sleep(0.05)

    assert final is not None
    assert final['result']['source'] == 'fresh'
    assert final['result']['data'][0]['ticker'] == 'AAA'
    assert final['progress']['stage'] == 'done'


def test_submit_summary_task_cache_hit(client, monkeypatch):
    backtest_endpoints = importlib.import_module("backend.api.backtest_endpoints")
    summary_service_mod = importlib.import_module("backend.services.summary_async_service")
    svc = summary_service_mod.SummaryAsyncService()
    monkeypatch.setattr(svc, 'get_cached', lambda s, e: {
        'elapsed_ms': 123,
        'result': {'status': 'success', 'data': [], 'data_source': 'cache_first', 'fetch_note': 'cached'},
    })
    monkeypatch.setattr(backtest_endpoints, 'SummaryAsyncService', lambda: svc)

    submit = client.post('/api/summary/tasks', params={'start_date': '20240101', 'end_date': '20240131'})
    assert submit.status_code == 200
    task_id = submit.json()['data']['task_id']
    poll = client.get(f'/api/summary/tasks/{task_id}')
    assert poll.status_code == 200
    body = poll.json()['data']
    assert body['task_status'] == 'completed'
    assert body['result']['source'] == 'cache'
    assert body['result']['elapsed_ms'] == 123


def test_summary_sync_endpoint_still_works_via_service(client, monkeypatch):
    summary_service_mod = importlib.import_module("backend.services.summary_async_service")
    monkeypatch.setattr(summary_service_mod, 'load_config', lambda: {
        'stock_pool': ['AAA'],
        'strategy': {'name': 'nonexistent_strategy', 'parameters': {}},
        'account': {'initial_cash': 100000},
    })
    response = client.get('/api/summary', params={'start_date': '20240101', 'end_date': '20240131'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'success'
    assert payload['data'] == []
    assert payload['data_source'] == 'unknown_strategy'
