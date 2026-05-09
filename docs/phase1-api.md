# Phase 1 API Reference

## Base

All phase-1 workflow endpoints are mounted under `/api`.

---

## 1. Start low-value workflow

### `POST /api/workflows/low-value/run`

Start an async low-value workflow run.

### Request body

```json
{
  "use_default_template": true,
  "custom_query": null,
  "user_id": "test-user",
  "batch_size": 5
}
```

### Response

```json
{
  "status": "success",
  "run_id": "uuid"
}
```

---

## 2. List recent workflow runs

### `GET /api/workflows`

Returns recent workflow runs for the history page.

### Query params

- `limit` — integer, default 20, max 100
- `status` — optional (`running`, `completed`, `failed`)
- `user_id` — optional exact-match filter

### Response

```json
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "user_id": "test-user",
      "workflow_type": "low_value_discovery",
      "status": "completed",
      "started_at": "2026-05-09T09:00:00",
      "completed_at": "2026-05-09T09:01:00",
      "total_steps": 5,
      "config": {},
      "created_at": "2026-05-09T09:00:00",
      "updated_at": "2026-05-09T09:01:00"
    }
  ]
}
```

---

## 3. Get workflow run detail

### `GET /api/workflows/{run_id}`

Returns run metadata, steps, candidates, and watchlist output.

### Response shape

```json
{
  "status": "success",
  "data": {
    "run": {},
    "steps": [],
    "candidates": [],
    "watchlist": []
  }
}
```

---

## 4. Get one workflow step

### `GET /api/workflows/{run_id}/steps/{step_code}`

Returns detail for a single step.

### 404 cases

- workflow step not found

---

## 5. Get workflow candidates

### `GET /api/workflows/{run_id}/candidates`

### Optional query param

- `status` — candidate status filter

### Response

```json
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "symbol": "600000",
      "name": "示例股份",
      "status": "selected",
      "reason": {},
      "data": {},
      "created_at": "2026-05-09T09:00:00"
    }
  ]
}
```

---

## 6. Get watchlist

### `GET /api/watchlist`

Returns watchlist rows in reverse created order.

### Query params

- `view` — optional, `all` (default) or `latest`

### Related endpoint

- `GET /api/watchlist/latest` — explicit alias for `view=latest`

### Watchlist response example

```json
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "workflow_run_id": "run-uuid",
      "symbol": "603166",
      "name": "福达股份",
      "entry_reason": "PB 3.62；PE 31.38",
      "risk_level": "medium",
      "catalyst_factors": ["高分红"],
      "board": "主板",
      "pe_ttm": "31.38",
      "pb": "3.6164",
      "latest_price": "14.60",
      "dividend_yield": "0.6754",
      "month_return": "13.00",
      "st_flag": "否",
      "metrics": {
        "pe_ttm": 31.38,
        "pb": 3.6164,
        "latest_price": 14.6,
        "dividend_yield": 0.6754,
        "month_return": 13.0
      },
      "watch_price_zone": "4.04~5.25 元（PB 1.0~1.3）",
      "entry_date": "2026-05-09T09:00:00",
      "created_at": "2026-05-09T09:00:00"
    }
  ]
}
```

Notes:
- top-level string fields are retained for backward compatibility
- `metrics` exposes numeric watchlist values for future sorting/filtering and backend recompute support

---

## 7. Update watchlist entry

### `PATCH /api/watchlist/{entry_id}`

Partial update for phase-1 watchlist management.

### Request body

```json
{
  "entry_reason": "更新后的入池理由",
  "risk_level": "high",
  "catalyst_factors": ["业绩改善", "高分红"],
  "watch_price_zone": "10.00~12.00 元",
  "pb": "3.62",
  "latest_price": "14.60",
  "dividend_yield": "0.88"
}
```

### Notes

- `risk_level` must be one of the enum values in `RiskLevel`
- `catalyst_factors` may be an array or a delimited string
- invalid `risk_level` returns `400`
- missing entry returns `404`
- watchlist numeric text fields (`pe_ttm`, `pb`, `latest_price`, `dividend_yield`, `month_return`) are stored as text for compatibility and mirrored into numeric `metrics` values
- if a numeric text field cannot be parsed (for example `"--"`), its numeric mirror becomes `null` without clearing the text field

---

## 8. Delete one watchlist entry

### `DELETE /api/watchlist/{entry_id}`

### Response

```json
{
  "status": "success",
  "deleted": 1
}
```

---

## 9. Batch delete watchlist entries

### `POST /api/watchlist/batch-delete`

### Request body

```json
{
  "ids": ["uuid-1", "uuid-2"]
}
```

### Response

```json
{
  "status": "success",
  "deleted": 2
}
```

---

## Common error semantics

- `404` when a run or watchlist row does not exist
- `400` for malformed watchlist update values such as invalid `risk_level`
- successful responses use top-level `status: success`
