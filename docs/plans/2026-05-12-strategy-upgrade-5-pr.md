# 策略体系升级：demo 降级 + 多因子正式策略 + 契约/测试/配置锁死

> **For Hermes:** 使用 quantsandbox-batched-development + writing-plans 技能逐 PR 执行。

**Goal:** 将 target_weight_demo 降级为 smoke test 校验器，新增 multi_factor_target_weight 正式策略为默认策略，固化策略契约、测试和配置。

**Architecture:** 5 个 PR，每个在 `make smoke` 下独立验证。新增 `strategy_contract.py` 公共约束模块。

**Tech Stack:** Python 3.12, pd/np, FastAPI, pytest, .venv, QuantSandbox 因子体系

---

## 当前状态问题清单 (来自代码审查)

### Engine 侧缺陷
1. **run_with_positions (L59-67)**: `global_target` 兜底让只返回单个 target 的策略静默通行
2. **run_portfolio (L339)**: `current_target = pos_targets[-1]` — 取最后一个 target 当成所有 bar 的目标！这是最大的 bug
3. **run_with_positions (L109-111)**: 每 bar 的 `rebalance_threshold` 从 `bar_target.metadata` 取，合理但依赖 bar_date 索引

### Strategy 侧
4. **contract**: 抽象方法声明 `generate_targets → list[PositionTarget]` 但无数量的契约约束
5. **target_weight_demo**: 已实现逐 bar 输出（90行的正确实现），但 registry 默认它就是默认策略
6. **PositionTarget**: 只有 `symbol/target_weight/confidence/metadata`，无硬性 bar_date 要求

### 测试侧
7. `StubPositionEngine` 的 `run_with_positions` (L14): 用 `targets[0].target_weight` 填充所有行 — 隐含对单 target 模式的依赖
8. 测试函数引用策略名 `target_weight_demo` 分散在多处

---

## PR1: 策略契约固化（strategy_contract.py + engine 修正）

### 目标
让所有正式策略强制返回逐 bar target，引擎不再容忍单 target 兜底。

### 改动文件
| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/core/strategy_contract.py` | **新增** | 契约工具：`validate_per_bar_targets()` / `WARNING_LEGACY_SINGLE` |
| `backend/core/strategy.py` | 修改 | `PositionTarget` 增加 `bar_date` 属性；`Strategy.generate_targets` 契约收紧 |
| `backend/core/engine.py` | 修改 | `run_with_positions`: 移除 `global_target` fallback，要求所有 target 有 `bar_date`；`run_portfolio`: `pos_targets[-1]` → 按 bar_date 取当前 bar target |
| `tests/unit/test_strategy_contract.py` | **新增** | 契约单元测试 |

### 关键代码

#### strategy_contract.py
```python
"""策略契约工具：确保所有正式策略返回逐 bar target。"""

import logging
from backend.core.strategy import PositionTarget

logger = logging.getLogger(__name__)

LEGACY_SINGLE_TARGET_WARNING = (
    "LEGACY: strategy returned a single target; "
    "formal strategies MUST return per-bar targets (len(targets) == len(df)). "
    "Single-target fallback will be removed in v2.0."
)

def validate_per_bar_targets(
    targets: list[PositionTarget],
    df_len: int,
    strategy_name: str,
    symbol: str,
) -> list[PositionTarget]:
    """验证策略返回的 targets 是否符合逐 bar 契约。
    
    - 长度必须等于 df_len（正式策略硬约束）
    - 每个 target 的 metadata 必须包含 bar_date
    - 返回原始 targets（通过则不变，供链式调用）
    """
    if len(targets) == 1 and df_len > 1:
        logger.warning(
            f"{strategy_name} ({symbol}): {LEGACY_SINGLE_TARGET_WARNING}"
        )
    elif len(targets) != df_len:
        raise ValueError(
            f"{strategy_name} ({symbol}): target count {len(targets)} "
            f"does not match dataframe length {df_len}. "
            f"Formal strategies must return exactly one PositionTarget per bar."
        )
    
    for i, t in enumerate(targets):
        if not t.metadata.get("bar_date"):
            raise ValueError(
                f"{strategy_name} ({symbol}): target[{i}] missing metadata.bar_date"
            )
    
    return targets
