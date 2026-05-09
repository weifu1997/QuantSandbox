# API Documentation

## Overview
QuantSandbox provides a RESTful API for quantitative simulation workflows.

Base URL: `/api`

## Endpoints

### Configuration Management

#### GET /api/config
Retrieve current configuration.

**Response:**
```json
{
  "status": "success",
  "stock_pool": ["AAPL", "MSFT"],
  "strategy": {
    "name": "momentum",
    "parameters": {"window": 20}
  }
}
```

#### POST /api/config
Update configuration.

**Request:**
```json
{
  "stock_pool": ["AAPL", "MSFT"],
  "strategy_name": "momentum",
  "strategy_parameters": {"window": 20}
}
```

**Response:**
```json
{
  "status": "success"
}
```

### System Meta

#### GET /api/meta
Get system meta information.

**Response:**
```json
{
  "status": "success",
  "latest_trade_date": "2024-01-01",
  "data_sources": {"tushare": "active", "akshare": "active"},
  "priority": ["tushare", "akshare"]
}
```

### Stock Data

#### GET /api/detail/{ticker}
Get detailed stock data for a specific ticker.

**Parameters:**
- `start_date` (optional): Start date in YYYYMMDD format
- `end_date` (optional): End date in YYYYMMDD format

**Response:**
```json
{
  "status": "success",
  "name": "Apple Inc.",
  "metadata": {...},
  "klines": [...],
  "logs": [...],
  "today_trades": [...],
  "data_source": "cache_first"
}
```

### MX Service Integrations

#### POST /api/mx/search
Search MX资讯.

**Request:**
```json
{
  "query": "人工智能概念股"
}
```

**Response:**
```json
{
  "status": "success",
  "results": {...}
}
```

#### POST /api/mx/data
Query MX金融数据.

**Request:**
```json
{
  "query": "AAPL 基本指标"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {...}
}
```

#### POST /api/mx/xuangu
Run MX智能选股.

**Request:**
```json
{
  "query": "低估值、高股息、业绩预增"
}
```

**Response:**
```json
{
  "status": "success",
  "candidates": [...]
}
```

#### POST /api/mx/moni
Query MX模拟组合.

**Request:**
```json
{
  "query": "我的模拟组合"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {...}
}
```

### Workflow Management

#### POST /api/workflows/low-value/run
Start a low value workflow.

**Request:**
```json
{
  "use_default_template": true,
  "batch_size": 5,
  "user_id": "test-user"
}
```

**Response:**
```json
{
  "status": "success",
  "run_id": "workflow-run-id"
}
```

#### GET /api/workflows/{run_id}
Get workflow run details.

**Response:**
```json
{
  "status": "success",
  "data": {
    "run": {
      "id": "run-id",
      "user_id": "user-123",
      "status": "completed",
      "started_at": "2024-01-01T00:00:00",
      "completed_at": "2024-01-01T00:05:00",
      "total_steps": 5,
      "config": {...}
    },
    "steps": [...],
    "candidates": [...],
    "watchlist": [...]
  }
}
```

#### GET /api/workflows/{run_id}/steps/{step_code}
Get specific workflow step details.

#### GET /api/workflows/{run_id}/candidates
Get candidates for a workflow run (with optional status filter).

#### GET /api/watchlist
Get all watchlist entries.

## 📊  Response Format

All API responses follow this format:

```json
{
  "status": "success|error",
  "data": {...},
  "error": "Error message (if status is error)"
}
```

## 🔐  Authentication

Some endpoints may require authentication. Use Bearer token in Authorization header:
```
Authorization: Bearer <token>
```

## ⏱️  Rate Limiting

API has rate limiting: 100 requests per minute per IP.

## 📚  Examples

### Example: Get stock detail
```bash
curl http://localhost:8000/api/detail/AAPL?start_date=20240101&end_date=20240201
```

### Example: Run workflow
```bash
curl -X POST http://localhost:8000/api/workflows/low-value/run \
  -H "Content-Type: application/json" \
  -d '{"use_default_template": true, "batch_size": 5, "user_id": "user123"}'
```

## 🚧  Error Handling

Common error codes:
- `400`: Bad request (invalid parameters)
- `404`: Not found (resource doesn't exist)
- `500`: Internal server error
- `429`: Too many requests (rate limiting)

## 📈  Monitoring

The API provides Prometheus metrics at `/metrics`.

