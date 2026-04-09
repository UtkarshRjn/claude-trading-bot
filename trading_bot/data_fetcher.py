import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import ccxt
from kiteconnect import KiteConnect
from alpaca_trade_api import REST as AlpacaREST

log = logging.getLogger(__name__)


class DataFetcher:
    def __init__(self, cfg):
        self.cfg = cfg

    def fetch_ohlcv(self, symbol):
        try:
            if self.cfg.BROKER == "binance":
                ex = ccxt.binance({
                    "apiKey": self.cfg.BINANCE_API_KEY,
                    "secret": self.cfg.BINANCE_SECRET,
                    "enableRateLimit": True,
                })
                raw = ex.fetch_ohlcv(symbol, self.cfg.TIMEFRAME, limit=self.cfg.CANDLE_LIMIT)
                df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

            elif self.cfg.BROKER == "zerodha":
                kite = KiteConnect(api_key=self.cfg.ZERODHA_API_KEY)
                kite.set_access_token(self.cfg.ZERODHA_ACCESS_TOKEN)
                imap = {
                    "1m": "minute", "5m": "5minute", "15m": "15minute",
                    "30m": "30minute", "1h": "60minute", "1d": "day",
                }
                to_dt = datetime.now()
                fr_dt = to_dt - timedelta(days=60)
                data = kite.historical_data(
                    instrument_token=256265,
                    from_date=fr_dt, to_date=to_dt,
                    interval=imap.get(self.cfg.TIMEFRAME, "60minute"),
                )
                df = pd.DataFrame(data).rename(columns={"date": "timestamp"})

            elif self.cfg.BROKER == "alpaca":
                api = AlpacaREST(
                    self.cfg.ALPACA_API_KEY, self.cfg.ALPACA_SECRET_KEY,
                    self.cfg.ALPACA_BASE_URL,
                )
                tf_map = {
                    "1m": "1Min", "5m": "5Min", "15m": "15Min",
                    "30m": "30Min", "1h": "1Hour", "1d": "1Day",
                }
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=max(30, self.cfg.CANDLE_LIMIT // 7))
                bars = api.get_bars(
                    symbol, tf_map.get(self.cfg.TIMEFRAME, "1Hour"),
                    start=start_dt.strftime("%Y-%m-%d"),
                    end=end_dt.strftime("%Y-%m-%d"),
                    limit=self.cfg.CANDLE_LIMIT, feed="iex",
                ).df
                bars = bars.reset_index()
                df = pd.DataFrame({
                    "timestamp": bars["timestamp"],
                    "open": bars["open"], "high": bars["high"],
                    "low": bars["low"], "close": bars["close"],
                    "volume": bars["volume"],
                })

            else:
                df = self._synthetic(symbol)

            return df.set_index("timestamp").sort_index()
        except Exception as e:
            log.error(f"fetch_ohlcv({symbol}): {e}")
            raise

    def fetch_ohlcv_range(self, symbol, start, end):
        """Fetch OHLCV data for a specific date range (for backtesting)."""
        if self.cfg.BROKER == "alpaca":
            api = AlpacaREST(
                self.cfg.ALPACA_API_KEY, self.cfg.ALPACA_SECRET_KEY,
                self.cfg.ALPACA_BASE_URL,
            )
            tf_map = {
                "1m": "1Min", "5m": "5Min", "15m": "15Min",
                "30m": "30Min", "1h": "1Hour", "1d": "1Day",
            }
            bars = api.get_bars(
                symbol, tf_map.get(self.cfg.TIMEFRAME, "1Hour"),
                start=start, end=end, limit=10000, feed="iex",
            ).df
            bars = bars.reset_index()
            df = pd.DataFrame({
                "timestamp": bars["timestamp"],
                "open": bars["open"], "high": bars["high"],
                "low": bars["low"], "close": bars["close"],
                "volume": bars["volume"],
            })
            return df.set_index("timestamp").sort_index()
        else:
            return self.fetch_ohlcv(symbol)

    def get_price(self, symbol):
        try:
            if self.cfg.BROKER == "binance":
                ex = ccxt.binance({"enableRateLimit": True})
                return float(ex.fetch_ticker(symbol)["last"])
            elif self.cfg.BROKER == "zerodha":
                kite = KiteConnect(api_key=self.cfg.ZERODHA_API_KEY)
                kite.set_access_token(self.cfg.ZERODHA_ACCESS_TOKEN)
                return float(kite.quote([symbol])[symbol]["last_price"])
            elif self.cfg.BROKER == "alpaca":
                api = AlpacaREST(
                    self.cfg.ALPACA_API_KEY, self.cfg.ALPACA_SECRET_KEY,
                    self.cfg.ALPACA_BASE_URL,
                )
                return float(api.get_latest_trade(symbol).price)
            else:
                return float(self._synthetic(symbol)["close"].iloc[-1])
        except Exception as e:
            log.error(f"get_price({symbol}): {e}")
            return 0.0

    @staticmethod
    def _synthetic(symbol):
        np.random.seed(hash(symbol) % 9999)
        n = 200
        base = 50000 if "BTC" in symbol else 3000
        prices = base * np.cumprod(1 + np.random.normal(0.0002, 0.015, n))
        ts = pd.date_range(end=datetime.now(), periods=n, freq="1h")
        noise = lambda: np.random.uniform(-0.01, 0.01, n)
        return pd.DataFrame({
            "timestamp": ts,
            "open": prices * (1 + noise()),
            "high": prices * (1 + np.abs(noise())),
            "low": prices * (1 - np.abs(noise())),
            "close": prices,
            "volume": np.random.uniform(100, 5000, n),
        })