```

#### strategy.py — PositionTarget 加 bar_date
```python
@dataclass(slots=True)
class PositionTarget:
    symbol: str
    target_weight: float
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def bar_date(self) -> str | None:
        """从 metadata 提取 bar_date，方便引擎侧使用。"""
        return self.metadata.get("bar_date")

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "target_weight": self.targetWeight,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }
```

#### engine.py — run_with_positions 移除 global_target
```python
# 旧代码 (L53-67) — 删除 global_target fallback
# 新代码:
target_by_date: dict[str, PositionTarget] = {}
for target in position_targets:
    bar_date = target.bar_date
    if not bar_date:
        raise ValueError(
            f"Strategy returned target without bar_date for {symbol}. "
            f"All targets must have metadata.bar_date."
        )
    target_by_date[str(bar_date)] = target

# ... 在 bar 循环中 (L100):
bar_target = target_by_date.get(trade_date)
if bar_target is None:
    raise KeyError(
        f"No target for {symbol} on {trade_date}. "
        f"Strategy must provide per-bar targets for all dates."
    )
target_weight = max(0.0, min(0.30, float(bar_target.target_weight)))
```

#### engine.py — run_portfolio 修正 target 选取
```python
# 旧代码 (L328-349) — 用 pos_targets[-1]
# 新代码: 按 bar_date 取当前 bar 的 target
# 在 run_portfolio 的 bar 循环中:
trade_date = base_dates[bar_idx].strftime("%Y-%m-%d")

targets: list[dict[str, Any]] = []
for ticker in aligned:
    df = aligned[ticker]
    if bar_idx >= len(df):
        continue
    strategy = strategy_by_ticker[ticker]
    pos_targets = strategy.generate_targets(df.iloc[: bar_idx + 1], ticker)
    
    # 按 bar_date 匹配当前 bar 的 target
    bar_target = None
    for pt in pos_targets:
        if pt.bar_date == trade_date:
            bar_target = pt
            break
    if bar_target is None:
        tw, conf, rebal = 0.0, 0.0, 0.0
    else:
        tw = float(bar_target.target_weight)
        conf = float(bar_target.confidence)
        rebal = float(bar_target.metadata.get("rebalance_threshold", 0.0) or 0.0)
    targets.append({...})
```

### 验证
```bash
cd /root/project/QuantSandbox
.venv/bin/python -m pytest tests/unit/test_strategy_contract.py -v
make smoke
```

---

## PR2: 新增 multi_factor_target_weight 正式策略

### 目标
实现一个完整的 5 因子仓位策略，替换 demo 成为默认。

### 改动文件
| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/core/strategies/multi_factor_target_weight.py` | **新增** | 多因子策略实现 |
| `backend/core/strategies/registry.py` | 修改 | 注册新策略（暂不切换默认） |

### 策略逻辑

```
score = 
  0.25 * valuation_score   (pe_ttm + pb)
+ 0.25 * trend_score        (ma_cross_value)
+ 0.20 * momentum_score     (macd_hist)
+ 0.20 * reversal_score     (rsi_value)
+ 0.10 * volatility_score   (atr_value)

target_weight = max_target_weight * clip(score, 0, 1)
低于 score_threshold → target_weight = 0
abs(target_weight - current_weight) < rebalance_threshold → 不调仓
```

#### 各因子打分逻辑

**valuation_score** (pe_ttm + pb):
- PE 缺失 → 0.50 (中性)
- PE > 200 → 0.0 (极高估)
- PE > 100 → 0.20
- PE > 50 → 0.40
- PE > 30 → 0.60
- PE > 15 → 0.80
- PE ≤ 15 → 1.00
- PB 同理，阈值: ≥ 8 → 0.0, ≥ 4 → 0.3, ≥ 2 → 0.6, ≥ 1 → 0.8, < 1 → 1.0
- 缺失 → 0.50
- valuation_score = 0.6 * pe_score + 0.4 * pb_score

**trend_score** (ma_cross_value):
- NaN → 0.30 (中性偏空，数据不足时不激进)
- < -0.05 → 0.0 (强下跌趋势)
- < -0.02 → 0.25
- < 0 → 0.40
- == 0 → 0.50
- > 0 → 0.70
- > 0.02 → 0.85
- > 0.05 → 1.0 (强上涨趋势)

**momentum_score** (macd_hist):
- NaN → 0.50
- < -1.0 → 0.0
- < -0.3 → 0.25
- < 0 → 0.40
- == 0 → 0.50
- > 0 → 0.65
- > 0.3 → 0.80
- > 1.0 → 1.0

