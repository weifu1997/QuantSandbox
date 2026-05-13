# Sprint D 已知问题与修复记录

> 归档 D-6 ~ D-9 期间发现并修复的问题。
> 格式：症状 → 根因 → 修复 → 防回归措施

---

## 问题 1：Summary / Detail 仍走旧 StrategyFactory 路径

**症状**：`GET /api/summary` 返回 `"未知的策略名称: target_weight_demo"` 或 500 错误。

**根因**：Summary 和 Detail 端点通过 `StrategyFactory.generate_signals()` 路由策略，该工厂仅支持旧三种策略（dual_ma / bollinger_bands / rsi_reversal），不支持新注册的 `target_weight_demo`。

**修复**：
1. Summary 端点改为 `registry.create()` + `engine.run_with_positions()`
2. Detail 端点同步改为 `registry.create()` + `engine.run_with_positions()`
3. `config.yaml` 默认策略从 `bollinger_bands` 改为 `target_weight_demo`

**防回归测试**：
- `test_backtest_summary_diagnostics.py::test_summary_preserves...` — summary 新路径
- `test_backtest_summary_diagnostics.py::test_summary_unknown_strategy_returns_empty_not_500` — 未知策略不崩溃

---

## 问题 2：config.yaml 默认配置与新策略不匹配

**症状**：
- `stock_pool: [AAPL, MSFT]` — 美股数据源频繁 cooldown，接口返回全空
- `strategy.name: bollinger_bands` — 不在新 registry 中，导致 400 错误

**修复**：
- `stock_pool` 改为当前 A 股示例池：`[sh600901, sz000883, sh601033, sh601598, sh600098, sz002091, sh600177, sz000543, sh600795]`
- `strategy.name` 改为 `target_weight_demo`
- `strategy.parameters` 改为新策略参数（`rsi_period`, `max_target_weight`, `rebalance_threshold`）
- 测试用例禁止再用 `AAPL/MSFT` 写入运行时配置

**影响文件**：`config.yaml`

---

## 问题 3：Portfolio 单标的 per-ticker -100% 异常

**症状**：`POST /api/strategies/portfolio/backtest` 对只有 1 只标的且无交易的场景，返回 `per_ticker[ticker].total_return = -100%`, `final_equity = 0`。

**根因**：`_calculate_metrics()` 使用 `self.initial_cash`（100000）作为 baseline 计算收益率。但 `run_portfolio()` 在构建 per-ticker equity 时填充的是该标的持仓市值（`shares * close_price`），无买入时全为 0。导致 `(0 - 100000) / 100000 = -100%`。

**修复**（`engine.py:581-586`）：
```python
final_s = positions.get(ticker, {"shares": 0})["shares"]
tm["final_shares"] = final_s
if final_s == 0:
    tm["total_return"] = 0.0
    tm["max_drawdown"] = 0.0
    tm["sharpe_ratio"] = 0.0
```

**防回归测试**：
- `test_portfolio_backtest.py::TestPortfolioSingleTickerNoRegression::test_single_ticker_no_shares_no_false_loss`
- `test_portfolio_backtest.py::TestPortfolioSingleTickerNoRegression::test_portfolio_per_ticker_equity_all_zero_when_no_shares_held`

---

## 问题 4：前端仍残留旧策略心智

**症状**：
- WalkForward 页面缺失，用户无法从前端发起和查看 Walk-Forward
- Dashboard 保留"前进 30 天"推演按钮和动画逻辑
- ConfigManager 硬编码 120+ 行 `strategyMeta`（dual_ma / bollinger_bands / rsi_reversal）
- Detail 日志表仅 7 列，无法展示新仓位调仓日志

**修复**（D-6）：
1. 新建 `WalkForward.vue` + 路由 + 导航菜单
2. Dashboard 删除 `advance30Days()` 和按钮，添加 4 个导航卡片
3. ConfigManager 重写为动态加载 `GET /api/strategies` + `GET /api/factors`，按 `parameter_schema` 渲染表单
4. Detail 日志表扩展为 13 列（目标权重、当前权重、佣金、印花税、交易前后权益、现金等）

**防回归措施**：
- 前端 npm build 一键验证
- 路由可访问性手动验收

---

## 问题 5：旧策略删除后测试残留

**症状**：`tests/integration/test_backtest_summary_diagnostics.py` 使用 `StubStrategyFactory`、`StubEngine.run()`、旧 `backtest_endpoints.StrategyFactory` monkeypatch，删除后编译失败。

**修复**：测试文件重写为 `StubStrategyRegistry` + `StubEngine.run_with_positions()` + `backtest_endpoints.get_strategy_registry` monkeypatch。

**影响文件**：`tests/integration/test_backtest_summary_diagnostics.py`

---

## 问题 6：前端 API 方法命名不统一

**症状**：WalkForward / optimize / portfolio backtest 页面直接拼 URL，缺少统一 API 出口。

**修复**（D-6）：在 `frontend/src/api/index.js` 集中添加：
- `getStrategies()`, `getFactors()`
- `runWalkForward()`, `getWalkForwardTask()`
- `runPortfolioOptimize()`, `runPortfolioBacktest()`
- `runStrategyBacktest()`

---

## 未完成 / 已知限制

| 限制 | 说明 |
|---|---|
| 新 registry 只有 `target_weight_demo` | 后续可注册更多策略 |
| 基本面因子未接 MX data fallback | D-1 待完成项 |
| WebSocket 实时进度推送 | 待后续 Sprint |
| Portfolio 多标的组合偶发数据源 cooldown | 数据源容量限制 |
