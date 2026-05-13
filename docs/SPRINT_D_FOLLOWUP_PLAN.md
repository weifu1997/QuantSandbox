# QuantSandbox Sprint D 完成报告

> 生成时间：2026-05-12
> **状态：✅ Sprint D 已全部完成（D-0 ~ D-9）**

---

## 1. 实际交付结果（D-6 ~ D-9）

### D-6：前端产品重构
| 交付项 | 文件 | 状态 |
|---|---|---|
| WalkForward.vue | `frontend/src/views/WalkForward.vue` | ✅ 新建 |
| Dashboard 去推演 | `frontend/src/views/Dashboard.vue` | ✅ 删除"前进30天"，添加导航卡片 |
| ConfigManager 动态化 | `frontend/src/views/ConfigManager.vue` | ✅ 硬编码 strategyMeta → 动态 API |
| Detail 新日志适配 | `frontend/src/views/Detail.vue` | ✅ 7→13 列 |
| API 方法收口 | `frontend/src/api/index.js` | ✅ 8 个新方法 |

### D-7：收口批
| 交付项 | 状态 |
|---|---|
| 回归验证 6/6 API 端点 | ✅ |
| 新旧对比报告 | ✅ |
| 旧引用清点 | ✅ |
| config.yaml 切换 | ✅ |

### D-8：旧体系删除 + Portfolio 修复
| 交付项 | 状态 |
|---|---|
| 旧策略文件删除（dual_ma/bollinger_bands/rsi_reversal） | ✅ |
| StrategyFactory 删除 | ✅ |
| engine.run() 删除 | ✅ |
| Portfolio 单标的 -100% 修复 | ✅ |
| 测试更新 | ✅ |

### D-9：测试固化 + 文档归档
| 交付项 | 状态 |
|---|---|
| 回归测试补强（+5 测试） | ✅ 49 passed |
| DEVELOPMENT_PLAN.md 更新 | ✅ |
| 迁移归档文档 | ✅ |
| 问题清单归档 | ✅ |

---

## 1. 当前完成度评估

### 1.1 总体判断

当前 Sprint D 已完成后端主体骨架：因子系统、新策略基类、目标仓位契约、仓位管理器、新策略回测 API、Walk-Forward API 骨架均已存在。结合 Hermes 反馈与当前代码复核，D-3 已推进到第八批：per-window 评估摘要、顶层 `window_summary`、窗口级 `backtest_results` 均已接入，`evaluated` 状态测试断言已同步完成，并补齐了 `backtest_results` 边界断言。

按当前代码复核，D-4 优化器框架、D-5 第一批真实撮合引擎、D-5 第二批 Walk-Forward + Optimizer 真实引擎集成与多标的组合级 `run_portfolio()` 均已完成；D-5 第三批的大部分后端能力也已落地，包括组合级指标增强和 `POST /api/strategies/portfolio/backtest`。当前剩余核心缺口转为：Walk-Forward API 暴露 portfolio_mode、组合级 optimize endpoint、真正后台异步任务，以及前端产品接入。

**综合完成度：约 82%-85%。**

若只统计后端策略/回测主链路，约 **92%-95%**；若按 Sprint D 完整交付口径，包括前端产品重构和旧代码清理，则仍未完成。

### 1.2 分阶段完成度