**reversal_score** (rsi_value):
- NaN → 0.50
- < 25 → 0.90 (深度超卖，反转概率高)
- < 35 → 0.70
- 35-65 → 0.50 (中性区)
- > 65 → 0.25
- > 75 → 0.10
- > 85 → 0.0 (深度超买)

**volatility_score** (atr/close):
- NaN → 0.50
- atr_pct > 0.05 → 0.0 (高波动，降仓)
- atr_pct > 0.03 → 0.30
- atr_pct > 0.02 → 0.60
- atr_pct > 0.01 → 0.80
- ≤ 0.01 → 1.0

**综合**:
```python
score = (
    0.25 * valuation_score
    + 0.25 * trend_score
    + 0.20 * momentum_score
    + 0.20 * reversal_score
    + 0.10 * volatility_score
)
# clip and threshold
if score < score_threshold:  # default 0.35
    target_weight = 0.0
else:
    target_weight = max_target_weight * min(max(score, 0.0), 1.0)
```

#### 参数 schema
```python
parameter_schema = {
    "max_target_weight": {"type": "number", "default": 0.30, "minimum": 0.0, "maximum": 1.0},
    "score_threshold": {"type": "number", "default": 0.35, "minimum": 0.0, "maximum": 1.0},
    "rebalance_threshold": {"type": "number", "default": 0.03, "minimum": 0.0, "maximum": 1.0},
    # 技术因子参数
    "ma_fast": {"type": "integer", "default": 5, "minimum": 1},
    "ma_slow": {"type": "integer", "default": 20, "minimum": 2},
    "rsi_period": {"type": "integer", "default": 14, "minimum": 2},
    "macd_fast": {"type": "integer", "default": 12, "minimum": 1},
    "macd_slow": {"type": "integer", "default": 26, "minimum": 2},
    "macd_signal": {"type": "integer", "default": 9, "minimum": 1},
    "atr_period": {"type": "integer", "default": 14, "minimum": 2},
    # 估值阈值
    "pe_high": {"type": "number", "default": 200.0, "minimum": 0.0},
    "pe_warn": {"type": "number", "default": 100.0, "minimum": 0.0},
    "pe_caution": {"type": "number", "default": 50.0, "minimum": 0.0},
    "pb_high": {"type": "number", "default": 8.0, "minimum": 0.0},
    "pb_warn": {"type": "number", "default": 4.0, "minimum": 0.0},
}
```

#### generate_targets 实现要点
- 逐 bar 计算，返回 `len(df)` 个 target
- 每个 target 带 `metadata.bar_date`、`metadata.reason`、`metadata.factor_values`、`metadata.score`
- PE/PB 缺失 → 对应子打分中性（0.50），不报错
- 因子值 NaN → 子打分中性
- 依赖因子: `rsi_value, ma_cross_value, macd_hist, atr_value, pe_ttm, pb`

### 验证
```bash
cd /root/project/QuantSandbox
# 导入检查
.venv/bin/python -c "from backend.core.strategies.multi_factor_target_weight import MultiFactorTargetWeightStrategy; print('OK')"
# 生成 targets 基本测试
.venv/bin/python -c "
import pandas as pd
from backend.core.strategies.multi_factor_target_weight import MultiFactorTargetWeightStrategy
df = pd.DataFrame({
    'date': pd.date_range('2024-01-02', periods=30, freq='B'),
    'open': [10]*30, 'high': [11]*30, 'low': [9]*30, 'close': [10]*30,
    'volume': [1000]*30, 'name': ['TEST']*30,
})
s = MultiFactorTargetWeightStrategy()
targets = s.generate_targets(df, 'TEST')
assert len(targets) == 30, f'Expected 30, got {len(targets)}'
print(f'OK: {len(targets)} targets generated')
"
```

---

## PR3: 注册表切换 + demo 降级为 smoke test

### 目标
- 默认策略从 `target_weight_demo` 切换到 `multi_factor_target_weight`
- `target_weight_demo` 保留为注册策略（用于 smoke test 对比）
- 更新所有引用

### 改动文件
| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/core/strategies/registry.py` | 修改 | 导入 + 注册 `MultiFactorTargetWeightStrategy` |
| `tests/integration/test_strategy_backtest_registry_api.py` | 修改 | 更新策略名引用为 `multi_factor_target_weight` |
| `tests/integration/test_walk_forward_api.py` | 修改 | 同上 |
| `tests/integration/test_portfolio_backtest.py` | 修改 | 同上 |
| `tests/integration/test_optimizer_api.py` | 修改 | 同上 |
| `tests/integration/test_backtest_summary_diagnostics.py` | 修改 | 同上 |

### registry.py 变更
```python
from .target_weight_demo import TargetWeightDemoStrategy
from .multi_factor_target_weight import MultiFactorTargetWeightStrategy

