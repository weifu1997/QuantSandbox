# Phase 1 Workflow Overview

## Scope

Phase 1 delivers the **低估发现流** MVP for QuantSandbox. The goal is to let a user start a workflow run, inspect step-by-step execution, review generated candidates, and manage the resulting watchlist entries.

## Workflow Steps

The backend workflow runner lives at `backend/workflows/low_value_flow/runner.py` and executes these steps in order:

1. `xuangu` — run 妙想选股 query via `XuanguService`
2. `risk` — quick rejection pass for obvious ST / loss expansion risks
3. `data` — fetch structured security data via `DataService` in batches
4. `search` — gather search/news context via `SearchService`
5. `zixuan` — sync or summarize final watchlist output via `ZixuanService`

## Inputs

Workflow input schema: `backend/workflows/low_value_flow/schemas.py`

- `use_default_template: bool`
- `custom_query: str | None`
- `user_id: str | None`
- `batch_size: int`

### Default template behavior

`build_default_query()` generates a default low-value query with these defaults:

- market scope: `全A`
- exclude ST
- exclude 科创板
- exclude 创业板
- exclude 北交所
- `PE < 20`
- `PB < 2`
- `股息率 > 2%`
- `近1月跌幅 > 8%`

## Data Model Summary

Core phase-1 tables:

- `workflow_runs`
- `workflow_step_runs`
- `candidates`
- `candidate_reviews`
- `watchlist_entries`

### Run statuses

`workflow_runs.status`:

- `running`
- `completed`
- `failed`

### Step statuses

Each row in `workflow_step_runs` records:

- `step_code`
- `step_name`
- `status`
- `started_at`
- `completed_at`
- `result_data`
- `error_message`

### Candidate statuses

`candidates.status`:

- `pending`
- `selected`
- `eliminated`
- `insufficient_data`

## Batch processing behavior

`mx-data` batching is controlled by:

- request `batch_size`
- `backend/workflows/common/batching.py`
- runner-side orchestration in `LowValueWorkflowRunner`

Current phase-1 behavior:

- symbols are chunked into batches
- each batch is queried independently
- partial field gaps are surfaced into structured warnings
- downstream review logic can mark entries as `insufficient_data`

## Watchlist output

Each watchlist row may contain:

- `symbol`
- `name`
- `entry_reason`
- `risk_level`
- `catalyst_factors`
- `watch_price_zone`
- `entry_date`
- `workflow_run_id`

### `watch_price_zone`

`watch_price_zone` is stored as a plain text field and displayed directly in the frontend. Phase 1 does not enforce a strict numeric schema; the workflow can write a descriptive range such as `10.00~12.00 元`.

## Failure handling

Phase 1 failure handling rules:

- the workflow run is created before async execution starts
- each completed step writes its result to `workflow_step_runs`
- if a step fails, the step row should capture `error_message`
- failed runs remain queryable from `/api/workflows/{run_id}`
- already-persisted candidates/watchlist rows are not implicitly rolled back as a product feature

## Frontend pages

Phase 1 frontend pages:

- `/workflow` — execution page
- `/workflow/history` — recent workflow runs
- `/workflow/:runId` — workflow detail page
- `/watchlist` — watchlist browser/editor

## Manual verification checklist

1. Start a run from `/workflow`
2. Confirm run appears in `/workflow/history`
3. Open `/workflow/:runId` and verify steps/candidates/watchlist render
4. Open `/watchlist` and edit a row
5. Refresh `/watchlist` and confirm updates persist
