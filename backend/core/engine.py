from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Any

from backend.core.position_manager import CurrentPosition, PositionManager
from backend.core.strategy import PositionTarget
from backend.core.strategy_contract import validate_per_bar_targets


class BacktestEngine:
    """专业级向量化与事件混合回测引擎"""

    def __init__(self, initial_cash=100000.0, commission_rate=0.00025, tax_rate=0.0005, slippage_rate=0.0005):
        self.initial_cash = initial_cash
        self.commission = commission_rate
        self.tax = tax_rate
        self.slippage_rate = slippage_rate
        self.logs = []

    def run_with_positions(self, df: pd.DataFrame, symbol: str, position_targets: list[PositionTarget]) -> dict:
        """真实 target_weight 撮合引擎。

        每根 bar 维护真实账户状态，按 target_weight 调仓：
        - 现金 (cash)
        - 持仓数量 (shares) — 按 100 股整手
        - 持仓市值 (market_value)
        - 总权益 (total_equity)
        - 当前目标权重 (current_weight)

        交易约束：
        - 停牌不交易
        - 涨停不买
        - 跌停不卖
        - 买入按资金约束缩量
        - 卖出不超过当前持仓
        费用：
        - commission (佣金) on buy & sell
        - tax (印花税) on sell only
        - slippage (滑点) on both buy & sell
        """
        df = df.copy()
        self.logs = []

        # ---- 账户状态 ----
        cash = self.initial_cash
        shares = 0
        avg_cost = 0.0
        trade_returns: list[float] = []
        equity_curve = []

        # ---- 验证 + 建档 target 按日期索引 ----
        # 两级校验：正式策略强制逐 bar；legacy 单 target 打 warning 但允许全段复用
        validate_per_bar_targets(position_targets, len(df), "unknown", symbol)

        target_by_date: dict[str, PositionTarget] = {}
        if len(position_targets) == 1 and len(df) > 1:
            # Legacy/smoke: 单 target 复用到所有 bar
            single = position_targets[0]
            for i in range(len(df)):
                trade_date = df.iloc[i]["date"].strftime("%Y-%m-%d")
                target_by_date[trade_date] = single
        else:
            for target in position_targets:
                bar_date = target.bar_date
                if not bar_date:
                    raise ValueError(
                        f"Strategy returned target without bar_date for {symbol}. "
                        f"All targets must have metadata.bar_date."
                    )
                target_by_date[str(bar_date)] = target

        for i in range(len(df)):
            row = df.iloc[i]
            trade_date = row['date'].strftime('%Y-%m-%d')

            # ---- 当前 bar 价格 ----
            open_price = float(row['open']) if not pd.isna(row['open']) else 0.0
            close_price = float(row['close']) if not pd.isna(row['close']) else 0.0
            reference_price = close_price if close_price > 0 else open_price
            if reference_price <= 0:
                reference_price = 0.01  # 极小值防止除零

            # ---- 停牌 / 涨跌停判断 ----
            is_suspended = pd.isna(row.get('volume')) or row.get('volume', 0) <= 0
            limit_ratio = row.get('limit_ratio', 0.10)
            is_limit_up = False
            is_limit_down = False
            # Use prev_close when available; fall back to same-bar close for bar 0
            prev_close = df.iloc[i - 1]['close'] if i > 0 else None
            if prev_close is None or pd.isna(prev_close) or prev_close <= 0:
                prev_close = close_price
            if prev_close > 0:
                limit_up_price = prev_close * (1 + limit_ratio)
                limit_down_price = prev_close * (1 - limit_ratio)
                is_limit_up = open_price >= limit_up_price or close_price >= limit_up_price
                is_limit_down = open_price <= limit_down_price or close_price <= limit_down_price

            # ---- 当前持仓市值 ----
            current_market_value = shares * close_price
            total_equity = cash + current_market_value

            # ---- 确定本 bar 的 target_weight（严格按 bar_date 匹配） ----
            bar_target = target_by_date.get(trade_date)
            if bar_target is None:
                raise KeyError(
                    f"No target for {symbol} on {trade_date}. "
                    f"Strategy must provide per-bar targets for all dates."
                )
            target_weight = max(0.0, min(0.30, float(bar_target.target_weight)))  # 单票上限 30%

            # ---- 当前实际权重 ----
            current_weight = current_market_value / total_equity if total_equity > 0 else 0.0

            # ---- 目标市值 vs 当前市值 ----
            target_market_value = total_equity * target_weight
            trade_value = target_market_value - current_market_value  # 正=买入, 负=卖出
            rebalance_threshold = 0.0
            if bar_target and bar_target.metadata:
                rebalance_threshold = float(bar_target.metadata.get("rebalance_threshold", 0.0) or 0.0)
            if rebalance_threshold > 0 and abs(target_weight - current_weight) < rebalance_threshold:
                trade_value = 0.0

            action = "hold"
            executed_shares = 0
            fee = 0.0
            fill_price = 0.0
            reason = ""
            commission_fee = 0.0
            tax_fee = 0.0

            if trade_value > 0:
                # ---- 买入 ----
                action = "buy"
                reason = "target_weight_buy"
                fill_price = open_price * (1 + self.slippage_rate)

                if is_suspended:
                    action = "buy_failed"
                    reason = "停牌，无法买入"
                elif is_limit_up:
                    action = "buy_failed"
                    reason = "涨停，无法买入"
                else:
                    # 按资金约束计算可买股数（整手）
                    planned_shares = int(abs(trade_value) / fill_price // 100 * 100)
                    if planned_shares == 0:
                        # trade_value 太小，不够一手
                        action = "hold"
                        reason = "trade_value_too_small_for_lot"
                    else:
                        # 实际可买受现金约束
                        max_affordable_value = cash / (1 + self.commission)
                        max_affordable_shares = int(max_affordable_value / fill_price // 100 * 100)
                        executed_shares = min(planned_shares, max_affordable_shares)

                        if executed_shares == 0:
                            action = "buy_failed"
                            reason = "资金不足，无法买入整手"
                        else:
                            actual_value = executed_shares * fill_price
                            commission_fee = actual_value * self.commission
                            cost = actual_value + commission_fee

                            if cost > cash:
                                # 安全保险：回退到可负担
                                executed_shares = max_affordable_shares
                                actual_value = executed_shares * fill_price
                                commission_fee = actual_value * self.commission
                                cost = actual_value + commission_fee

                            cash -= cost
                            prev_shares = shares
                            shares += executed_shares
                            fee = commission_fee
                            if shares > 0:
                                avg_cost = ((avg_cost * prev_shares) + (executed_shares * fill_price)) / shares

                            if executed_shares < planned_shares:
                                reason = "buy_trimmed_by_cash"

            elif trade_value < 0:
                # ---- 卖出 ----
                action = "sell"
                reason = "target_weight_sell"
                fill_price = open_price * (1 - self.slippage_rate)

                if is_suspended:
                    action = "sell_failed"
                    reason = "停牌，无法卖出"
                elif is_limit_down:
                    action = "sell_failed"
                    reason = "跌停，无法卖出"
                else:
                    planned_sell_value = abs(trade_value)
                    planned_shares = int(planned_sell_value / fill_price // 100 * 100)

                    # 卖出不超过当前持仓
                    executed_shares = min(planned_shares, shares)

                    if executed_shares == 0:
                        action = "hold"
                        reason = "sell_insufficient_shares_or_too_small"
                    else:
                        actual_value = executed_shares * fill_price
                        commission_fee = actual_value * self.commission
                        tax_fee = actual_value * self.tax
                        fee = commission_fee + tax_fee
                        revenue = actual_value - fee

                        # closed-trade return: average-cost basis, net of sell-side fees
                        if avg_cost > 0:
                            net_sell_price = revenue / executed_shares
                            realized_return = (net_sell_price - avg_cost) / avg_cost
                            trade_returns.append(realized_return)

                        cash += revenue
                        shares -= executed_shares
                        if shares == 0:
                            avg_cost = 0.0
            else:
                action = "hold"
                reason = "target_weight_unchanged"

            # ---- 日志记录 ----
            self._add_position_log(
                trade_date=trade_date,
                symbol=symbol,
                action=action,
                fill_price=fill_price if action not in ("hold",) else reference_price,
                shares=executed_shares,
                commission_fee=commission_fee,
                tax_fee=tax_fee,
                reason=reason,
                target_weight=round(target_weight, 6),
                current_weight=round(current_weight, 6),
                cash_after=cash,
                total_equity_before=round(total_equity, 2),
                total_equity_after=round(cash + shares * close_price, 2),
            )

            # ---- 每日净值快照（按收盘价） ----
            daily_equity = cash + shares * close_price
            equity_curve.append(daily_equity)

        df['target_weight'] = [
            float(target_by_date[row['date'].strftime('%Y-%m-%d')].target_weight)
            for _, row in df.iterrows()
        ]
        df['total_equity'] = equity_curve if equity_curve else [self.initial_cash] * len(df)
        df['position_mode'] = 'target_weight'

        metrics = self._calculate_metrics(df, trade_returns, symbol)
        metrics.update({
            "position_mode": "target_weight",
            "target_count": len(position_targets),
            "final_shares": shares,
            "final_cash": round(cash, 2),
            "avg_cost": round(avg_cost, 4) if avg_cost > 0 else 0.0,
            "active_target_weight": float(df['target_weight'].iloc[-1]) if len(df) else 0.0,
        })

        return {
            "metadata": self._clean_nan(metrics),
            "data": df,
            "logs": self.logs,
        }

    def run_portfolio(
        self,
        frames_by_ticker: dict[str, pd.DataFrame],
        strategy_cls: type,
        strategy_params: dict[str, Any] | None = None,
    ) -> dict:
        """多标的组合级真实回测引擎。

        所有标的共享同一个现金池，按 bar-by-bar 对齐执行：
        1. 每个 bar，先卖出需要减仓的标的（释放现金）
        2. 再按 confidence 从高到低买入需要加仓的标的
        3. 买入受共享现金池约束，资金不足时按目标市值占比缩量

        返回：
        - portfolio_equity: 组合级权益曲线
        - per_ticker: 每标的单独结果（metadata + equity）
        - logs: 所有标的的交易日志（按时间排序）
        """
        import pandas as pd
        
        strategy_params = strategy_params or {}
        self.logs = []

        # ---- 对齐所有标的到同一日期索引 ----
        aligned: dict[str, pd.DataFrame] = {}
        for ticker, df in frames_by_ticker.items():
            df = df.copy()
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            aligned[ticker] = df

        # 以最长的 DataFrame 为基准日期序列
        base_ticker = max(aligned, key=lambda t: len(aligned[t]))
        base_dates = aligned[base_ticker]["date"].tolist()

        # ---- 账户状态 ----
        cash = self.initial_cash
        positions: dict[str, dict[str, Any]] = {}  # ticker -> {shares, avg_cost}
        portfolio_equity: list[float] = []

        strategy_by_ticker = {ticker: strategy_cls(strategy_params) for ticker in aligned}

        # ---- 逐 bar 执行 ----
        for bar_idx in range(len(base_dates)):
            trade_date = base_dates[bar_idx].strftime("%Y-%m-%d")

            # ---- Step 1: 计算当前总权益和各标的市值 ----
            total_market_value = 0.0
            current_prices: dict[str, float] = {}
            current_weights: dict[str, float] = {}

            for ticker in aligned:
                df = aligned[ticker]
                if bar_idx >= len(df):
                    continue
                row = df.iloc[bar_idx]
                close_price = float(row["close"]) if not pd.isna(row["close"]) else 0.0
                if close_price <= 0:
                    close_price = 0.01
                current_prices[ticker] = close_price

                pos = positions.get(ticker, {"shares": 0})
                mv = pos["shares"] * close_price
                total_market_value += mv

            total_equity = cash + total_market_value

            # ---- Step 2: 生成各标的当前 target_weight（按 bar_date 匹配，不用 [-1]） ----
            targets: list[dict[str, Any]] = []
            for ticker in aligned:
                df = aligned[ticker]
                if bar_idx >= len(df):
                    continue
                strategy = strategy_by_ticker[ticker]
                pos_targets = strategy.generate_targets(df.iloc[: bar_idx + 1], ticker)
                tw = 0.0
                conf = 0.0
                rebalance_threshold = 0.0
                # 按 bar_date 匹配当前 bar 的 target（不再取 [-1]）
                bar_target = None
                for pt in pos_targets:
                    if pt.bar_date == trade_date:
                        bar_target = pt
                        break
                if bar_target is not None:
                    tw = float(bar_target.target_weight)
                    conf = float(bar_target.confidence)
                    if bar_target.metadata:
                        rebalance_threshold = float(bar_target.metadata.get("rebalance_threshold", 0.0) or 0.0)
                targets.append({
                    "ticker": ticker,
                    "target_weight": max(0.0, min(0.30, tw)),
                    "confidence": conf,
                    "rebalance_threshold": rebalance_threshold,
                })

            # ---- Step 3: 先卖后买 ----
            # Sell pass: 需要减仓的标的
            for t in targets:
                ticker = t["ticker"]
                target_weight = t["target_weight"]
                rebalance_threshold = float(t.get("rebalance_threshold", 0.0) or 0.0)
                close_price = current_prices.get(ticker, 0.0)
                if close_price <= 0:
                    continue
                pos = positions.get(ticker, {"shares": 0, "avg_cost": 0.0})
                current_mv = pos["shares"] * close_price
                current_weight = current_mv / total_equity if total_equity > 0 else 0.0

                if current_weight <= target_weight or (rebalance_threshold > 0 and abs(current_weight - target_weight) < rebalance_threshold):
                    continue  # no sell needed

                # 需要卖出
                target_mv = total_equity * target_weight
                sell_value = current_mv - target_mv
                sell_shares = int(sell_value / close_price // 100 * 100)
                sell_shares = min(sell_shares, pos["shares"])
                if sell_shares == 0:
                    continue

                fill_price = close_price * (1 - self.slippage_rate)
                actual_value = sell_shares * fill_price
                commission_fee = actual_value * self.commission
                tax_fee = actual_value * self.tax
                fee = commission_fee + tax_fee
                cash += (actual_value - fee)
                pos["shares"] -= sell_shares
                if pos["shares"] == 0:
                    positions.pop(ticker, None)
                else:
                    positions[ticker] = pos

                self._add_position_log(
                    trade_date=trade_date,
                    symbol=ticker,
                    action="sell",
                    fill_price=fill_price,
                    shares=sell_shares,
                    commission_fee=commission_fee,
                    tax_fee=tax_fee,
                    reason="portfolio_rebalance_sell",
                    target_weight=round(target_weight, 6),
                    current_weight=round(current_weight, 6),
                    cash_after=cash,
                    total_equity_before=round(total_equity, 2),
                    total_equity_after=round(cash + (pos["shares"] * close_price), 2),
                )

            # Recalculate total_equity after sells
            total_market_value = sum(
                positions.get(t, {"shares": 0})["shares"] * current_prices.get(t, 0.0)
                for t in aligned if bar_idx < len(aligned[t])
            )
            total_equity = cash + total_market_value

            # Buy pass: 需要加仓的标的，按 confidence 排序
            buy_targets = sorted(
                [t for t in targets if t["target_weight"] > 0],
                key=lambda t: (-t["confidence"], t["ticker"]),
            )
            for t in buy_targets:
                ticker = t["ticker"]
                target_weight = t["target_weight"]
                rebalance_threshold = float(t.get("rebalance_threshold", 0.0) or 0.0)
                close_price = current_prices.get(ticker, 0.0)
                if close_price <= 0:
                    continue

                pos = positions.get(ticker, {"shares": 0, "avg_cost": 0.0})
                current_mv = pos["shares"] * close_price
                current_weight = current_mv / total_equity if total_equity > 0 else 0.0

                if current_weight >= target_weight or (rebalance_threshold > 0 and abs(target_weight - current_weight) < rebalance_threshold):
                    continue  # no buy needed

                # ---- 停牌 / 涨跌停判断 ----
                df = aligned[ticker]
                if bar_idx >= len(df):
                    continue
                row = df.iloc[bar_idx]
                is_suspended = pd.isna(row.get("volume")) or row.get("volume", 0) <= 0
                limit_ratio = row.get("limit_ratio", 0.10)
                prev_close = df.iloc[bar_idx - 1]["close"] if bar_idx > 0 else close_price
                is_limit_up = False
                if prev_close > 0:
                    limit_up_price = prev_close * (1 + limit_ratio)
                    is_limit_up = close_price >= limit_up_price or float(row.get("open", close_price)) >= limit_up_price

                if is_suspended:
                    self._add_position_log(
                        trade_date=trade_date, symbol=ticker, action="buy_failed",
                        fill_price=close_price, shares=0, commission_fee=0.0, tax_fee=0.0,
                        reason="停牌，无法买入", target_weight=round(target_weight, 6),
                        current_weight=round(current_weight, 6), cash_after=cash,
                        total_equity_before=round(total_equity, 2),
                        total_equity_after=round(total_equity, 2),
                    )
                    continue
                if is_limit_up:
                    self._add_position_log(
                        trade_date=trade_date, symbol=ticker, action="buy_failed",
                        fill_price=close_price, shares=0, commission_fee=0.0, tax_fee=0.0,
                        reason="涨停，无法买入", target_weight=round(target_weight, 6),
                        current_weight=round(current_weight, 6), cash_after=cash,
                        total_equity_before=round(total_equity, 2),
                        total_equity_after=round(total_equity, 2),
                    )
                    continue

                fill_price = close_price * (1 + self.slippage_rate)
                target_mv = total_equity * target_weight
                buy_value = target_mv - current_mv
                planned_shares = int(buy_value / fill_price // 100 * 100)
                if planned_shares == 0:
                    continue

                max_affordable_value = cash / (1 + self.commission) if self.commission < 1 else cash
                max_affordable_shares = int(max_affordable_value / fill_price // 100 * 100)
                executed_shares = min(planned_shares, max_affordable_shares)
                if executed_shares == 0:
                    continue

                actual_value = executed_shares * fill_price
                commission_fee = actual_value * self.commission
                cost = actual_value + commission_fee
                if cost > cash:
                    executed_shares = max_affordable_shares
                    actual_value = executed_shares * fill_price
                    commission_fee = actual_value * self.commission
                    cost = actual_value + commission_fee

                cash -= cost
                pos["shares"] += executed_shares
                pos["avg_cost"] = ((pos["avg_cost"] * (pos["shares"] - executed_shares)) + (executed_shares * fill_price)) / max(pos["shares"], 1)
                positions[ticker] = pos

                reason = "portfolio_rebalance_buy"
                if executed_shares < planned_shares:
                    reason = "portfolio_buy_trimmed_by_cash"

                self._add_position_log(
                    trade_date=trade_date, symbol=ticker, action="buy",
                    fill_price=fill_price, shares=executed_shares,
                    commission_fee=commission_fee, tax_fee=0.0,
                    reason=reason, target_weight=round(target_weight, 6),
                    current_weight=round(current_weight, 6), cash_after=cash,
                    total_equity_before=round(total_equity, 2),
                    total_equity_after=round(cash + (pos["shares"] * close_price), 2),
                )

            # ---- Step 4: 每日净值快照 ----
            final_mv = sum(
                positions.get(t, {"shares": 0})["shares"] * current_prices.get(t, 0.0)
                for t in aligned if bar_idx < len(aligned[t])
            )
            portfolio_equity.append(cash + final_mv)

        # ---- 构建返回值 ----
        # 组合级指标
        portfolio_df = pd.DataFrame({
            "date": base_dates,
            "total_equity": portfolio_equity,
        })
        portfolio_metrics = self._calculate_metrics(portfolio_df, [], "PORTFOLIO")
        portfolio_metrics["ticker_count"] = len(aligned)
        portfolio_metrics["position_mode"] = "portfolio_target_weight"

        # ---- 组合级增强指标 ----
        # per_ticker_contribution: 每标的最终权益贡献
        per_ticker_contribution = {}
        for ticker in aligned:
            pos = positions.get(ticker, {"shares": 0})
            close_price = float(aligned[ticker]["close"].iloc[-1]) if not pd.isna(aligned[ticker]["close"].iloc[-1]) else 0.01
            per_ticker_contribution[ticker] = round(pos["shares"] * close_price, 2)

        # gross_exposure: 总持仓市值 / 总权益
        total_mv = sum(per_ticker_contribution.values())
        final_pe = portfolio_equity[-1] if portfolio_equity else self.initial_cash
        gross_exposure = round(total_mv / final_pe, 6) if final_pe > 0 else 0.0

        # concentration_ratio: 最大单票持仓占比
        max_single_mv = max(per_ticker_contribution.values()) if per_ticker_contribution else 0.0
        concentration_ratio = round(max_single_mv / total_mv, 6) if total_mv > 0 else 0.0

        # cash_utilization: 已使用资金占比
        cash_utilization = round(total_mv / self.initial_cash, 6)

        # average_position_count: 平均每 bar 持仓标的数
        position_counts_per_bar = []
        buy_sell_logs = [l for l in self.logs if l["action"] in ("buy", "sell")]
        if buy_sell_logs:
            running_positions = {}
            log_index = 0
            for bar_idx in range(len(base_dates)):
                while log_index < len(buy_sell_logs) and buy_sell_logs[log_index]["timestamp"] <= base_dates[bar_idx].strftime("%Y-%m-%d"):
                    ll = buy_sell_logs[log_index]
                    ticker = ll["ticker"]
                    if ll["action"] == "buy":
                        running_positions[ticker] = running_positions.get(ticker, 0) + ll["shares"]
                    elif ll["action"] == "sell":
                        running_positions[ticker] = max(0, running_positions.get(ticker, 0) - ll["shares"])
                        if running_positions[ticker] == 0:
                            running_positions.pop(ticker, None)
                    log_index += 1
                position_counts_per_bar.append(len([t for t, s in running_positions.items() if s > 0]))
            avg_pos_count = round(sum(position_counts_per_bar) / len(position_counts_per_bar), 2) if position_counts_per_bar else 0.0
        else:
            avg_pos_count = 0.0

        # turnover_rate: 日换手率（双边成交 / 权益均值）
        total_traded_value = 0.0
        for l in self.logs:
            if l["action"] in ("buy", "sell") and l["shares"] > 0:
                total_traded_value += l["shares"] * l["price"]
        avg_equity = sum(portfolio_equity) / len(portfolio_equity) if portfolio_equity else self.initial_cash
        turnover_rate = round(total_traded_value / avg_equity, 6) if avg_equity > 0 else 0.0

        # max_single_ticker_drawdown: 各标的最大回撤中的最大值
        max_single_dd = 0.0
        for ticker in aligned:
            df = aligned[ticker]
            ticker_equity = []
            for bar_idx in range(len(df)):
                row = df.iloc[bar_idx]
                close_price = float(row["close"]) if not pd.isna(row["close"]) else 0.01
                pos = positions.get(ticker, {"shares": 0})
                ticker_equity.append(pos["shares"] * close_price)
            if ticker_equity:
                series = pd.Series(ticker_equity)
                rolling_max = series.cummax()
                dd = ((series - rolling_max) / rolling_max.replace(0, 1.0)).min()
                if not pd.isna(dd) and dd < max_single_dd:
                    max_single_dd = float(dd)

        portfolio_metrics["per_ticker_contribution"] = per_ticker_contribution
        portfolio_metrics["gross_exposure"] = gross_exposure
        portfolio_metrics["concentration_ratio"] = concentration_ratio
        portfolio_metrics["cash_utilization"] = cash_utilization
        portfolio_metrics["average_position_count"] = avg_pos_count
        portfolio_metrics["turnover_rate"] = turnover_rate
        portfolio_metrics["max_single_ticker_drawdown"] = round(max_single_dd * 100, 2)

        # 每标的单独 equity
        per_ticker: dict[str, dict] = {}
        for ticker in aligned:
            df = aligned[ticker]
            ticker_equity = []
            for bar_idx in range(len(df)):
                row = df.iloc[bar_idx]
                close_price = float(row["close"]) if not pd.isna(row["close"]) else 0.0
                if close_price <= 0:
                    close_price = 0.01
                pos = positions.get(ticker, {"shares": 0})
                ticker_equity.append(pos["shares"] * close_price)
            
            ticker_df = df.copy()
            ticker_df["total_equity"] = ticker_equity
            tm = self._calculate_metrics(ticker_df, [], ticker)
            tm["position_mode"] = "portfolio_target_weight"
            final_s = positions.get(ticker, {"shares": 0})["shares"]
            tm["final_shares"] = final_s
            # Fix: _calculate_metrics uses self.initial_cash as baseline, but
            # per-ticker ticker_equity represents position market value (not
            # account equity). When no shares were ever held (final_s==0),
            # final_equity=0 and total_return incorrectly shows -100%.
            if final_s == 0:
                tm["total_return"] = 0.0
                tm["position_return"] = 0.0
                tm["avg_deployed_ratio"] = 0.0
                tm["max_drawdown"] = 0.0
                tm["sharpe_ratio"] = 0.0
            per_ticker[ticker] = {
                "metadata": tm,
                "equity": ticker_equity,
            }

        return self._clean_nan({
            "portfolio_metrics": portfolio_metrics,
            "portfolio_equity": portfolio_equity,
            "per_ticker": per_ticker,
            "logs": self.logs,
        })

    @staticmethod
    def _clean_nan(value):
        """递归清理 NaN/Inf，替换为 JSON-safe 默认值"""
        if isinstance(value, dict):
            return {k: BacktestEngine._clean_nan(v) for k, v in value.items()}
        if isinstance(value, list):
            return [BacktestEngine._clean_nan(v) for v in value]
        if isinstance(value, float):
            if np.isnan(value) or np.isinf(value):
                return 0.0
        return value

    def _calculate_metrics(self, df, trade_returns, symbol):
        """核心金融数学计算模块

        字段契约：`win_rate` / `pnl_ratio` 永远返回数值，同时提供
        `win_rate_display` / `pnl_ratio_display` 给前端直接展示。
        当没有已平仓交易时，数值字段为 0.0，展示字段为 "--"，避免
        API 漏字段或前端把 0 当作空值。
        """
        equity_series = df['total_equity']
        final_equity = equity_series.iloc[-1] if not equity_series.empty else self.initial_cash

        # 1. 累计收益率（账户整体）
        total_return = (final_equity - self.initial_cash) / self.initial_cash

        # 1b. 持仓收益率（按实际部署资金，不受闲置现金稀释）
        avg_tw = 0.0
        if 'target_weight' in df.columns and not df['target_weight'].empty:
            tw_series = df['target_weight']
            avg_tw_val = tw_series[tw_series > 0].mean()
            if pd.notna(avg_tw_val) and avg_tw_val > 0:
                avg_tw = float(avg_tw_val)
                deployed_capital = self.initial_cash * avg_tw
                position_return = (final_equity - self.initial_cash) / deployed_capital
            else:
                position_return = 0.0
        else:
            position_return = 0.0

        # 2. 最大回撤 (Max Drawdown) - 机构最看重的风控指标
        rolling_max = equity_series.cummax()
        drawdowns = (equity_series - rolling_max) / rolling_max
        max_drawdown = drawdowns.min() if not drawdowns.empty else 0

        # 3. 夏普比率 (Sharpe Ratio) - 衡量性价比 (假设无风险利率为0)
        df['daily_return'] = equity_series.pct_change().fillna(0)
        mean_return = df['daily_return'].mean()
        std_return = df['daily_return'].std()
        # 乘以根号252将日夏普年化
        sharpe = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0

        # 4. 胜率 (Win Rate) & 盈亏比 (PnL Ratio)
        win_rate, pnl_ratio = 0.0, 0.0
        if trade_returns:
            winning_trades = [r for r in trade_returns if r > 0]
            losing_trades = [r for r in trade_returns if r <= 0]

            win_rate = len(winning_trades) / len(trade_returns)

            avg_win = np.mean(winning_trades) if winning_trades else 0
            avg_loss = abs(np.mean(losing_trades)) if losing_trades else 0

            if avg_loss > 0:
                pnl_ratio = avg_win / avg_loss
            elif avg_win > 0:
                pnl_ratio = 99.9  # 全胜无败的情况

        closed_trade_count = len(trade_returns)
        has_closed_trades = closed_trade_count > 0
        win_rate_value = round(win_rate * 100, 2)
        pnl_ratio_value = round(pnl_ratio, 2)

        result = {
            "symbol": symbol,
            "final_equity": round(final_equity, 2),
            "total_return": round(total_return * 100, 2),
            "position_return": round(position_return * 100, 2),
            "avg_deployed_ratio": round(avg_tw * 100, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "win_rate": win_rate_value,
            "pnl_ratio": pnl_ratio_value,
            "win_rate_display": f"{win_rate_value}%" if has_closed_trades else "--",
            "pnl_ratio_display": f"{pnl_ratio_value}" if has_closed_trades else "--",
            "trade_count": closed_trade_count,
            "closed_trade_count": closed_trade_count,
            "has_closed_trades": has_closed_trades,
        }
        return self._clean_nan(result)

    def _add_position_log(
        self,
        trade_date,
        symbol,
        action,
        fill_price,
        shares,
        commission_fee,
        tax_fee,
        reason,
        target_weight,
        current_weight,
        cash_after,
        total_equity_before,
        total_equity_after,
    ):
        self.logs.append({
            "timestamp": trade_date,
            "signal_date": trade_date,
            "execution_date": trade_date,
            "ticker": symbol,
            "action": action,
            "price": round(fill_price, 2),
            "shares": shares,
            "fee": round(commission_fee + tax_fee, 2),
            "commission": round(commission_fee, 2),
            "tax": round(tax_fee, 2),
            "reason": reason,
            "target_weight": round(target_weight, 6),
            "current_weight": round(current_weight, 6),
            "cash_after": round(cash_after, 2),
            "total_equity_before": total_equity_before,
            "total_equity_after": total_equity_after,
        })