| 阶段 | 当前状态 | 完成度 | 说明 |
|---|---:|---:|---|
| D-0 配置安全 | 基本完成 | 90% | `TICKFLOW_API_KEY` / `TUSHARE_TOKEN` 环境变量 fallback 已有，`.gitignore` 已忽略 `config.yaml`，`config.example.yaml` 已存在 |
| D-1 因子层 | 基本完成 | 80% | `backend/core/factors/`、技术因子、基本面因子、注册表、`GET /api/factors` 已有；基本面因子暂未真正接 MX data fallback |
| D-2 策略层 + 仓位管理 + 新回测 API | 骨架完成 | 60% | `Strategy`、`PositionTarget`、`PositionManager`、`run_with_positions()`、`POST /api/strategies/backtest` 已有；但权益/现金/持仓未真实滚动 |
| D-3 样本外检验 | 第八批已完成，框架层已收口 | 65% | `walk_forward.py`、`POST /api/strategies/walk-forward`、per-window 摘要、顶层 `window_summary`、`backtest_results`、`evaluated` 状态断言、skipped/zero-window 边界断言均已完成 |
| D-4 优化器框架 | 已完成 | 80% | `GridOptimizer`、参数网格展开、train 段扫描、best_params 选择、test 段评估、API `optimize/param_grid/objective` 已接入，相关测试通过；真正后台异步仍待增强 |
| D-5 真实撮合 / 组合回测 | 基本完成，第三批部分完成 | 90% | `run_with_positions()` 单标的真实撮合、Walk-Forward + Optimizer 真实引擎集成、多标的组合级 `run_portfolio()`、组合级指标增强、`POST /api/strategies/portfolio/backtest` 均已完成；portfolio_mode API 暴露、portfolio optimize 与前端接入待补 |
| D-4 前端基础收口 | 部分完成 | 40% | axios response interceptor 已有；`MxMoniTab.vue` 仍使用 `localStorage` |
| D-5 前端产品重构 | 未开始 | 0-10% | `WalkForward.vue` 不存在；Dashboard / ConfigManager / Detail 仍以旧策略体验为主 |
| D-6 清理旧代码 | 未开始，且暂不应开始 | 0% | 旧策略仍被现有 API 引用，当前保留是正确状态 |

### 1.3 已验证事项

本次评估中已完成以下验证：

```bash
python3 -m compileall -q backend
```

结果：通过。

```bash
cd frontend && npm run build
```

结果：通过。

```bash
.venv/bin/python -m pytest -q tests/integration/test_strategy_backtest_registry_api.py tests/integration/test_walk_forward_api.py
```

初次评估结果：`15 passed`。

Hermes 后续反馈：D-3 第六批已完成，`window_summary` 字段断言已补齐，曾达到 Walk-Forward 相关 7 个测试全部通过。随后 D-3 第七批完成，`evaluated` 状态与测试断言已对齐。D-3 第八批完成后，7 个 Walk-Forward 测试均包含必要的 `backtest_results` / `window_summary` 边界断言并全部通过。

本次复核当前工作区时，单跑：

```bash
.venv/bin/python -m pytest -q tests/integration/test_walk_forward_api.py
```

第八批完成后复核当前工作区：`7 passed, 28 warnings`。`backtest_results` 的 evaluated / skipped 状态、零窗口 `window_summary` 等边界断言已补齐。

注意：`.venv-tests` 环境缺少 `pandas`，无法运行上述测试；主 `.venv` 可以正常运行。

---

## 2. 当前关键风险与缺口

### 2.1 D-2 核心风险：`run_with_positions()` 仍是骨架

当前新回测路径虽然已经接入 `PositionManager`，但每根 bar 的资金和权益仍使用初始值：

```python
available_cash=self.initial_cash
total_equity=self.initial_cash
```

这会导致：

- 权益曲线不能真实反映行情波动和交易结果
- 调仓不会影响后续现金
- 当前仓位不会随价格变化自然漂移
- 交易日志更接近「目标指令记录」，不是完整撮合日志
- 后续 Walk-Forward 的训练/测试指标会失真

这是 Sprint D 后续最优先要修复的问题。

### 2.2 D-1 基本面因子数据源仍偏静态

当前基本面因子主要从 DataFrame 读取字段，例如：

- `pe_ttm_num`
- `pe_ttm`
- `pe`
- `pb_num`
- `dividend_yield_num`

尚未真正实现计划中的：

1. 优先从 MX data 获取；
2. MX data 不稳定或字段不一致时 fallback 到 watchlist 结构化字段；
3. 再 fallback 到 DataCenter / DataFrame 已有数据。

