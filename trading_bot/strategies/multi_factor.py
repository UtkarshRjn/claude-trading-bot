from trading_bot.strategies.base import BaseStrategy


class MultiFactorStrategy(BaseStrategy):
    """
    Multi-factor strategy: VWAP + MACD + RSI + ADX + Volume + EMA.

    BUY when ALL are true:
      1. EMA(9) crosses above EMA(21)
      2. Price > VWAP (institutional buying)
      3. MACD line > Signal line (momentum)
      4. ADX > 20 (trending market)
      5. RSI between 30-65 (momentum without overbought)
      6. Volume > 20-period MA (participation)

    SELL when ANY is true:
      1. EMA cross down (trend reversal)
      2. RSI > 75 (overbought)
    """

    def should_buy(self, df):
        r = df.iloc[-1]
        return bool(
            r["cross_up"]
            and r["close"] > r["vwap"]
            and r["macd_line"] > r["macd_signal"]
            and r["adx"] > self.cfg.ADX_THRESHOLD
            and self.cfg.RSI_ENTRY_LOW <= r["rsi"] <= self.cfg.RSI_ENTRY_HIGH
            and r["volume"] > r["volume_ma"]
        )

    def should_sell(self, df):
        r = df.iloc[-1]
        return bool(
            r["cross_down"]
            or r["rsi"] > self.cfg.RSI_EXIT
        )
