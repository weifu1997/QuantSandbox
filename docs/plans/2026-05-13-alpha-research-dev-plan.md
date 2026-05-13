# Alpha Research v1 开发计划

> 目标：把 QuantSandbox 从“策略回测 demo”收敛为“因子研究 + alpha 验证 + 组合策略生成”的实验室。  
> 执行者建议：Hermes 负责代码实现；OpenClaw/Hermes 使用本计划做 PR 拆分和验收。

---

## 0. 核心判断

当前项目已有：

- 行情数据获取与缓存
- 因子注册体系
- 回测引擎
- 单票/组合回测
- walk-forward
- optimizer

但缺少真正的 alpha 研究链路。下一阶段不要继续直接堆策略公式，而是先建立因子研究能力：

```text
数据集构建 → 因子计算 → 未来收益标签 → IC/RankIC → 分组回测 → TopN 组合 → 策略化
```

---

## 1. 总体目标

Alpha Research v1 需要回答四个问题：

1. 某个因子是否能预测未来收益？
2. 因子在不同持有周期上是否稳定？
3. 因子分组收益是否单调？
4. 用因子选 TopN 股票，是否跑赢股票池等权和基准？

v1 不追求复杂机器学习，先把可解释、可复现的研究管线打通。

---

## 2. 建议目录结构

新增：

```text
backend/research/
  __init__.py
  dataset_builder.py
  factor_library.py
  factor_analysis.py
  group_backtest.py
  topn_backtest.py
  benchmark.py
  report_builder.py
  schemas.py
```

新增 API：

```text
backend/api/research_endpoints.py
```

新增前端页面：

```text
frontend/src/views/AlphaResearch.vue
```

新增测试：

```text
tests/unit/test_alpha_dataset_builder.py
tests/unit/test_factor_analysis.py
tests/unit/test_group_backtest.py
tests/unit/test_topn_backtest.py
tests/integration/test_research_api.py
```

---

## 3. PR 拆分

建议分 6 个 PR，避免一次改太大。

---

# PR1：Alpha Dataset 数据集构建

## 目标

构建统一研究数据集，把股票池行情、因子值、未来收益标签对齐到一个 DataFrame。

## 新增文件

```text
backend/research/dataset_builder.py
backend/research/schemas.py
```

## 核心输入

```python
AlphaDatasetRequest:
    tickers: list[str]
    start_date: str
    end_date: str
    factors: list[str]
    horizons: list[int] = [5, 20, 60]
    price_adjust: str = "qfq" | "none"
```

## 核心输出字段

每一行表示：某只股票在某个交易日的研究样本。

```text
date
ticker
open
high
low
close
volume
factor:{factor_name}
future_return_5d
future_return_20d
future_return_60d
is_valid_sample
missing_reason
```

## 未来收益定义

```text
future_return_Nd = close(t+N) / close(t) - 1
```

注意：

- 最后 N 天没有未来收益，要标记为 NaN，不得 forward fill。
- 停牌/无成交量日期默认剔除或标记 invalid。
- 因子值使用 t 日可见数据，不允许使用 t+1 之后信息。

## 核心函数

```python
def build_alpha_dataset(
    tickers: list[str],
    start_date: str,
    end_date: str,
    factors: list[str],
    horizons: list[int],
) -> pd.DataFrame:
    ...
```

```python
def add_future_returns(
    df: pd.DataFrame,
    horizons: list[int],
) -> pd.DataFrame:
    ...
```

```python
def align_factor_values(
    df: pd.DataFrame,
    factor_names: list[str],
) -> pd.DataFrame:
    ...
```

## 验收标准

1. 3 只股票 × 30 个交易日能生成 dataset。
2. 每个 horizon 都有对应 future_return 字段。
3. 最后 N 天 future_return_Nd 为 NaN。
4. 不允许未来函数。
5. 单元测试通过：

```bash
.venv/bin/python -m pytest tests/unit/test_alpha_dataset_builder.py -q
```

---

# PR2：因子库标准化 Factor Library

## 目标

为 alpha 研究新增一批标准因子，和现有策略因子区分开。

现有 `backend/core/factors/` 偏策略运行；研究层需要更丰富的横截面因子。

## 新增文件

```text
backend/research/factor_library.py
```

## v1 因子清单

### 动量类

```text
momentum_20d = close / close.shift(20) - 1
momentum_60d = close / close.shift(60) - 1
momentum_120d = close / close.shift(120) - 1
momentum_20d_skip5d = close.shift(5) / close.shift(25) - 1
```

### 反转类

```text
reversal_5d = -(close / close.shift(5) - 1)
rsi_14
bollinger_position_20
```

### 趋势类

```text
ma5_ma20 = ma5 / ma20 - 1
ma20_ma60 = ma20 / ma60 - 1
macd_hist
```

### 波动类

```text
volatility_20d = daily_return.rolling(20).std()
atr_pct_14 = atr_14 / close
max_drawdown_20d
```

### 量价类

```text
volume_ratio_20d = volume / volume.rolling(20).mean()
turnover_proxy_20d = amount_or_volume rolling mean proxy
```