### 2.3 D-3 Walk-Forward 已完成八批，但还不是完整样本外检验

结合 Hermes 反馈和当前代码，D-3 已完成以下内容：

| 批次 | 内容 | 状态 |
|---|---|---|
| D-3 第一批 | 最小 Walk-Forward 骨架：`walk_forward.py` + API | 已完成 |
| D-3 第二批 | Walk-Forward 基础 API / Runner 测试 | 已完成 |
| D-3 第三批 | 最小评估摘要结构：per-window fields | 已完成 |
| D-3 第四批 | 评估摘要字段测试补齐 | 已完成 |
| D-3 第五批 | 顶层 `window_summary` 汇总 | 已完成 |
| D-3 第六批 | `window_summary` 测试断言 | 已完成 |
| D-3 第七批 | `evaluated` 状态与测试断言对齐，Walk-Forward 7 个测试全绿 | 已完成 |
| D-3 第八批 | `backtest_results` 断言补齐，覆盖 evaluated / skipped / zero-window 等边界 | 已完成 |

当前代码还显示 `WalkForwardRunner.evaluate_window()` 已可在 test 段调用 `BacktestEngine.run_with_positions()`，并输出 per-ticker `backtest_results`。这比原先评估的“只做窗口切分”更进一步。

但 D-3 仍未达到原计划中的完整样本外检验，因为尚未实现：

- `backend/core/optimizer.py`；
- 参数网格搜索；
- 训练窗口择优；
- 基于 best_params 的测试窗口回测；
- 夏普比率、胜率稳定性、训练-测试收益落差；
- `GET /api/strategies/walk-forward/{task_id}` 查询异步任务结果。

第七批已完成测试断言同步：完成窗口标记为 `evaluated`，相关测试已按该语义更新。第八批进一步补齐 `backtest_results` 和零窗口 `window_summary` 断言，D-3 框架层测试护栏已基本收口。

### 2.4 D-4 前端安全收口未完成

已完成：

- axios response interceptor 初步存在。

未完成：

- interceptor 尚未统一映射 HTTP 状态码到 `ElMessage`；
- `MxMoniTab.vue` 仍使用 `localStorage` 缓存模拟组合信息。

### 2.5 D-5 / D-6 不能提前推进

当前前端仍存在旧策略产品形态：

- Dashboard 仍有「前进 30 天」按钮和推演逻辑；
- ConfigManager 仍有硬编码 `strategyMeta`；
- Detail 尚未适配新仓位调整日志格式；
- 旧 `StrategyFactory` 仍被旧回测路径引用。

因此 D-6 删除旧代码目前不具备条件。若提前删除，会破坏现有功能。

---

## 3. 后续开发路线图

推荐将 Sprint D 后续拆成 6 个 Phase 推进，顺序如下：

1. **D-2.5：真实仓位回测引擎补齐**
2. **D-1.5：基本面因子数据源 fallback 补齐**
3. **D-3.1：真实 Optimizer + 训练窗口择优**
4. **D-3.2：Walk-Forward 异步任务化**
5. **D-4：前端基础安全收口**
6. **D-5 / D-6：前端产品重构与旧代码清理**

最关键原则：**先把 D-2 的执行语义做实，再推进 D-3 optimizer 和 D-5。** D-3 当前 evaluated 状态和测试断言已经对齐，但 Walk-Forward 仍依赖 `run_with_positions()` 的真实权益曲线质量。

---

## 4. Phase 1：D-2.5 真实仓位回测引擎补齐

### 4.1 目标

将 `BacktestEngine.run_with_positions()` 从「目标仓位骨架」升级为「可真实评估的仓位回测路径」。

### 4.2 具体任务

#### 任务 1：重构 `PositionTarget` 时间语义

当前 `PositionTarget` 缺少明确日期字段，建议新增：

- `signal_date`：策略生成目标仓位的日期；
- `effective_date`：目标仓位最早可执行日期；
- `metadata` 中保留 factor values / reason。

