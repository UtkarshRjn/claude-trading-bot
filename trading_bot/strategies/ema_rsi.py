from trading_bot.strategies.base import BaseStrategy


class EmaRsiStrategy(BaseStrategy):
    """
    Original strategy: EMA Crossover + RSI Filter.

    BUY  when: fast EMA crosses above slow EMA AND RSI not overbought
    SELL when: fast EMA crosses below slow EMA OR RSI overbought
    """

    def should_buy(self, df):
        r = df.iloc[-1]
        return bool(r["cross_up"] and r["rsi"] < self.cfg.RSI_OVERBOUGHT)

    def should_sell(self, df):
        r = df.iloc[-1]
        return bool(r["cross_down"] or r["rsi"] >= self.cfg.RSI_OVERBOUGHT)
