from __future__ import annotations

import pandas as pd


class QualityTrendBreakoutStrategy:
    """强势突破回踩策略 v1.1

    第一版规则：
    - 长期趋势向上：close > MA250
    - 中期突破确认：突破 MA60 或 20 日高点
    - 突破位上方连续站稳 2 天后，才允许回踩确认入场
    - 5 日动量更强，要求 > 2%
    - 成交量不塌
    - RSI 不过热
    - 出场：跌破 MA60/MA250、固定止损、盈利追踪止损、超时退出
    """

    @staticmethod
    def generate(df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        df["trade_signal"] = 0

        ma_long = int(params.get("ma_long", 250))
        ma_mid = int(params.get("ma_mid", 60))
        breakout_window = int(params.get("breakout_window", 20))
        pullback_band = float(params.get("pullback_band", 0.03))
        rsi_window = int(params.get("rsi_window", 14))
        rsi_upper = float(params.get("rsi_upper", 70))
        volume_ma_window = int(params.get("volume_ma_window", 20))
        volume_ratio_floor = float(params.get("volume_ratio_floor", 0.8))
        momentum_window = int(params.get("momentum_window", 5))
        breakout_confirm_days = int(params.get("breakout_confirm_days", 2))
        momentum_floor = float(params.get("momentum_floor", 0.02))
        stop_loss = float(params.get("stop_loss", 0.07))
        profit_activation = float(params.get("profit_activation", 0.10))
        trail_stop = float(params.get("trail_stop", 0.06))
        max_hold_days = int(params.get("max_hold_days", 45))

        df["ma_long"] = df["close"].rolling(window=ma_long).mean()
        df["ma_mid"] = df["close"].rolling(window=ma_mid).mean()
        df["breakout_line"] = df["close"].rolling(window=breakout_window).max().shift(1)
        df["volume_ma"] = df["volume"].rolling(window=volume_ma_window).mean()
        df["momentum_5d"] = df["close"].pct_change(momentum_window)

        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_window).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        in_position = False
        entry_price = 0.0
        peak_price = 0.0
        hold_days = 0
        breakout_line_at_entry = 0.0
        breakout_above_days = 0

        for i in range(len(df)):
            row = df.iloc[i]
            close = row.get("close")
            volume = row.get("volume")
            ma_l = row.get("ma_long")
            ma_m = row.get("ma_mid")
            breakout_line = row.get("breakout_line")
            vol_ma = row.get("volume_ma")
            rsi = row.get("rsi")
            momentum = row.get("momentum_5d")

            if pd.isna(close):
                continue

            prev_row = df.iloc[i - 1] if i > 0 else None
            prev_close = prev_row.get("close") if prev_row is not None else None
            prev_breakout = prev_row.get("breakout_line") if prev_row is not None else None

            if not in_position:
                trend_ok = pd.notna(ma_l) and close > ma_l

                if pd.notna(breakout_line) and pd.notna(close):
                    if close > breakout_line:
                        breakout_above_days += 1
                    else:
                        breakout_above_days = 0
                else:
                    breakout_above_days = 0

                breakout_ok = pd.notna(breakout_line) and close > breakout_line
                confirm_ok = breakout_above_days >= breakout_confirm_days

                pullback_ok = False
                if pd.notna(breakout_line):
                    pullback_ok = close >= breakout_line * (1 - pullback_band)

                momentum_ok = pd.notna(momentum) and momentum > momentum_floor

                volume_ok = True
                if pd.notna(vol_ma) and vol_ma > 0 and pd.notna(volume):
                    volume_ok = volume >= vol_ma * volume_ratio_floor

                rsi_ok = True
                if pd.notna(rsi):
                    rsi_ok = rsi < rsi_upper

                if trend_ok and breakout_ok and confirm_ok and pullback_ok and momentum_ok and volume_ok and rsi_ok:
                    df.at[df.index[i], "trade_signal"] = 1
                    in_position = True
                    entry_price = float(close)
                    peak_price = float(close)
                    hold_days = 0
                    breakout_line_at_entry = float(breakout_line) if pd.notna(breakout_line) else float(close)
                    breakout_above_days = 0
                continue

            hold_days += 1
            if pd.notna(close):
                peak_price = max(peak_price, float(close))
            peak_return = (peak_price - entry_price) / entry_price if entry_price > 0 else 0.0
            current_return = (float(close) - entry_price) / entry_price if entry_price > 0 else 0.0

            stop_loss_hit = pd.notna(entry_price) and entry_price > 0 and close <= entry_price * (1 - stop_loss)
            trend_break = pd.notna(ma_l) and close < ma_l
            breakout_fail = pd.notna(breakout_line_at_entry) and breakout_line_at_entry > 0 and close < breakout_line_at_entry * (1 - pullback_band)
            soft_trend_break = pd.notna(ma_m) and close < ma_m and peak_return < profit_activation
            trailing_stop_hit = peak_return >= profit_activation and close <= peak_price * (1 - trail_stop)
            time_exit = hold_days >= max_hold_days

            if stop_loss_hit or trend_break or breakout_fail or soft_trend_break or trailing_stop_hit or time_exit:
                df.at[df.index[i], "trade_signal"] = -1
                in_position = False
                entry_price = 0.0
                peak_price = 0.0
                hold_days = 0
                breakout_line_at_entry = 0.0

        return df