可选方案：

```python
@dataclass(slots=True)
class PositionTarget:
    symbol: str
    target_weight: float
    confidence: float = 0.0
    signal_date: str | None = None
    effective_date: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

#### 任务 2：让策略输出逐日 target 序列

`TargetWeightDemoStrategy.generate_targets()` 应从「只输出一个最新 target」改为「按每根 bar 输出 target 序列」。

要求：

- 每日收盘后基于截至当日数据计算因子；
- 生成当日 `signal_date` 的目标仓位；
- 次交易日开盘执行；
- 无有效因子值时输出 0 仓位或沿用上一目标，需要明确规则。

建议第一版规则：

- RSI 不可用时 target_weight = 0；
- RSI 低于 oversold floor 时仓位接近 `max_target_weight`；
- RSI 高于 overbought ceiling 时仓位接近 0；
- 中间区间线性映射。

#### 任务 3：重写 `run_with_positions()` 状态机

每日循环维护：

- `cash`
- `shares`
- `market_value`
- `total_equity`
- `current_weight`
- `pending_target`
- `entry_price`
- `trade_returns`

每根 bar 流程：

1. 读取当日 open / close / volume / limit_ratio；
2. 用上一交易日产生的 target 在当日开盘执行；
3. 检查停牌、涨停、跌停；
4. 调用 `PositionManager.allocate()` 生成订单；
5. 按开盘价 + 滑点撮合；
6. 计算佣金、印花税；
7. 更新 cash / shares；
8. 用收盘价 mark-to-market；
9. 记录 equity curve；
10. 当日收盘后读取当日 target，作为下一交易日 pending target。

#### 任务 4：扩展 `Order` 结构化字段

建议将当前藏在 metadata 中的关键字段提升出来：

- `planned_shares`
- `executed_shares`
- `planned_trade_value`
- `executed_trade_value`
- `fill_price`
- `commission_fee`
- `tax_fee`
- `slippage_fee`
- `skipped_reason`

这样前端 Detail 和日志展示会更稳定。

#### 任务 5：补充回测指标

`run_with_positions()` 返回 metadata 至少应包含：

- `initial_cash`
- `final_equity`
- `total_return`
- `annualized_return`
- `max_drawdown`
- `sharpe_ratio`
- `trade_count`
- `win_rate`
- `profit_loss_ratio`
- `position_mode = target_weight`

### 4.3 验收标准

- `run_with_positions()` 的 `total_equity` 随价格和交易变化；
- 资金不足时高 confidence 订单优先成交；
- 买入遵守 100 股整手；
- 单票上限 30%、总仓位上限 95% 生效；
- 停牌、涨停买入失败、跌停卖出失败有日志；
- 旧 `run()` 不受影响；
- `POST /api/strategies/backtest` 返回真实权益曲线；
- 新增测试覆盖主要撮合路径。

### 4.4 建议测试清单

新增或扩展测试：

- `tests/unit/test_position_manager.py`
- `tests/unit/test_engine_run_with_positions.py`
- `tests/integration/test_strategy_backtest_registry_api.py`

测试场景：

1. 单票买入成功；
2. 单票减仓成功；
3. 清仓成功；
4. 资金不足时按 confidence 排序；
5. 目标仓位低于一手金额时跳过；
6. 涨停时买入失败；
7. 跌停时卖出失败；
8. 停牌时交易失败；
9. total_equity 随 close 变化；
10. 多日 T+1 执行语义正确。

---

## 5. Phase 2：D-1.5 基本面因子数据源 fallback

### 5.1 目标

让基本面因子从「读取已有 DataFrame 字段」升级为「具备稳定 fallback 的业务因子」。

### 5.2 具体任务

#### 任务 1：引入 FactorContext

建议新增：

```python
@dataclass(slots=True)
class FactorContext:
    symbol: str | None = None
    watchlist_metrics: dict[str, Any] = field(default_factory=dict)
    mx_snapshot: dict[str, Any] = field(default_factory=dict)
    data_center_snapshot: dict[str, Any] = field(default_factory=dict)
