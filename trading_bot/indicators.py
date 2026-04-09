import pandas as pd
import numpy as np


class Indicators:

    @staticmethod
    def ema(s, n):
        return s.ewm(span=n, adjust=False).mean()

    @staticmethod
    def rsi(s, n):
        d = s.diff()
        gain = d.clip(lower=0).rolling(n).mean()
        loss = (-d.clip(upper=0)).rolling(n).mean()
        return 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    @staticmethod
    def atr(h, l, c, n):
        tr = pd.concat(
            [(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1
        ).max(axis=1)
        return tr.rolling(n).mean()

    @staticmethod
    def adx(high, low, close, period):
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr = pd.concat(
            [(high - low), (high - close.shift()).abs(), (low - close.shift()).abs()],
            axis=1,
        ).max(axis=1)

        atr_smooth = tr.rolling(period).sum()
        plus_di = 100 * plus_dm.rolling(period).sum() / atr_smooth
        minus_di = 100 * minus_dm.rolling(period).sum() / atr_smooth

        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        return dx.rolling(period).mean()

    @staticmethod
    def macd(close, fast, slow, signal):
        macd_line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
        macd_signal = macd_line.ewm(span=signal, adjust=False).mean()
        macd_hist = macd_line - macd_signal
        return macd_line, macd_signal, macd_hist

    @staticmethod
    def vwap(high, low, close, volume):
        typical_price = (high + low + close) / 3
        cum_tp_vol = (typical_price * volume).cumsum()
        cum_vol = volume.cumsum()
        return cum_tp_vol / cum_vol

    @staticmethod
    def volume_ma(volume, period):
        return volume.rolling(period).mean()

    @classmethod
    def compute(cls, df, cfg):
        df = df.copy()

        # Core indicators
        df["ema_fast"] = cls.ema(df["close"], cfg.EMA_FAST)
        df["ema_slow"] = cls.ema(df["close"], cfg.EMA_SLOW)
        df["rsi"] = cls.rsi(df["close"], cfg.RSI_PERIOD)
        df["atr"] = cls.atr(df["high"], df["low"], df["close"], cfg.ATR_PERIOD)

        # Crossovers
        df["cross_up"] = (df["ema_fast"] > df["ema_slow"]) & (
            df["ema_fast"].shift() <= df["ema_slow"].shift()
        )
        df["cross_down"] = (df["ema_fast"] < df["ema_slow"]) & (
            df["ema_fast"].shift() >= df["ema_slow"].shift()
        )

        # ADX
        df["adx"] = cls.adx(df["high"], df["low"], df["close"], cfg.ADX_PERIOD)

        # MACD
        df["macd_line"], df["macd_signal"], df["macd_hist"] = cls.macd(
            df["close"], cfg.MACD_FAST, cfg.MACD_SLOW, cfg.MACD_SIGNAL
        )

        # VWAP
        df["vwap"] = cls.vwap(df["high"], df["low"], df["close"], df["volume"])

        # Volume MA
        df["volume_ma"] = cls.volume_ma(df["volume"], cfg.VOLUME_MA_PERIOD)

        return df
