import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant

from trading_bot.strategies.base import BaseStrategy


class PairsTradingStrategy(BaseStrategy):
    """
    Statistical Arbitrage — Pairs Trading via Cointegration + Z-Score.

    How it works:
    1. Find pairs of stocks that are cointegrated (prices move together long-term)
    2. Compute the spread = Stock_A - hedge_ratio * Stock_B
    3. When spread deviates far from mean (high z-score), bet on reversion:
       - Z > +entry_z: spread too high → SHORT A, LONG B
       - Z < -entry_z: spread too low  → LONG A, SHORT B
    4. Exit when spread reverts to mean (z-score crosses 0)
    5. Stop loss if z-score blows out past stop_z

    This is NOT directional — it profits from the RELATIONSHIP between stocks,
    regardless of whether the market goes up or down.
    """

    # --- Pair discovery ---

    @staticmethod
    def find_cointegrated_pairs(stock_data, lookback=None):
        """
        Test all stock combinations for cointegration.
        Returns list of (stock_a, stock_b, p_value, hedge_ratio) sorted by p-value.
        """
        symbols = list(stock_data.keys())
        pairs = []

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                s1, s2 = symbols[i], symbols[j]
                df1 = stock_data[s1]["close"]
                df2 = stock_data[s2]["close"]

                # Align on common timestamps
                common = df1.index.intersection(df2.index)
                if len(common) < 60:
                    continue
                p1 = df1.loc[common].values
                p2 = df2.loc[common].values

                if lookback:
                    p1 = p1[-lookback:]
                    p2 = p2[-lookback:]

                try:
                    _, p_value, _ = coint(p1, p2)
                except Exception:
                    continue

                if p_value < 0.05:  # statistically significant
                    # Compute hedge ratio via OLS
                    model = OLS(p1, add_constant(p2)).fit()
                    hedge_ratio = model.params[1]
                    pairs.append((s1, s2, p_value, hedge_ratio))

        pairs.sort(key=lambda x: x[2])  # best p-value first
        return pairs

    # --- Spread computation ---

    @staticmethod
    def compute_spread(prices_a, prices_b, hedge_ratio):
        """Spread = A - hedge_ratio * B"""
        return prices_a - hedge_ratio * prices_b

    @staticmethod
    def compute_zscore(spread, lookback=60):
        """Rolling z-score of the spread."""
        mean = spread.rolling(lookback).mean()
        std = spread.rolling(lookback).std()
        return (spread - mean) / std.replace(0, np.nan)

    # --- Signal generation ---

    def should_open_pair(self, zscore, cfg):
        """
        Returns:
          +1 = spread too HIGH → short A, long B
          -1 = spread too LOW  → long A, short B
           0 = no signal
        """
        z = zscore
        if z > cfg.PAIRS_ENTRY_Z:
            return +1  # spread stretched up
        elif z < -cfg.PAIRS_ENTRY_Z:
            return -1  # spread stretched down
        return 0

    def should_close_pair(self, zscore, direction, cfg):
        """
        Close when spread reverts to mean or hits stop.
        direction: +1 or -1 (same as what should_open_pair returned)
        """
        z = zscore
        # Mean reversion: z-score crossed zero
        if direction == +1 and z <= cfg.PAIRS_EXIT_Z:
            return True
        if direction == -1 and z >= -cfg.PAIRS_EXIT_Z:
            return True
        # Stop loss: spread blew out further
        if abs(z) > cfg.PAIRS_STOP_Z:
            return True
        return False

    # --- Position sizing for pairs ---

    def size_pair_position(self, capital, price_a, price_b, hedge_ratio, cfg):
        """
        Size both legs of the pair trade.
        Total notional capped at MAX_POSITION_PCT of capital.
        """
        max_notional = capital * cfg.MAX_POSITION_PCT
        # Notional per unit = price_a + hedge_ratio * price_b
        notional_per_unit = price_a + abs(hedge_ratio) * price_b
        if notional_per_unit <= 0:
            return 0, 0
        units = max_notional / notional_per_unit
        qty_a = units
        qty_b = units * abs(hedge_ratio)
        return qty_a, qty_b
