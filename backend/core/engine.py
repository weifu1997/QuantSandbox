import pandas as pd
import numpy as np


class BacktestEngine:
    """专业级向量化与事件混合回测引擎"""

    def __init__(self, initial_cash=100000.0, commission_rate=0.00025, tax_rate=0.0005, slippage_rate=0.0005):
        self.initial_cash = initial_cash
        self.commission = commission_rate
        self.tax = tax_rate
        self.slippage_rate = slippage_rate
        self.logs = []

    def run(self, df: pd.DataFrame, symbol: str):
        cash = self.initial_cash
        shares = 0
        equity_curve = []
        self.logs = []

        # 记录每笔闭环交易的收益率，用于计算胜率和盈亏比
        trade_returns = []
        entry_price = 0.0

        # 使用“前一交易日信号 -> 下一交易日开盘执行”的机制，避免信号与成交同日造成回看偏差
        pending_signal = 0
        pending_signal_date = None

        for i in range(len(df)):
            row = df.iloc[i]
            current_price = row['open']
            current_close = row['close']
            current_signal = row['trade_signal']
            trade_date = row['date'].strftime('%Y-%m-%d')

            prev_close = df.iloc[i - 1]['close'] if i > 0 else None
            is_suspended = pd.isna(row.get('volume')) or row.get('volume', 0) <= 0
            limit_ratio = row.get('limit_ratio', 0.10)
            is_limit_up = False
            is_limit_down = False
            if prev_close is not None and not pd.isna(prev_close) and prev_close > 0:
                limit_up_price = prev_close * (1 + limit_ratio)
                limit_down_price = prev_close * (1 - limit_ratio)
                is_limit_up = current_price >= limit_up_price or current_close >= limit_up_price
                is_limit_down = current_price <= limit_down_price or current_close <= limit_down_price

            # --- 交易撮合逻辑 ---
            # 1. 先执行前一交易日留下来的信号
            if pending_signal == 1 and shares == 0:
                if is_suspended:
                    self._add_log(
                        trade_date,
                        symbol,
                        "买入失败",
                        current_price,
                        0,
                        0.0,
                        "停牌，无法买入",
                        signal_date=pending_signal_date,
                        execution_date=trade_date,
                    )
                elif is_limit_up:
                    self._add_log(
                        trade_date,
                        symbol,
                        "买入失败",
                        current_price,
                        0,
                        0.0,
                        "涨停，无法买入",
                        signal_date=pending_signal_date,
                        execution_date=trade_date,
                    )
                else:
                    # 买入按当日开盘价 + 滑点成交
                    fill_price = current_price * (1 + self.slippage_rate)
                    shares_to_buy = int(cash / (fill_price * (1 + self.commission)) // 100 * 100)
                    if shares_to_buy > 0:
                        principal = shares_to_buy * fill_price
                        commission_fee = principal * self.commission
                        cost = principal + commission_fee
                        cash -= cost
                        shares = shares_to_buy
                        entry_price = fill_price
                        self._add_log(
                            trade_date,
                            symbol,
                            "买入",
                            fill_price,
                            shares,
                            commission_fee,
                            "前一交易日策略买入信号",
                            signal_date=pending_signal_date,
                            execution_date=trade_date,
                        )

            elif pending_signal == -1 and shares > 0:
                if is_suspended:
                    self._add_log(
                        trade_date,
                        symbol,
                        "卖出失败",
                        current_price,
                        shares,
                        0.0,
                        "停牌，无法卖出",
                        signal_date=pending_signal_date,
                        execution_date=trade_date,
                    )
                elif is_limit_down:
                    self._add_log(
                        trade_date,
                        symbol,
                        "卖出失败",
                        current_price,
                        shares,
                        0.0,
                        "跌停，无法卖出",
                        signal_date=pending_signal_date,
                        execution_date=trade_date,
                    )
                else:
                    # 卖出按当日开盘价 - 滑点成交
                    fill_price = current_price * (1 - self.slippage_rate)
                    principal = shares * fill_price
                    fee = principal * (self.commission + self.tax)
                    revenue = principal * (1 - self.commission - self.tax)

                    # 计算这单交易的绝对净利润率
                    trade_return = (revenue - (shares * entry_price)) / (shares * entry_price)
                    trade_returns.append(trade_return)

                    cash += revenue
                    self._add_log(
                        trade_date,
                        symbol,
                        "卖出",
                        fill_price,
                        shares,
                        fee,
                        "前一交易日策略卖出信号",
                        signal_date=pending_signal_date,
                        execution_date=trade_date,
                    )
                    shares = 0
                    entry_price = 0.0

            # 2. 每日净值快照（按收盘价计值）
            daily_equity = cash + shares * current_close
            equity_curve.append(daily_equity)

            # 3. 当前交易日的信号留给下一交易日执行
            pending_signal = current_signal
            pending_signal_date = trade_date

        # 将资金曲线写入 Dataframe 给前端画图
        df['total_equity'] = equity_curve

        # 计算高阶金融指标
        metrics = self._calculate_metrics(df, trade_returns, symbol)

        return {
            "metadata": metrics,  # 包含了完整的战报指标
            "data": df,          # 包含了 K 线和 资金曲线 (total_equity)
            "logs": self.logs
        }

    def _calculate_metrics(self, df, trade_returns, symbol):
        """核心金融数学计算模块"""
        equity_series = df['total_equity']
        final_equity = equity_series.iloc[-1] if not equity_series.empty else self.initial_cash

        # 1. 累计收益率
        total_return = (final_equity - self.initial_cash) / self.initial_cash

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

        return {
            "symbol": symbol,
            "final_equity": round(final_equity, 2),
            "total_return": round(total_return * 100, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "win_rate": round(win_rate * 100, 2),
            "pnl_ratio": round(pnl_ratio, 2),
            "trade_count": len(trade_returns)
        }

    def _add_log(self, date, ticker, action, price, shares, fee, reason, signal_date=None, execution_date=None):
        self.logs.append({
            "timestamp": execution_date or date,
            "signal_date": signal_date or date,
            "execution_date": execution_date or date,
            "ticker": ticker,
            "action": action,
            "price": round(price, 2),
            "shares": shares,
            "fee": round(fee, 2),
            "reason": reason
        })
