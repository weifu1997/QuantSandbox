from __future__ import annotations

import pandas as pd


class RsiReversalStrategy:
    @staticmethod
    def generate(df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        df['trade_signal'] = 0

        window = params.get('window', 14)
        buy_threshold = params.get('buy_threshold', 30)
        sell_threshold = params.get('sell_threshold', 70)

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()

        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        df.loc[(df['rsi'] < buy_threshold) & (df['rsi'].shift(1) >= buy_threshold), 'trade_signal'] = 1
        df.loc[(df['rsi'] > sell_threshold) & (df['rsi'].shift(1) <= sell_threshold), 'trade_signal'] = -1

        return df