```

并将因子接口扩展为：

```python
compute(df: pd.DataFrame, context: FactorContext | None = None) -> pd.Series
```

为保持兼容，可让 `context` 默认为 None。

#### 任务 2：实现基本面因子 fallback 顺序

建议顺序：

1. `context.mx_snapshot`
2. `context.watchlist_metrics`
3. DataFrame 的 `*_num` 字段
4. DataFrame 的兼容文本字段
5. 返回空 Series

#### 任务 3：避免因子内部直接调外部 API

不建议让 `Factor.compute()` 自己调用 MX API。更好的边界是：

- API / service 层负责拉数据；
- 组装 `FactorContext`；
- 因子只负责稳定取值和计算。

这样测试、缓存、超时控制都会更清晰。

### 5.3 验收标准

- MX 字段缺失时不抛 500；
- MX 调用失败时能 fallback；
- watchlist 有 `*_num` 时可正常计算；
- `/api/factors` 可标明因子数据源要求；
- 有测试覆盖 MX 缺失、watchlist fallback、DataFrame fallback。

---

## 6. Phase 3：D-3.1 Walk-Forward Optimizer

### 6.1 目标

当前已完成的 Walk-Forward 第八批已经固化：`window_summary`、per-window 摘要、`backtest_results`、`evaluated` 状态、skipped/zero-window 边界断言均与测试保持一致。下一步从“窗口级测试段回测摘要”升级为“真实训练-测试检验”。

### 6.2 当前已通过验证

```bash
.venv/bin/python -m pytest -q tests/integration/test_walk_forward_api.py
```

结果：`7 passed, 28 warnings`。

当前 7 个测试均已覆盖必要的 Walk-Forward 基础行为，其中包括：

- minimal windows 的 `backtest_results` evaluated 断言；
- single ticker source；
- multi ticker 去重；
- zero windows 的 `window_summary` 断言；
- skipped ticker 的 `backtest_results["BBB"].status == "skipped"` 断言；
- all tickers failed 返回 404；
- unknown strategy 返回 400。

完成窗口当前语义：

```python
window.status = "evaluated"
```

该语义已被测试接受。

### 6.3 新增文件

- `backend/core/optimizer.py`

### 6.4 Optimizer 职责

`Optimizer` 第一版只需做简单参数网格搜索：

```python
class GridSearchOptimizer:
    def optimize(strategy_name, param_grid, train_df, objective):
        ...
