from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

import pandas as pd

from backend.api.config_endpoints import get_data_center, load_config
from backend.core.engine import BacktestEngine
from backend.core.task_store import TaskStore, TaskStatus
from backend.core.strategies.registry import get_strategy_registry

CACHE_DIR = Path('/root/project/QuantSandbox/data/summary_cache')
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SECONDS = 15 * 60
CACHE_MAX_FILES = 100


def _normalize_ticker_output(ticker: str) -> str:
    value = str(ticker or '').strip()
    if len(value) > 2 and value[:2].lower() in {'sh', 'sz', 'bj'} and value[2:].isdigit():
        return value[2:]
    return value


def _resolve_stock_name(df: pd.DataFrame, ticker: str) -> str:
    if not df.empty and 'name' in df.columns:
        name = str(df['name'].iloc[0] or '').strip()
        if name:
            return name
    try:
        return str(get_data_center().get_stock_name(ticker) or '').strip()
    except Exception:
        return ''


def _extract_today_trades(logs: list[dict], end_date: str) -> list[dict]:
    today_str = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
    return [
        {"action": l.get("action"), "price": l.get("price"), "shares": l.get("shares")}
        for l in logs if str(l.get("execution_date", "")).startswith(today_str)
    ]


def _extract_fetch_diagnostics(df: pd.DataFrame) -> dict[str, Any]:
    return {
        'data_source': str(df.attrs.get('data_source', '') or ''),
        'resolved_source': str(df.attrs.get('resolved_source', '') or ''),
        'cache_miss': bool(df.attrs.get('cache_miss', False)),
        'fallback_trace': list(df.attrs.get('fallback_trace', []) or []),
        'source_detail': str(df.attrs.get('source_detail', '') or ''),
        'fetch_note': str(df.attrs.get('fetch_note', '') or '').strip(),
    }


def _build_empty_error(ticker: str) -> dict:
    return {
        'ticker': ticker,
        'reason': 'empty_dataframe',
        'message': f'{ticker} 在指定区间无可用数据',
        'data_source': '',
        'resolved_source': '',
        'cache_miss': None,
        'fallback_trace': [],
        'source_detail': '',
    }


def _build_exception_error(ticker: str, exc: Exception) -> dict:
    return {
        'ticker': ticker,
        'reason': type(exc).__name__,
        'message': str(exc),
        'data_source': '',
        'resolved_source': '',
        'cache_miss': None,
        'fallback_trace': [],
        'source_detail': '',
    }