def get_strategy_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(MultiFactorTargetWeightStrategy)  # 默认第一个注册=默认
    registry.register(TargetWeightDemoStrategy)          # 保留供 smoke test
    return registry
```

### 测试策略名迁移
所有测试中 `"target_weight_demo"` → `"multi_factor_target_weight"`，同时：
- 参数也从 `{"rsi_period": 5}` → `{"rsi_period": 5, "max_target_weight": 0.30}` (新策略参数兼容)
- `factor_names` 断言从 `["rsi_value"]` → 新策略的因子列表
- `StubPositionEngine` 不需要变（它 mock 的是 engine，不关心策略）

### 验证
```bash
cd /root/project/QuantSandbox
# 先检查旧策略名残留
grep -rn "target_weight_demo" tests/ backend/ --include="*.py" | grep -v "import\|TargetWeightDemo\|\.pyc"
# 确保只剩下策略类定义和 import 引用，没有硬编码策略名字符串断言
make smoke
```

---

## PR4: 测试锁死（contract + strategy + engine + WF）

### 目标
用测试把策略契约、新策略行为、引擎修正锁死。

### 改动文件
| 文件 | 操作 | 说明 |
|------|------|------|
| `tests/unit/test_strategy_contract.py` | **新增** | 契约测试 |
| `tests/unit/test_multi_factor_strategy.py` | **新增** | 策略行为测试 |
| `tests/unit/test_engine_contract.py` | **新增** | 引擎契约测试 |
| `tests/integration/test_strategy_backtest_registry_api.py` | 修改 | 加契约 assert |
| `tests/integration/test_walk_forward_api.py` | 修改 | 加逐 bar 契约 assert |
| `tests/integration/test_portfolio_backtest.py` | 修改 | 不能取 pos_targets[0] |
| `Makefile` | 修改 | smoke 加入新测试文件 |

### 测试清单

#### test_strategy_contract.py
```python
def test_generate_targets_count_equals_df_length():
    """单票：target 数量等于 K 线数量"""
    
def test_all_targets_have_bar_date():
    """每个 target 必须有 metadata.bar_date"""
    
def test_all_targets_have_reason():
    """每个 target 必须有 metadata.reason"""
    
def test_all_targets_have_score():
    """每个 target 必须有 metadata.score"""
    
def test_all_targets_have_factor_values():
    """每个 target 必须有 metadata.factor_values"""
    
def test_single_target_on_multi_bar_df_raises():
    """多 bar df 只返回一个 target → 应报错（正式策略）"""
    
def test_validate_per_bar_targets_rejects_mismatch():
    """长度不匹配抛 ValueError"""
```

#### test_multi_factor_strategy.py
```python
def test_per_bar_output_length_matches_df():
    """30 bar df → 30 targets"""
    
def test_empty_df_returns_single_zero_target():
    """空 df → 一个零仓位 target"""
    
def test_target_weight_in_range():
    """所有 target_weight 在 [0, max_target_weight] 之间"""
    
def test_score_in_range():
    """所有 metadata.score 在 [0, 1] 之间"""
    
def test_target_weight_varies():
    """至少在有信号的样本中 target_weight 有变化（不是全 0 或全同）"""
    
def test_factor_values_present():
    """所有 target 的 factor_values 包含 5 个子分数"""
    
def test_pe_missing_does_not_error():
    """PE 列缺失 → 不报错，估值打分中性"""
    
def test_all_nan_factors_gives_zero_or_low_weight():
    """所有因子 NaN → score 降低"""
    
def test_rebalance_threshold_present():
    """每个 target metadata 含 rebalance_threshold"""
```

#### test_engine_contract.py
```python
def test_run_with_positions_rejects_target_without_bar_date():
    """target 无 bar_date → 抛错"""
    
def test_run_with_positions_no_global_fallback():
    """target_by_date 缺失某天 → 抛 KeyError（不再 global_target 兜底）"""
    
def test_run_portfolio_uses_bar_date_not_last():
    """组合回测按 bar_date 取 target，不用 [-1]"""