```

支持 objective：

- `sharpe_ratio`
- `total_return`
- `max_drawdown_adjusted_return`（可后置）

### 6.5 Walk-Forward 执行流程

每个窗口执行：

1. 切训练集；
2. 展开参数网格；
3. 训练期逐组参数回测；
4. 根据 objective 选择 best_params；
5. 在测试期用 best_params 回测；
6. 保存窗口结果；
7. 汇总全部测试窗口。

### 6.6 API 输出建议

`POST /api/strategies/walk-forward` 同步版可先返回：

```json
{
  "status": "success",
  "strategy_name": "target_weight_demo",
  "objective": "sharpe_ratio",
  "window_count": 4,
  "windows": [
    {
      "window_index": 1,
      "train_start": "2022-01-01",
      "train_end": "2023-12-31",
      "test_start": "2024-01-01",
      "test_end": "2024-06-30",
      "best_params": {},
      "train_metrics": {},
      "test_metrics": {},
      "degradation": {}
    }
  ],
  "summary": {
    "stitched_total_return": 0.0,
    "average_test_sharpe": 0.0,
    "win_rate_stability": 0.0,
    "train_test_return_gap": 0.0
  }
}
```

### 6.7 验收标准

- 当前 `test_walk_forward_api.py` 的 7 个测试保持全部通过；
- 单 ticker 可跑完整 Walk-Forward；
- 多 ticker 可部分失败但整体返回成功；
- 每个窗口都有真实 train/test metrics；
- best_params 来自真实训练窗口；
- summary 汇总所有测试窗口；
- 有测试覆盖参数网格、窗口不足、部分 ticker 数据不足。

---

## 7. Phase 4：D-3.2 Walk-Forward 异步任务化

### 7.1 目标

实现原计划中的：

- `POST /api/strategies/walk-forward`
- `GET /api/strategies/walk-forward/{task_id}`

避免长耗时请求阻塞前端。

### 7.2 实现建议

第一版可用内存任务注册表，不必立刻引入 Celery / Redis。

建议新增：

- `backend/services/task_registry.py`
- 或在 backtest service 内维护轻量任务状态

任务状态：

- `pending`
- `running`
- `success`
- `failed`

任务字段：

- `task_id`
- `created_at`
- `updated_at`
- `progress`
- `message`
- `result`
- `error`

### 7.3 验收标准

- POST 返回 task_id；
- GET 可查询进度；
- 任务失败可返回明确错误；
- 进程内多任务不互相覆盖；
- 有最小集成测试覆盖 success / failed。

---

## 8. Phase 5：D-4 前端基础安全收口

### 8.1 目标

完成 D-4 原定的安全修复和基础设施，不做大规模产品重构。

### 8.2 具体任务

#### 任务 1：axios interceptor 统一错误提示

当前 interceptor 已标准化错误字段，但未统一 `ElMessage`。

建议：

- HTTP 400：显示业务错误；
- HTTP 401/403：显示授权/权限错误；
- HTTP 404：显示资源不存在；
- HTTP 500：显示服务端错误；
- timeout/canceled 单独处理；
- 允许请求传入 `{ silent: true }` 抑制弹窗。

#### 任务 2：移除 `MxMoniTab.vue` 中的 localStorage

当前仍有：

- `localStorage.getItem`
- `localStorage.setItem`
- `localStorage.removeItem`

可替换为：

- `sessionStorage`，改动小；或
- 组件级内存缓存，更安全但刷新丢失。

建议采用 `sessionStorage`，符合原计划且成本低。

### 8.3 验收标准

- `grep -R "localStorage" frontend/src/views/mx/MxMoniTab.vue` 无结果；
- `npm run build` 通过；
- 错误提示不重复弹出；
- 现有页面渲染不受影响。

---

## 9. Phase 6：D-5 前端产品重构

### 9.1 前置条件

必须先完成：

- D-5 第一批真实单标的撮合引擎稳定；
- D-4 优化器框架稳定；
- 新 API 返回结构稳定。

建议在前端大规模接入前，优先补齐 D-5 第二批：Walk-Forward + Optimizer 在真实撮合引擎上的端到端确认、多标的组合级回测和收益归因。

### 9.2 新增 WalkForward 页面

新增文件：

- `frontend/src/views/WalkForward.vue`

页面能力：

- 策略选择；
- 股票池选择；
- train/test/step window 输入；
- 参数网格配置；
- 任务启动；
- 任务进度查询；
- 窗口结果表；
- train/test 指标对比；
- 稳定性指标展示。

### 9.3 Dashboard 改为多策略回测对比

删除：

- 「前进 30 天」按钮；
- 推演动画逻辑。

新增：

- 多策略回测结果表；
- 收益 / 回撤 / 夏普 / 胜率排序；
- 单策略详情入口；
- 支持新 `POST /api/strategies/backtest`。

### 9.4 ConfigManager 动态因子配置

删除硬编码：

- `strategyMeta`

改为从后端加载：

- `GET /api/factors`
- `GET /api/strategies`

新增：

- 动态参数表单；
- 因子选择面板；
- 仓位约束输入；
- 参数 schema 校验。

### 9.5 Detail 适配新仓位日志

展示字段：

- `target_weight`
- `current_weight`
- `delta_weight`
- `planned_shares`
- `executed_shares`
- `fill_price`
- `commission_fee`
- `tax_fee`
- `skipped_reason`

### 9.6 验收标准

- `WalkForward.vue` 页面可访问；
- Dashboard 不再出现「前进 30 天」；
- ConfigManager 不再出现硬编码 `strategyMeta`；
- Detail 可展示新仓位日志；
- `npm run build` 通过；
- 前端可完整跑通一次新策略回测。

---

## 10. Phase 7：D-6 清理旧代码

### 10.1 前置条件

以下条件缺一不可：

1. 新策略回测 API 稳定；
2. Walk-Forward API 稳定；
3. 前端完全切换到新策略体系；
4. 当前真实股票池完成一轮完整新旧对比验证；
5. 新旧结果差异报告已产出并确认一致，或差异可解释；
6. 回归测试覆盖新路径；
7. 代码中无任何 import 引用旧 `backend/core/strategies/` 下的旧策略类。

### 10.2 清理内容

满足条件后再删除：

- `backend/core/strategies/dual_ma.py`
- `backend/core/strategies/bollinger_bands.py`
- `backend/core/strategies/rsi_reversal.py`
- `backend/core/strategy.py` 中的 `StrategyFactory`
- `backend/core/engine.py` 中旧 `run()` 方法

### 10.3 验收标准

- `grep -R "StrategyFactory\|dual_ma\|bollinger_bands\|rsi_reversal" backend frontend/src tests` 无旧业务引用；
- 后端测试通过；
- 前端构建通过；
- 新旧差异报告归档到 `docs/`。

---

## 11. 建议里程碑

### Milestone 1：真实仓位回测可用

范围：Phase 1

预计产出：

- `run_with_positions()` 真实滚动；
- 新交易日志结构；
- 新指标；
- 单元测试 + 集成测试。

完成后才能认为 D-2 真正完成。

### Milestone 2：因子数据源稳定

范围：Phase 2

预计产出：

- `FactorContext`；
- 基本面因子 fallback；
- MX/watchlist/DataFrame 多级容错。

完成后 D-1 才能算生产可用。

### Milestone 3：Walk-Forward 真实可用

范围：Phase 3 + Phase 4

当前基础：D-3 第一至第八批已完成，包含窗口骨架、per-window 摘要、顶层 `window_summary`、`backtest_results`，以及 `evaluated` / skipped / zero-window 相关测试断言。

预计补齐产出：
- `optimizer.py`；
- 真实 train/test metrics；
- task_id 异步查询；
- 前端可消费的稳定 API。

完成后 D-3 才算完整完成。

### Milestone 4：前端切换新策略体系

范围：Phase 5 + Phase 6

预计产出：

- WalkForward 页面；
- Dashboard 策略对比；
- ConfigManager 动态因子配置；
- Detail 新交易日志展示。

完成后进入 D-6 清理准备。

### Milestone 5：旧体系下线

范围：Phase 7

预计产出：

- 旧策略代码删除；
- 差异报告；
- 回归测试；
- 文档更新。

---

## 12. 优先级排序

| 优先级 | 任务 | 理由 |
|---:|---|---|
| P0 | Walk-Forward portfolio_mode API 暴露 | `WalkForwardRunner` 已支持 portfolio_mode，但 `StrategyWalkForwardRequest` 尚未暴露该字段 |
| P0 | 组合级指标测试断言补齐 | 指标已实现，应补 `turnover_rate`、集中度、单标的最大回撤等断言防回归 |
| P1 | 组合级 optimize endpoint | `POST /api/strategies/portfolio/backtest` 已有，后续可补 portfolio optimize |
| P1 | 收益归因 | 为前端和策略分析提供按标的/按窗口/按阶段的收益拆解 |
| P1 | 真正后台异步 task | 当前 async_mode 是同步算完后存 task，尚不能解决长任务阻塞 |
| P1 | 基本面因子 fallback | 补齐多因子框架的数据可靠性 |
| P1 | Walk-Forward 异步任务化 | 避免长请求阻塞前端 |
| P2 | D-4 前端基础收口 | 小改动，高收益，减少安全和错误处理问题 |
| P2 | D-5 前端产品重构 | 依赖后端 API 稳定，不能过早做 |
| P3 | D-6 旧代码删除 | 必须最后做 |

---

## 13. 下一个建议开发切片

建议下一次直接执行以下切片：

### 切片名称

`D-2.5-real-position-backtest`

### 范围

只改：

- `backend/core/strategy.py`
- `backend/core/strategies/target_weight_demo.py`
- `backend/core/position_manager.py`
- `backend/core/engine.py`
- `tests/unit/` 或 `tests/integration/` 相关测试

暂不改：

- Walk-Forward optimizer；
- 前端页面；
- 旧策略删除。

### 完成定义

- 新策略回测权益曲线真实变化；
- T+1 调仓语义明确；
- 现金、持仓、费用、税费、滑点均参与计算；
- 测试覆盖关键撮合路径；
- `python3 -m compileall -q backend` 通过；
- `.venv/bin/python -m pytest` 对相关测试通过。

---


## 14. D-5 第一批复核结果

D-5 第一批：真实 `run_with_positions()` 撮合引擎已完成。

已确认能力：

- 每根 bar 维护真实账户状态：`cash`、`shares`、`market_value`、`total_equity`、`current_weight`
- 按 `target_weight` 调仓：目标市值 vs 当前市值
- 买入按资金约束缩量
- 卖出不超过当前持仓
- 佣金、印花税、滑点
- 停牌不交易
- 涨停不买
- 跌停不卖
- 100 股整手约束
- 旧 `run()` 保持不动
- `position_mode` 已从 `target_weight_skeleton` 升级为 `target_weight`

验证命令：

```bash
.venv/bin/python -m pytest -q tests/integration/test_real_matching_engine.py tests/integration/test_optimizer_api.py tests/integration/test_walk_forward_api.py tests/integration/test_strategy_backtest_registry_api.py
```

当前结果：`37 passed, 72 warnings`。

D-5 第二批已完成：Walk-Forward + Optimizer 已确认使用真实撮合引擎，多标的组合级 `run_portfolio()` 已实现并有 9 个组合测试覆盖。当前进一步确认到 D-5 第三批的大部分后端能力也已落地：组合级增强指标和 `POST /api/strategies/portfolio/backtest` 已存在。

当前复核命令：

```bash
.venv/bin/python -m pytest -q tests/integration/test_walk_forward_api.py tests/integration/test_real_matching_engine.py tests/integration/test_optimizer_api.py tests/integration/test_portfolio_backtest.py tests/integration/test_strategy_backtest_registry_api.py tests/integration/test_sprint_a_fixes.py tests/integration/test_backtest_summary_diagnostics.py tests/integration/test_config_api.py
```

当前结果：`70 passed, 108 warnings`。

下一步建议进入 **D-5 第三批收尾 / D-6 前置**，优先顺序：

1. 暴露 Walk-Forward `portfolio_mode` 到 API，并补测试：每个 Walk-Forward window 使用组合级 `run_portfolio()`；
2. 补组合级指标断言：`turnover_rate`、`max_single_ticker_drawdown`、`concentration_ratio`、`cash_utilization`、`gross_exposure`；
3. 视需求新增 `POST /api/strategies/portfolio/optimize`；
4. 将当前同步算完再存 task 的 async_mode 升级为真正后台任务；
5. 前端 WalkForward / Optimize / Portfolio 接入。

## 14. 管理建议

1. Sprint D 后续不要再继续堆 API 壳，优先补真实执行语义。
2. 每个 Phase 单独 commit，避免后端引擎、Walk-Forward、前端重构混在一起。
3. D-6 删除旧代码前必须产出新旧差异报告。
4. `config.yaml`、SQLite 数据库、venv、运行态缓存不要进入功能提交。
5. 对外展示前，应明确标注当前新策略结果是「骨架」还是「真实撮合」。