### 估值类

```text
pe_ttm
pb
dividend_yield
```

估值因子在数据源缺失时：

- 不报错
- 输出 NaN
- 后续分析阶段按缺失处理

## 统一因子描述结构

```python
@dataclass
class ResearchFactor:
    name: str
    category: str
    description: str
    higher_is_better: bool
    required_columns: list[str]
    min_periods: int
    compute: Callable[[pd.DataFrame], pd.Series]
```

## 缺失值原则

- 因子层只计算，不随便填中性值。
- 分析层可以选择：drop / neutral_fill。
- 报告必须展示缺失率。

## 验收标准

1. 每个因子能独立计算。
2. 输出长度等于输入 df 长度。
3. warmup 期 NaN 合理。
4. 不允许 inf。
5. 单元测试通过：

```bash
.venv/bin/python -m pytest tests/unit/test_factor_library.py -q
```

---

# PR3：IC / RankIC 因子分析

## 目标

给定 dataset 和因子名，计算因子预测未来收益的能力。

## 新增文件

```text
backend/research/factor_analysis.py
```

## 核心指标

对每个因子、每个 horizon：

```text
ic_mean
ic_std
ic_ir = ic_mean / ic_std
rank_ic_mean
rank_ic_std
rank_ic_ir
positive_ic_ratio
sample_count
missing_ratio
monthly_ic_series
```

## IC 计算方式

按日期横截面计算：

```python
for date in dates:
    x = factor_value(date, all_tickers)
    y = future_return_horizon(date, all_tickers)
    ic = pearson_corr(x, y)
    rank_ic = spearman_corr(rank(x), rank(y))
```

然后对每日 IC 序列做统计。

## 重要细节

- 每个 date 至少需要 N 个有效样本，默认 `min_cross_section=10`。
- 缺失率高的因子要在报告中标红。
- IC 方向要考虑 `higher_is_better`。
- 对估值类因子，PE/PB 越低越好，所以可以：
  - 要么 factor 值取负
  - 要么 `higher_is_better=False` 时自动翻转方向

## 核心函数

```python
def analyze_factor_ic(
    dataset: pd.DataFrame,
    factor_name: str,
    horizons: list[int],
    min_cross_section: int = 10,
) -> FactorICReport:
    ...
```

## 输出 schema

```python
FactorICReport:
    factor_name: str
    horizons: dict[int, HorizonICStats]
    warnings: list[str]
```

## 验收标准

1. 人工构造“完美正相关”数据，IC 接近 1。
2. 人工构造“完美负相关”数据，IC 接近 -1。
3. 随机数据 IC 接近 0。
4. 缺失数据不会崩。
5. 单元测试通过：

```bash
.venv/bin/python -m pytest tests/unit/test_factor_analysis.py -q
```

---

# PR4：分组回测 Group Backtest

## 目标

判断因子排序是否能带来单调收益。

## 新增文件

```text
backend/research/group_backtest.py
```

## 核心逻辑

每天按因子值把股票分成 N 组：

```text
Q1: 因子最低
Q2
Q3
Q4
Q5: 因子最高
```

计算每组未来收益，形成净值曲线。

## 指标

```text
group_return_Q1 ... group_return_Q5
long_short_return = Q5 - Q1
monotonicity_score
annual_return_by_group
max_drawdown_by_group
win_rate_by_group
turnover_by_group
```

## 组合规则

v1 简化：

- 每组等权
- 每 `rebalance_frequency` 调仓一次
- 默认日频，也支持周频/月频
- 默认不考虑行业中性

## 核心函数

```python
def run_group_backtest(
    dataset: pd.DataFrame,
    factor_name: str,
    horizon: int = 20,
    groups: int = 5,
    rebalance_frequency: str = "D",
) -> GroupBacktestReport:
    ...
```

## 单调性评分

可以先用简单版本：

```text
monotonicity_score = count(Q[i+1] > Q[i]) / (groups - 1)
```

如果 Q5 > Q4 > Q3 > Q2 > Q1，则为 1.0。

## 验收标准

1. 人工构造单调因子，Q5 > Q1。
2. 人工构造反向因子，Q1 > Q5。
3. 长短组合收益可计算。
4. 组内样本不足时给 warning。
5. 单元测试通过：

```bash
.venv/bin/python -m pytest tests/unit/test_group_backtest.py -q
```

---

# PR5：TopN 组合回测

## 目标

把有效因子转成最简单的组合策略，回答“用这个因子买 TopN 是否赚钱”。

## 新增文件

```text
backend/research/topn_backtest.py
backend/research/benchmark.py
```

## 核心逻辑

每个调仓日：

1. 对股票池按因子/score 排序
2. 买入 TopN
3. 等权或 score 加权
4. 下个调仓日换仓

## 参数

```python
TopNBacktestRequest:
    tickers: list[str]
    factor_name: str
    start_date: str
    end_date: str
    top_n: int = 10
    rebalance_frequency: str = "W"  # D/W/M
    weighting: str = "equal" | "score"
    transaction_cost_bps: float = 10
    benchmark: str = "equal_weight_universe"
```

