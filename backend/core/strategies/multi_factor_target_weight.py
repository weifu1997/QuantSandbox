from __future__ import annotations

import pandas as pd
import math

from backend.core.factors import get_factor_registry
from backend.core.strategy import PositionTarget, Strategy


def _safe_factor_val(series: pd.Series, idx) -> float | None:
    """安全提取因子值，NaN/None → None。"""
    try:
        val = series.loc[idx]
        if pd.isna(val):
            return None
        return float(val)
    except (KeyError, TypeError, ValueError):
        return None


def _score_pe(pe: float | None, params: dict) -> float:
    """PE 估值打分：低 PE → 高分。缺失 → 0.50 中性。"""
    if pe is None:
        return 0.50
    pe_high = float(params.get("pe_high", 200.0))
    pe_warn = float(params.get("pe_warn", 100.0))
    pe_caution = float(params.get("pe_caution", 50.0))
    if pe > pe_high:
        return 0.0
    if pe > pe_warn:
        return 0.20
    if pe > pe_caution:
        return 0.40
    if pe > 30:
        return 0.60
    if pe > 15:
        return 0.80
    return 1.00


def _score_pb(pb: float | None, params: dict) -> float:
    """PB 估值打分：低 PB → 高分。缺失 → 0.50 中性。"""
    if pb is None:
        return 0.50
    pb_high = float(params.get("pb_high", 8.0))
    pb_warn = float(params.get("pb_warn", 4.0))
    if pb >= pb_high:
        return 0.0
    if pb >= pb_warn:
        return 0.30
    if pb >= 2:
        return 0.60
    if pb >= 1:
        return 0.80
    return 1.00


def _score_ma_cross(mac: float | None) -> float:
    """趋势打分：快均线相对慢均线的偏离比例。NaN → 0.30（中性偏空）。"""
    if mac is None:
        return 0.30
    if mac < -0.05:
        return 0.0
    if mac < -0.02:
        return 0.25
    if mac < 0:
        return 0.40
    if mac == 0:
        return 0.50
    if mac < 0.02:
        return 0.70
    if mac < 0.05:
        return 0.85
    return 1.0


def _score_macd_hist(hist: float | None) -> float:
    """动量打分：MACD 柱。NaN → 0.50 中性。"""
    if hist is None:
        return 0.50
    if hist < -1.0:
        return 0.0
    if hist < -0.3:
        return 0.25
    if hist < 0:
        return 0.40
    if hist == 0:
        return 0.50
    if hist < 0.3:
        return 0.65
    if hist < 1.0:
        return 0.80
    return 1.0


def _score_rsi(rsi: float | None) -> float:
    """超跌反转打分：RSI 低位 → 高分。NaN → 0.50 中性。"""
    if rsi is None:
        return 0.50
    if rsi < 25:
        return 0.90
    if rsi < 35:
        return 0.70
    if rsi <= 65:
        return 0.50
    if rsi <= 75:
        return 0.25
    if rsi <= 85:
        return 0.10
    return 0.0


def _score_atr(atr_pct: float | None) -> float:
    """波动率打分：高 ATR → 低分（降仓）。NaN → 0.50 中性。"""
    if atr_pct is None:
        return 0.50
    if atr_pct > 0.05:
        return 0.0
    if atr_pct > 0.03:
        return 0.30
    if atr_pct > 0.02:
        return 0.60
    if atr_pct > 0.01:
        return 0.80
    return 1.0

