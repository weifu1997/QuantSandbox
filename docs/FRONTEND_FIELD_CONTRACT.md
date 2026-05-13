# 策略体系前端字段契约

> 本文档定义前端页面与后端 API 返回字段的依赖关系。
> 更新时间：2026-05-12

---

## 1. 命名约定

| 术语 | 语义 | 出现端点 |
|---|---|---|
| `metadata` | 单标的/单次回测核心指标（final_equity, total_return, ...） | backtest, detail, portfolio |
| `metrics` | 数值指标集合 | portfolio_metrics, test_metrics |
| `data` | 主返回载体（summary 行、图表数据） | summary, backtest envelope |
| `details` | 列表展开内容（完整回测对象） | backtest envelope |
| `window_summary` | Walk-Forward 顶层窗口聚合 | walk-forward |
| `klines` | K 线数组（含 target_weight, total_equity, position_mode） | backtest, detail |
| `logs` | 交易日志数组 | 所有回测端点 |
| `per_ticker` | 按标的拆分的子结果 | portfolio, optimize |

## 2. 页面字段依赖

### Detail.vue

| 用途 | 来源 `/api/detail/{ticker}` | 类型 |
|---|---|---|
| 头部指标卡片 | `metadata.final_equity`, `metadata.total_return`, `metadata.trade_count` | number |
| 标的名称 | `name`（带 `resolveStockName` 回退） | string |
| K 线图 | `klines[].date`, `klines[].open/high/low/close`, `klines[].total_equity` | array |
| 权益曲线 | `klines[].date`, `klines[].total_equity` | array |
| 交易日志表 | `logs[].action`, `logs[].price`, `logs[].shares`, `logs[].target_weight/current_weight/commission/tax/cash_before/cash_after/equity_before/equity_after/position_mode/execution_date` | array |
| 策略标签 | `metadata.strategy_name`（fallback: `'target_weight_demo'`） | string |

### WalkForward.vue

| 用途 | 来源 `/api/strategies/walk-forward` | 类型 |
|---|---|---|
| 窗口列表 | `windows[]` | array |
| 窗口索引 | `windows[].window_index` | number |
| 窗口状态 | `windows[].status` — `"evaluated"` / `"optimized"` | string |
| 优化结果 | `windows[].optimize_result.per_ticker[].best_params/best_objective/candidate_count` | object |
| 回测结果 | `windows[].backtest_results[].final_equity/total_return/trade_count/position_mode` | object |
| 窗口摘要 | `window_summary.window_status_counts` | object |
| 异步任务 | 提交: `{status:"accepted", data:{task_id}}`; 查询: `{status:"success", data:{task_id,task_status,progress,result,error}}` | object |

### Dashboard.vue

| 用途 | 来源 `/api/summary` | 类型 |
|---|---|---|
| 汇总表行 | `data[].ticker`, `data[].display_name`, `data[].return_rate`, `data[].trade_count`, `data[].final_equity` | array |
| 导航卡片 | —（纯前端） | — |

### ConfigManager.vue

| 用途 | 来源 `/api/strategies`, `/api/factors` | 类型 |
|---|---|---|
| 策略下拉 | `GET /api/strategies` → `strategies[].name`, `strategies[].description` | array |
| 因子列表 | `GET /api/factors` → `factors[].name`, `factors[].category` | array |
| 参数表单 | `GET /api/strategies/{name}` → `strategy.parameter_schema` | object |
| 回测触发 | `POST /api/strategies/backtest` → 统一 envelope | object |

## 3. 前端字段读取最佳实践

```js
// ✅ 推荐：用统一 helper
import axios from 'axios'
export const api = axios.create({ baseURL: '/api' })

export const unwrapResponse = (res, defaultValue = {}) => {
  const data = res?.data || {}
  if (data.status === 'success' || data.status === 'accepted') {
    return data
  }
  return defaultValue
}

// ✅ 推荐：页面内按模式读取
if (data.mode === 'single' || data.mode === 'multi') {
  // 统一 envelope 处理
  const rows = data.data       // summary 行
  const details = data.details // 完整详情
}

// ❌ 避免：裸读 axios response
res.data.ticker  // 单标的改用 res.data.details[0].ticker
```

## 4. 向后兼容承诺

以下字段在 1.0 前不会变更：

- `status` — 所有端点顶层必有
- `data` — 主载体
- `details` — 详情数组
- `metadata.final_equity`, `metadata.total_return`, `metadata.trade_count`
- `klines[].date/open/high/low/close`
- `logs[].action/price/shares`
- `window_summary.window_status_counts`