## 输出指标

```text
annual_return
total_return
max_drawdown
sharpe
volatility
turnover
win_rate
cost_paid
excess_return_vs_equal_weight
excess_return_vs_benchmark
holdings_by_rebalance_date
equity_curve
```

## 基准

v1 至少支持：

```text
equal_weight_universe
buy_hold_universe_average
```

后续再接沪深300/中证500。

## 验收标准

1. TopN 回测能跑完当前股票池。
2. 输出权益曲线。
3. 输出持仓列表。
4. 成本越高收益越低。
5. TopN 能和等权基准比较。
6. 单元测试通过：

```bash
.venv/bin/python -m pytest tests/unit/test_topn_backtest.py -q
```

---

# PR6：Research API + 前端 AlphaResearch 页面

## 目标

把研究能力暴露给前端和脚本。

## 新增后端 API

```text
POST /api/research/dataset/build
POST /api/research/factor/ic
POST /api/research/factor/group-backtest
POST /api/research/topn-backtest
POST /api/research/report
```

## 前端页面

新增：

```text
frontend/src/views/AlphaResearch.vue
```

页面分 4 块：

1. 参数区
   - 股票池
   - 日期区间
   - 因子选择
   - horizon
   - 分组数
   - TopN

2. 因子 IC 表
   - factor
   - horizon
   - IC
   - RankIC
   - ICIR
   - positive ratio
   - missing ratio

3. 分组收益图
   - Q1~Q5 柱状/曲线
   - Q5-Q1 多空收益

4. TopN 回测图
   - 策略净值
   - 等权基准
   - 回撤
   - 当前持仓

## 前端验收

```bash
cd frontend
npm run build
```

---

## 4. 报告输出格式

新增：

```text
backend/research/report_builder.py
```

支持输出 JSON 和 Markdown。

每次 alpha report 至少包含：

```text
研究配置
- 股票池数量
- 起止日期
- 因子列表
- horizon
- 成本假设

因子总览表
- IC
- RankIC
- ICIR
- missing_ratio
- 分组多空收益

单因子详情
- 月度 IC
- Q1~Q5 收益
- 多空净值

TopN 策略
- 总收益
- 年化收益
- 最大回撤
- Sharpe
- Turnover
- 成本后收益
- vs 等权基准

结论
- 推荐因子
- 弃用因子
- 需要进一步验证的因子
```

---

## 5. 成功标准

Alpha Research v1 完成后，应该能做到：

```bash
make alpha-report FACTOR=momentum_60d HORIZON=20
make alpha-topn FACTOR=momentum_60d TOP_N=10
```

并能回答：

1. 这个因子 IC 是否显著？
2. 分组收益是否单调？
3. TopN 是否跑赢股票池等权？
4. 成本后是否仍有收益？
5. 是否值得进入策略层？

---

## 6. Makefile 建议

新增：

```makefile
alpha-test:
	.venv/bin/python -m pytest tests/unit/test_alpha_dataset_builder.py \
		tests/unit/test_factor_analysis.py \
		tests/unit/test_group_backtest.py \
		tests/unit/test_topn_backtest.py -q

alpha-smoke:
	.venv/bin/python scripts/run_alpha_smoke.py

alpha-report:
	.venv/bin/python scripts/run_alpha_report.py --factor $(FACTOR) --horizon $(HORIZON)

alpha-topn:
	.venv/bin/python scripts/run_alpha_topn.py --factor $(FACTOR) --top-n $(TOP_N)
```

---

## 7. scripts 建议

新增：

```text
scripts/run_alpha_smoke.py
scripts/run_alpha_report.py
scripts/run_alpha_topn.py
```

用途：

- 给开发者快速验证
- 给 CI/手工测试使用
- 不依赖前端

---

## 8. Hermes 执行建议

建议 Hermes 按以下顺序执行：

1. 先完成 PR1 dataset builder，不碰前端。
2. PR2 factor_library 完成后，先跑本地单因子计算。
3. PR3 IC 分析完成后，输出 JSON。
4. PR4 group backtest 完成后，输出因子分组报告。
5. PR5 TopN 完成后，才讨论策略接入。
6. PR6 最后做 API 和前端页面。

不要一开始就做 UI。  
不要一开始就改正式策略。  
不要一开始就追求收益率。  
先证明因子有没有预测力。

---

## 9. 暂不做事项

v1 明确不做：

- 机器学习模型
- 行业中性
- Barra 风格暴露
- 复杂风险模型
- 实盘交易
- 自动调参实盘推荐
- 高频/分钟级数据

这些等 v1 因子研究跑通后再说。

---

## 10. 最重要的验收口径

如果一个因子满足：

```text
RankIC 均值 > 0.03
ICIR > 0.3
Q5-Q1 年化收益 > 5%
TopN 成本后跑赢股票池等权
样本外不崩
```

才允许进入策略层。

否则只能保留为观察因子，不能拿去构建默认策略。