class MultiFactorTargetWeightStrategy(Strategy):
    """正式多因子目标仓位策略。

    五因子综合打分：
    - 估值 (25%): PE_TTM + PB — 高估降权
    - 趋势 (25%): MA 交叉 — 趋势向下最多轻仓
    - 动量 (20%): MACD 柱 — hist>0 加分
    - 反转 (20%): RSI 低位 — 超跌反转加分
    - 波动 (10%): ATR — 高波降仓

    score = 0.25×估值 + 0.25×趋势 + 0.20×动量 + 0.20×反转 + 0.10×波动
    effective_score = sqrt(max(0, (score - threshold) / (1 - threshold)))
    target_weight = max_target_weight × effective_score
    """

    name = "multi_factor_target_weight"
    description = "估值/趋势/动量/反转/波动 五因子综合仓位策略"
    factor_names = [
        "pe_ttm", "pb", "ma_cross_value", "macd_hist",
        "rsi_value", "atr_value",
    ]
    parameter_schema = {
        "max_target_weight": {"type": "number", "default": 0.30, "minimum": 0.0, "maximum": 1.0},
        "score_threshold": {"type": "number", "default": 0.35, "minimum": 0.0, "maximum": 1.0},
        "rebalance_threshold": {"type": "number", "default": 0.03, "minimum": 0.0, "maximum": 1.0},
        # 技术因子
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

    def generate_targets(self, df: pd.DataFrame, symbol: str) -> list[PositionTarget]:
        """逐 bar 生成多因子综合仓位目标。

        每 bar 返回一个 PositionTarget，携带完整的因子值和得分。
        """
        if df.empty:
            return [PositionTarget(
                symbol=symbol, target_weight=0.0, confidence=0.0,
                metadata={"reason": "empty_dataframe", "bar_date": ""},
            )]

        params = self.params
        max_target_weight = float(params.get("max_target_weight", 0.30))
        score_threshold = float(params.get("score_threshold", 0.35))
        rebalance_threshold = float(params.get("rebalance_threshold", 0.03))

        # 获取因子实例并配置参数
        registry = get_factor_registry()

        rsi_factor = registry.get("rsi_value")
        rsi_factor.period = int(params.get("rsi_period", 14))

        ma_factor = registry.get("ma_cross_value")
        ma_factor.fast = int(params.get("ma_fast", 5))
        ma_factor.slow = int(params.get("ma_slow", 20))

        macd_factor = registry.get("macd_hist")
        macd_factor.fast = int(params.get("macd_fast", 12))
        macd_factor.slow = int(params.get("macd_slow", 26))
        macd_factor.signal = int(params.get("macd_signal", 9))

        atr_factor = registry.get("atr_value")
        atr_factor.period = int(params.get("atr_period", 14))

        pe_factor = registry.get("pe_ttm")
        pb_factor = registry.get("pb")

        # 预计算所有因子序列
        rsi_series = rsi_factor.compute(df)
        ma_series = ma_factor.compute(df)
        macd_series = macd_factor.compute(df)
        atr_series = atr_factor.compute(df)
        pe_series = pe_factor.compute(df)
        pb_series = pb_factor.compute(df)

        # ATR 百分比（ATR / close）
        close_series = pd.to_numeric(df["close"], errors="coerce")
        atr_pct_series = atr_series / close_series.replace(0, pd.NA)

        targets: list[PositionTarget] = []

        for idx, row in df.iterrows():
            # bar_date
            raw_date = row.get("date")
            bar_date = raw_date.strftime("%Y-%m-%d") if hasattr(raw_date, "strftime") else str(raw_date or "")

            # 提取因子值
            pe = _safe_factor_val(pe_series, idx)
            pb = _safe_factor_val(pb_series, idx)
            mac = _safe_factor_val(ma_series, idx)
            macd_hist = _safe_factor_val(macd_series, idx)
            rsi = _safe_factor_val(rsi_series, idx)
            atr_pct = _safe_factor_val(atr_pct_series, idx)

            # 各因子打分
            valuation_pe = _score_pe(pe, params)
            valuation_pb = _score_pb(pb, params)
            valuation_score = 0.6 * valuation_pe + 0.4 * valuation_pb

            trend_score = _score_ma_cross(mac)
            momentum_score = _score_macd_hist(macd_hist)
            reversal_score = _score_rsi(rsi)
            volatility_score = _score_atr(atr_pct)

            # 综合得分
            score = (
                0.25 * valuation_score
                + 0.25 * trend_score
                + 0.20 * momentum_score
                + 0.20 * reversal_score
                + 0.10 * volatility_score
            )
            score = max(0.0, min(1.0, score))

            # 综合置信度（基于各因子偏离中性的平均幅度）
            confidence = (
                abs(valuation_score - 0.50)
                + abs(trend_score - 0.50)
                + abs(momentum_score - 0.50)
                + abs(reversal_score - 0.50)
                + abs(volatility_score - 0.50)
            ) / (5 * 0.50)  # 归一化到 [0, 1]

            # 仓位判定（中心相对法：score 偏离中性 0.50 决定仓位）
            if score < score_threshold:
                target_weight = 0.0
                reason = "score_below_threshold"
            else:
                # effective_score: 将 [threshold, 1.0] 非线性映射到 [0, 1]
                # 使用平方根平滑：small scores get disproportionately small weight
                linear = (score - score_threshold) / (1.0 - score_threshold)
                effective_score = linear ** 0.5  # sqrt 使低分更保守，高分更容易接近上限
                target_weight = max_target_weight * effective_score
                reason = "multi_factor_position"

            target_weight = round(float(target_weight), 6)

            metadata = {
                "strategy": self.name,
                "bar_date": bar_date,
                "reason": reason,
                "score": round(score, 4),
                "rebalance_threshold": rebalance_threshold,
                "factor_values": {
                    "valuation": {
                        "pe": round(pe, 2) if pe is not None else None,
                        "pb": round(pb, 2) if pb is not None else None,
                        "score": round(valuation_score, 4),
                        "pe_sub": round(valuation_pe, 4),
                        "pb_sub": round(valuation_pb, 4),
                    },
                    "trend": {
                        "ma_cross_value": round(mac, 6) if mac is not None else None,
                        "score": round(trend_score, 4),
                    },
                    "momentum": {
                        "macd_hist": round(macd_hist, 6) if macd_hist is not None else None,
                        "score": round(momentum_score, 4),
                    },
                    "reversal": {
                        "rsi": round(rsi, 2) if rsi is not None else None,
                        "score": round(reversal_score, 4),
                    },
                    "volatility": {
                        "atr_pct": round(atr_pct, 6) if atr_pct is not None else None,
                        "score": round(volatility_score, 4),
                    },
                },
            }

            targets.append(PositionTarget(
                symbol=symbol,
                target_weight=target_weight,
                confidence=round(float(confidence), 6),
                metadata=metadata,
            ))

        return targets
