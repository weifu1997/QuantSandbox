# Sprint D 迁移完成报告

> 生成时间：2026-05-12
> 覆盖范围：D-6 ~ D-9

---

## 1. 旧体系删除清单

| 删除项 | 文件 | 行数 |
|---|---|---|
| DualMaStrategy | `backend/core/strategies/dual_ma.py` | 21 行 — **已删除** |
| BollingerBandsStrategy | `backend/core/strategies/bollinger_bands.py` | ~30 行 — **已删除** |
| RsiReversalStrategy | `backend/core/strategies/rsi_reversal.py` | ~30 行 — **已删除** |
| StrategyFactory 类 | `backend/core/strategy.py` | 36 行 — **已删除** |
| 旧策略 imports | `backend/core/strategy.py` | 4 行 — **已删除** |
| 引擎 `run()` 方法 | `backend/core/engine.py` | 153 行 — **已删除** |
| 引擎 `_add_log()` 方法 | `backend/core/engine.py` | 12 行 — **已删除** |
| 旧策略 label 映射 | `backend/api/backtest_endpoints.py` | 3 行 — **已清理** |
| 前端 `bollinger_bands` 回退值 | `frontend/src/views/Detail.vue` | — **已改为 target_weight_demo** |
| 硬编码 `strategyMeta` | `frontend/src/views/ConfigManager.vue` | ~120 行 — **已重写为动态加载** |

**总计删除：~290 行业务代码。**

## 2. 新体系当前能力

### 2.1 后端引擎

| 方法 | 用途 | 状态 |
|---|---|---|
| `run_with_positions()` | 单标的 target_weight 撮合引擎 | ✅ 标准路径 |
| `run_portfolio()` | 多标的组合级回测（共享现金池） | ✅ 标准路径 |
| `GridOptimizer` | 参数网格扫描 + best_params 选择 | ✅ |
| `WalkForwardRunner` | 滚动窗口 Walk-Forward 检验 | ✅ |

### 2.2 API 端点

| 端点 | 方法 | 状态 |
|---|---|---|
| `/api/strategies` | GET | ✅ 列出已注册策略 |
| `/api/strategies/{name}` | GET | ✅ 策略详情 |
| `/api/strategies/backtest` | POST | ✅ 新策略回测 |
| `/api/strategies/walk-forward` | POST | ✅ Walk-Forward 检验 |
| `/api/strategies/walk-forward/{task_id}` | GET | ✅ 异步任务查询 |
| `/api/strategies/portfolio/backtest` | POST | ✅ 组合级回测 |
| `/api/strategies/portfolio/optimize` | POST | ✅ 组合级参数优化 |
| `/api/summary` | GET | ✅ 已桥接到新 registry |
| `/api/detail/{ticker}` | GET | ✅ 已桥接到新 registry |
| `/api/factors` | GET | ✅ 因子列表 |

### 2.3 前端页面

| 页面 | 状态 |
|---|---|
| WalkForward.vue | ✅ 新建（D-6） |
| Dashboard.vue | ✅ 已去"前进30天"，添加导航卡片 |
| ConfigManager.vue | ✅ 动态策略/因子加载 |
| Detail.vue | ✅ 日志表 7→13 列，适配新仓位日志 |

## 3. 策略注册机制

当前唯一策略路径：`registry.create()` → `strategy.generate_targets()` → `engine.run_with_positions()` / `engine.run_portfolio()`

已注册策略：`target_weight_demo`

旧 `StrategyFactory.generate_signals()` 已删除，不可达。

## 4. 前端影响

- 策略列表由 `GET /api/strategies` 动态返回
- 因子列表由 `GET /api/factors` 动态返回
- 参数表单由后端 `parameter_schema` 驱动
- Walk-Forward 页面可从前端直接发起和查看结果
- 仓位日志兼容新旧字段（缺失字段显示 `--`）

## 5. 测试覆盖

| 测试文件 | 测试数 | 状态 |
|---|---|---|
| `test_strategy_backtest_registry_api.py` | 8 | ✅ |
| `test_portfolio_backtest.py` | 12 | ✅ |
| `test_walk_forward_api.py` | 14 | ✅ |
| `test_optimizer_api.py` | 9 | ✅ |
| `test_backtest_summary_diagnostics.py` | 4 | ✅ |
| `test_config_api.py` | 2 | ✅ |

**D-9 回归套件：49 passed, 0 failed。**

## 6. 已知差异

| 差异 | 解释 |
|---|---|
| 单标的 portfolio per-ticker 返回 0%而非 -100% | D-8B 修复：`final_shares==0` 时指标归零 |
| `target_weight_demo` 短区间返回 0% | 演示策略，RSI 基于权重而非买卖信号 |
| Summary 默认策略为 `target_weight_demo` | D-7 修复：config.yaml 已切换 |
| Portfolio 多标的组合可能只 resolve 部分标的 | 数据源限制，非代码 bug |

## 7. 验收命令

```bash
# 编译
python3 -m compileall -q backend

# 前端构建
cd frontend && npm run build

# 回归测试
.venv/bin/python -m pytest \
  tests/integration/test_strategy_backtest_registry_api.py \
  tests/integration/test_portfolio_backtest.py \
  tests/integration/test_walk_forward_api.py \
  tests/integration/test_optimizer_api.py \
  tests/integration/test_backtest_summary_diagnostics.py \
  -v
```