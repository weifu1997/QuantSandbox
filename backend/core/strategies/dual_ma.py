from __future__ import annotations

import pandas as pd


class DualMaStrategy:
    @staticmethod
    def generate(df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        df['trade_signal'] = 0

        fast = params.get('fast_period', 5)
        slow = params.get('slow_period', 20)

        df['fast_ma'] = df['close'].rolling(window=fast).mean()
        df['slow_ma'] = df['close'].rolling(window=slow).mean()

        df.loc[(df['fast_ma'] > df['slow_ma']) & (df['fast_ma'].shift(1) <= df['slow_ma'].shift(1)), 'trade_signal'] = 1
        df.loc[(df['fast_ma'] < df['slow_ma']) & (df['fast_ma'].shift(1) >= df['slow_ma'].shift(1)), 'trade_signal'] = -1

        return df