class SummaryAsyncService:
    def __init__(self) -> None:
        self.store = TaskStore.get_instance()

    def _config_snapshot(self) -> dict[str, Any]:
        config = load_config()
        return {
            'stock_pool': list(config.get('stock_pool', []) or []),
            'strategy': dict(config.get('strategy', {}) or {}),
            'account': dict(config.get('account', {}) or {}),
        }

    def _cache_key_payload(self, start_date: str, end_date: str) -> dict[str, Any]:
        snap = self._config_snapshot()
        return {
            'start_date': start_date,
            'end_date': end_date,
            'stock_pool': list(snap.get('stock_pool', [])),
            'strategy': snap.get('strategy', {}),
            'account': snap.get('account', {}),
        }

    def _cache_path(self, start_date: str, end_date: str) -> Path:
        payload = self._cache_key_payload(start_date, end_date)
        key = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:24]
        return CACHE_DIR / f'summary_{key}.json'

    def cleanup_cache(self) -> dict[str, int]:
        removed = 0
        files = sorted(CACHE_DIR.glob('summary_*.json'), key=lambda p: p.stat().st_mtime if p.exists() else 0)
        now = time.time()
        for path in files:
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
                created_at = float(payload.get('created_at', 0) or 0)
                if not created_at or now - created_at > CACHE_TTL_SECONDS:
                    path.unlink(missing_ok=True)
                    removed += 1
            except Exception:
                path.unlink(missing_ok=True)
                removed += 1
        files = sorted(CACHE_DIR.glob('summary_*.json'), key=lambda p: p.stat().st_mtime if p.exists() else 0)
        overflow = max(0, len(files) - CACHE_MAX_FILES)
        for path in files[:overflow]:
            path.unlink(missing_ok=True)
            removed += 1
        return {'removed': removed, 'remaining': len(list(CACHE_DIR.glob('summary_*.json')))}

    def get_cached(self, start_date: str, end_date: str) -> dict[str, Any] | None:
        path = self._cache_path(start_date, end_date)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return None
        created_at = float(payload.get('created_at', 0) or 0)
        if not created_at or time.time() - created_at > CACHE_TTL_SECONDS:
            return None
        payload['cache_age_ms'] = int((time.time() - created_at) * 1000)
        return payload

    def set_cached(self, start_date: str, end_date: str, result: dict[str, Any], elapsed_ms: int) -> None:
        path = self._cache_path(start_date, end_date)
        payload = {
            'created_at': time.time(),
            'elapsed_ms': elapsed_ms,
            'result': result,
            'cache_key_payload': self._cache_key_payload(start_date, end_date),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    async def _fetch_stock_data(self, ticker: str, start_date: str, end_date: str, timeout: int = 30):
        dc = get_data_center()
        return await asyncio.wait_for(asyncio.to_thread(dc.fetch_stock_data, ticker, start_date, end_date), timeout=timeout)

    async def build_summary(self, start_date: str, end_date: str, task: Any | None = None) -> dict[str, Any]:
        config = load_config()
        stock_pool = config.get('stock_pool', []) or []
        strategy_conf = config.get('strategy', {}) or {}
        strategy_name = strategy_conf.get('name', 'multi_factor_target_weight')
        strategy_params = strategy_conf.get('parameters', {}) or {}
        account_conf = config.get('account', {}) or {}
        registry = get_strategy_registry()

        if not stock_pool:
            return {'status': 'success', 'data': [], 'data_source': 'empty_pool', 'fetch_note': '股票池为空'}
        try:
            registry.get(strategy_name)
        except KeyError:
            return {'status': 'success', 'data': [], 'data_source': 'unknown_strategy', 'fetch_note': f'未知策略: {strategy_name}'}

        rows: list[dict[str, Any]] = []
        source_tags: list[str] = []
        notes: list[str] = []
        errors: list[dict] = []

        total_tickers = len(stock_pool)
        for idx, ticker in enumerate(stock_pool, start=1):
            if task is not None:
                task.progress = {
                    'current': idx,
                    'total': total_tickers,
                    'stage': 'processing_ticker',
                    'message': f'正在处理 {idx}/{total_tickers}: {ticker}',
                    'ticker': ticker,
                    'completed_tickers': idx - 1,
                    'total_tickers': total_tickers,
                }
            try:
                df = await self._fetch_stock_data(ticker, start_date, end_date, timeout=30)
                if df is None or df.empty:
                    errors.append(_build_empty_error(ticker))
                    continue
                diag = _extract_fetch_diagnostics(df)
                source_tags.append(diag['data_source'])
                if diag['fetch_note']:
                    notes.append(diag['fetch_note'])
                strategy = registry.create(strategy_name, strategy_params)
                targets = strategy.generate_targets(df, ticker)
                engine = BacktestEngine(
                    initial_cash=float(account_conf.get('initial_cash', 100000.0)),
                    commission_rate=float(account_conf.get('commission_rate', 0.00025)),
                    tax_rate=float(account_conf.get('tax_rate', 0.0005)),
                )
                result = engine.run_with_positions(df, ticker, targets)
                metrics = result.get('metadata', {}) or {}
                logs = result.get('logs', []) or []
                stock_name = _resolve_stock_name(df, ticker)
                output_ticker = _normalize_ticker_output(ticker)
                rows.append({
                    'ticker': output_ticker,
                    'display_name': stock_name or output_ticker,
                    'name': stock_name,
                    'strategy': strategy.meta().get('description') or strategy_name,
                    'final_equity': metrics.get('final_equity', 0),
                    'return_rate': metrics.get('total_return', 0),
                    'position_return': metrics.get('position_return', 0),
                    'avg_deployed_ratio': metrics.get('avg_deployed_ratio', 0),
                    'trade_count': metrics.get('trade_count', 0),
                    'today_trades': _extract_today_trades(logs, end_date),
                })
            except Exception as exc:
                errors.append(_build_exception_error(ticker, exc))

        if errors and not rows:
            return {'status': 'success', 'data': [], 'data_source': 'unavailable', 'fetch_note': '全部股票获取失败', 'errors': errors}

        unique_sources = {s for s in source_tags if s}
        if any('cache_plus' in s for s in unique_sources):
            data_source = 'cache_partial'
        elif any(s in {'tushare', 'remote'} for s in unique_sources):
            data_source = 'partial_fetch'
        elif unique_sources == {'cache'}:
            data_source = 'cache_first'
        else:
            data_source = next(iter(unique_sources), 'unknown')
        fetch_note = '；'.join(sorted(set(n for n in notes if n)))
        if errors:
            err_note = f'部分股票失败：{len(errors)} 只'
            fetch_note = f'{fetch_note}；{err_note}' if fetch_note else err_note
        return {'status': 'success', 'data': rows, 'data_source': data_source, 'fetch_note': fetch_note, 'errors': errors}

    def submit(self, start_date: str, end_date: str) -> dict[str, Any]:
        cleanup = self.cleanup_cache()
        cached = self.get_cached(start_date, end_date)
        if cached:
            task = self.store.create_task(payload={'tool': 'summary', 'start_date': start_date, 'end_date': end_date, 'cache_hit': True})
            task.status = TaskStatus.COMPLETED
            task.started_at = task.created_at
            task.completed_at = task.created_at
            task.progress = {'current': 1, 'total': 1, 'stage': 'done', 'message': '命中缓存'}
            task.result = {
                **dict(cached.get('result') or {}),
                'source': 'cache',
                'elapsed_ms': int(cached.get('elapsed_ms', 0) or 0),
                'cache_age_ms': int(cached.get('cache_age_ms', 0) or 0),
                'cache_cleanup': cleanup,
            }
            return {'task_id': task.task_id, 'cache_hit': True, 'cache_cleanup': cleanup}
        task = self.store.create_task(payload={'tool': 'summary', 'start_date': start_date, 'end_date': end_date, 'cache_hit': False})
        threading.Thread(target=self._run_task, args=(task.task_id, start_date, end_date), daemon=True).start()
        return {'task_id': task.task_id, 'cache_hit': False, 'cache_cleanup': cleanup}

    def _run_task(self, task_id: str, start_date: str, end_date: str) -> None:
        task = self.store.get_task(task_id)
        if task is None:
            return
        cleanup = self.cleanup_cache()
        task.status = TaskStatus.RUNNING
        task.started_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
        started = time.time()
        try:
            task.progress = {'current': 0, 'total': 1, 'stage': 'loading_config', 'message': '正在读取配置'}
            result = asyncio.run(self.build_summary(start_date, end_date, task=task))
            task.progress = {'current': 1, 'total': 1, 'stage': 'writing_cache', 'message': '正在写入缓存'}
            elapsed_ms = int((time.time() - started) * 1000)
            result = {**result, 'source': 'fresh', 'elapsed_ms': elapsed_ms, 'cache_cleanup': cleanup}
            self.set_cached(start_date, end_date, result, elapsed_ms)
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.progress = {'current': 1, 'total': 1, 'stage': 'done', 'message': f'完成，耗时 {elapsed_ms}ms'}
            task.completed_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.progress = {'current': 1, 'total': 1, 'stage': 'failed', 'message': str(e)}
            task.completed_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()

    def get_task_result(self, task_id: str) -> dict[str, Any] | None:
        task = self.store.get_task(task_id)
        if task is None:
            return None
        return {
            'task_id': task.task_id,
            'task_status': task.status,
            'progress': dict(task.progress),
            'result': task.result,
            'error': task.error,
            'created_at': task.created_at,
            'started_at': task.started_at,
            'completed_at': task.completed_at,
        }
