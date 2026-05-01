from __future__ import annotations

import pandas as pd


class BollingerBandsStrategy:
    @staticmethod
    def generate(df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        df['trade_signal'] = 0

        window = params.get('window', 20)
        std_dev = params.get('std_dev', 2.0)

        df['middle_band'] = df['close'].rolling(window=window).mean()
        df['std'] = df['close'].rolling(window=window).std()
        df['upper_band'] = df['middle_band'] + (df['std'] * std_dev)
        df['lower_band'] = df['middle_band'] - (df['std'] * std_dev)

        df.loc[df['close'] < df['lower_band'], 'trade_signal'] = 1
        df.loc[df['close'] > df['upper_band'], 'trade_signal'] = -1

        return df