```

#### test_strategy_backtest_registry_api.py 加断言
```python
# 在现有 test_strategy_backtest_single_ticker_returns_diagnostics 中加:
# 验证 details 中 target_count 字段等于 klines 长度
```

#### test_walk_forward_api.py 加断言
```python
def test_walk_forward_per_window_targets_are_per_bar():
    """每个窗口 test 段的 target 数量 == test_rows"""
```

#### test_portfolio_backtest.py 加断言
```python
def test_portfolio_does_not_use_pos_targets_first():
    """验证 run_portfolio 不是简单取第一个 target"""
```

### 验证
```bash
cd /root/project/QuantSandbox
.venv/bin/python -m pytest tests/unit/ -v
.venv/bin/python -m pytest tests/integration/ -v -k 'not data_fetch and not e2e'
make smoke
```

---

## PR5: 配置锁死 + 端到端验证

### 目标
config.yaml / config.example.yaml 一致锁定，make smoke 完整通过。

### 改动文件
| 文件 | 操作 | 说明 |
|------|------|------|
| `config.yaml` | 修改 | strategy.name → multi_factor_target_weight |
| `config.example.yaml` | 修改 | strategy.name → multi_factor_target_weight，参数同步 |
| `Makefile` | 修改 | smoke 列表加入新增测试文件 |

### config 变更
```yaml
strategy:
  name: multi_factor_target_weight
  parameters:
    max_target_weight: 0.30
    score_threshold: 0.35
    rebalance_threshold: 0.03
    rsi_period: 14
    ma_fast: 5
    ma_slow: 20
    macd_fast: 12
    macd_slow: 26
    macd_signal: 9
    atr_period: 14
```

### Makefile smoke 更新
```makefile
smoke:
	@echo "=== compile ==="
	python3 -m compileall -q backend
	@echo "=== frontend build ==="
	cd frontend && npm run build
	@echo "=== unit tests ==="
	.venv/bin/python -m pytest -q tests/unit/
	@echo "=== regression tests ==="
	.venv/bin/python -m pytest -q \
		tests/integration/test_strategy_backtest_registry_api.py \
		tests/integration/test_portfolio_backtest.py \
		tests/integration/test_walk_forward_api.py \
		tests/integration/test_optimizer_api.py \
		tests/integration/test_backtest_summary_diagnostics.py \
		tests/integration/test_config_api.py
	@echo ""
	@echo "✅ smoke passed"
```

### 最终验证
```bash
cd /root/project/QuantSandbox
# 1. grep 残留检查
grep -rn "target_weight_demo" tests/ --include="*.py" | grep -v "import\|TargetWeightDemo\|def test"
# 应只有 import/class 引用，无语义断言残留

# 2. grep 默认策略确认
grep "strategy:" config.yaml config.example.yaml
# 应显示 multi_factor_target_weight

# 3. 全量 smoke
make smoke

# 4. 全量 test
make test
```

---

## 执行顺序约束

```
PR1 (契约) ──→ PR2 (新策略) ──→ PR3 (注册切换) ──→ PR4 (测试) ──→ PR5 (配置)
     │              │                │                  │               │
     └── 必须先于 ──┘                │                  │               │
                    └── 必须先于 ────┘                  │               │
                                     └── 必须先于 ──────┘               │
                                                          └── 必须先于 ──┘
```

每个 PR 结束时跑 `make smoke`（PR1/PR2/PR3 可能因引用链暂时失败是预期的，PR4/PR5 必须全绿）。

---

## 风险点和缓解

| 风险 | 缓解 |
|------|------|
| engine 移除 global_target 导致现有测试失败 | StubPositionEngine 独立于真实 engine，需确保 stub 符合新契约 |
| run_portfolio 修正影响 Walk-Forward 优化器 | 优化器走 run_with_positions（单票），run_portfolio 只在 portfolio_mode=True 时调用 |
| 新策略首次生成需要 PE/PB 列 | 测试数据需包含这些列或用 NaN 中性处理 |
| 策略名全局替换遗漏 | grep 策略名字符串 + 逐文件 diff review |

---

## 成功标准

- [ ] `grep "target_weight_demo"` 在业务逻辑/断言中零残留
- [ ] `make smoke` 全绿（compile + build + unit + integration）
- [ ] `make test` 全绿
- [ ] `multi_factor_target_weight` 是 registry 第一个注册策略（=默认）
- [ ] `config.yaml` 和 `config.example.yaml` 一致指向新策略
- [ ] 所有正式策略 `generate_targets` 返回 `len(df)` 个 target
- [ ] engine 无 `global_target` fallback
- [ ] `run_portfolio` 按 bar_date 取 target
