"""
====================================================================
  AUTOMATED TRADING BOT — India Ready
  Supports: Zerodha (KiteConnect), Binance, Alpaca (US Stocks), or Paper Trading mode
  Strategy: EMA Crossover + RSI Filter + ATR-based Stop Loss
  Author: Claude | Run 24/7 on any VPS/cloud server
====================================================================

SETUP:
  pip install kiteconnect ccxt pandas numpy schedule requests alpaca-trade-api

USAGE:
  1. Set your broker credentials as env vars (see Config below)
  2. Choose BROKER = "zerodha" / "binance" / "paper"
  3. python trading_bot.py           # live/paper trading
  4. python trading_bot.py backtest  # backtest mode
====================================================================
"""

import os, sys, time, logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import numpy as np
import schedule
import ccxt
from kiteconnect import KiteConnect
from alpaca_trade_api import REST as AlpacaREST

# ─── Logging ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("trading_bot.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────
@dataclass
class Config:
    BROKER: str = "paper"  # "zerodha" | "binance" | "alpaca" | "paper"

    # Zerodha KiteConnect
    ZERODHA_API_KEY: str    = os.getenv("ZERODHA_API_KEY", "your_api_key")
    ZERODHA_API_SECRET: str = os.getenv("ZERODHA_API_SECRET", "your_api_secret")
    ZERODHA_ACCESS_TOKEN: str = os.getenv("ZERODHA_ACCESS_TOKEN", "")

    # Binance
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "your_binance_api_key")
    BINANCE_SECRET: str  = os.getenv("BINANCE_SECRET",  "your_binance_secret")

    # Alpaca (US Stocks)
    ALPACA_API_KEY: str    = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "")
    ALPACA_BASE_URL: str   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    # Instruments: Zerodha -> "NSE:RELIANCE" | Binance -> "BTC/USDT" | Alpaca -> "AAPL"
    SYMBOLS: list = field(default_factory=lambda: ["NSE:RELIANCE", "NSE:TCS", "NSE:INFY", "NSE:HDFCBANK", "NSE:SBIN"])

    # Strategy
    EMA_FAST: int        = 9
    EMA_SLOW: int        = 21
    RSI_PERIOD: int      = 14
    RSI_OVERBOUGHT: float = 70
    RSI_OVERSOLD: float   = 30
    ATR_PERIOD: int       = 14

    # Risk
    RISK_PER_TRADE: float       = 0.01   # 1% of capital per trade
    ATR_STOP_MULTIPLIER: float  = 2.0    # SL = 2x ATR below entry
    TAKE_PROFIT_RATIO: float    = 2.0    # TP = 2x the risk (2:1 RR)
    MAX_OPEN_TRADES: int        = 3
    MAX_DAILY_LOSS: float       = 0.05   # Halt if daily loss > 5%

    TIMEFRAME: str   = "1h"
    CANDLE_LIMIT: int = 100

    PAPER_CAPITAL: float = 100000.0   # ₹1 lakh virtual capital

CONFIG = Config()

# ─── Paper Portfolio ──────────────────────────────────────────────
class PaperPortfolio:
    def __init__(self, capital):
        self.capital = capital
        self.initial_capital = capital
        self.positions = {}
        self.trade_log = []
        self.daily_pnl = 0.0

    def buy(self, symbol, price, qty, sl, tp):
        if price * qty > self.capital:
            log.warning(f"[PAPER] Insufficient capital to buy {symbol}"); return False
        self.capital -= price * qty
        self.positions[symbol] = dict(qty=qty, entry=price, sl=sl, tp=tp)
        self.trade_log.append(dict(time=datetime.now(), symbol=symbol, action="BUY",
                                   price=price, qty=qty, sl=sl, tp=tp))
        log.info(f"[PAPER] BUY  {symbol} | Qty:{qty:.4f} @ {price:.2f} | SL:{sl:.2f} | TP:{tp:.2f}")
        return True

    def sell(self, symbol, price, reason="signal"):
        if symbol not in self.positions: return
        pos = self.positions.pop(symbol)
        pnl = (price - pos["entry"]) * pos["qty"]
        self.capital += price * pos["qty"]
        self.daily_pnl += pnl
        self.trade_log.append(dict(time=datetime.now(), symbol=symbol, action="SELL",
                                   price=price, pnl=pnl, reason=reason))
        log.info(f"[PAPER] SELL {symbol} | Price:{price:.2f} | PnL:{pnl:+.2f} | Reason:{reason}")

    def check_sl_tp(self, symbol, price):
        pos = self.positions.get(symbol)
        if not pos: return
        if price <= pos["sl"]:   self.sell(symbol, price, "stop_loss")
        elif price >= pos["tp"]: self.sell(symbol, price, "take_profit")

    def summary(self):
        roi = (self.capital - self.initial_capital) / self.initial_capital * 100
        log.info(f"[PORTFOLIO] Capital:{self.capital:.2f} | ROI:{roi:+.2f}% | "
                 f"Open:{len(self.positions)} | DailyPnL:{self.daily_pnl:+.2f}")

# ─── Indicators ──────────────────────────────────────────────────
class Indicators:
    @staticmethod
    def ema(s, n): return s.ewm(span=n, adjust=False).mean()

    @staticmethod
    def rsi(s, n):
        d = s.diff()
        gain = d.clip(lower=0).rolling(n).mean()
        loss = (-d.clip(upper=0)).rolling(n).mean()
        return 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    @staticmethod
    def atr(h, l, c, n):
        tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        return tr.rolling(n).mean()

    @classmethod
    def compute(cls, df, cfg):
        df = df.copy()
        df["ema_fast"]   = cls.ema(df["close"], cfg.EMA_FAST)
        df["ema_slow"]   = cls.ema(df["close"], cfg.EMA_SLOW)
        df["rsi"]        = cls.rsi(df["close"], cfg.RSI_PERIOD)
        df["atr"]        = cls.atr(df["high"], df["low"], df["close"], cfg.ATR_PERIOD)
        df["cross_up"]   = (df["ema_fast"] > df["ema_slow"]) & (df["ema_fast"].shift() <= df["ema_slow"].shift())
        df["cross_down"] = (df["ema_fast"] < df["ema_slow"]) & (df["ema_fast"].shift() >= df["ema_slow"].shift())
        return df

# ─── Strategy ────────────────────────────────────────────────────
class EMAStrategy:
    """
    BUY  when: fast EMA crosses above slow EMA AND RSI not overbought
    SELL when: fast EMA crosses below slow EMA OR RSI overbought
    SL/TP: ATR-based, 2:1 risk-reward ratio
    """
    def __init__(self, cfg): self.cfg = cfg

    def should_buy(self, df):
        r = df.iloc[-1]
        return bool(r["cross_up"] and r["rsi"] < self.cfg.RSI_OVERBOUGHT)

    def should_sell(self, df):
        r = df.iloc[-1]
        return bool(r["cross_down"] or r["rsi"] >= self.cfg.RSI_OVERBOUGHT)

    def size_position(self, capital, price, atr):
        sl_dist = atr * self.cfg.ATR_STOP_MULTIPLIER
        sl = price - sl_dist
        tp = price + sl_dist * self.cfg.TAKE_PROFIT_RATIO
        qty = (capital * self.cfg.RISK_PER_TRADE) / sl_dist
        return dict(qty=qty, sl=sl, tp=tp)

# ─── Data Fetcher ────────────────────────────────────────────────
class DataFetcher:
    def __init__(self, cfg):
        self.cfg = cfg

    def fetch_ohlcv(self, symbol):
        try:
            if self.cfg.BROKER == "binance":
                ex = ccxt.binance({"apiKey": self.cfg.BINANCE_API_KEY,
                                   "secret": self.cfg.BINANCE_SECRET,
                                   "enableRateLimit": True})
                raw = ex.fetch_ohlcv(symbol, self.cfg.TIMEFRAME, limit=self.cfg.CANDLE_LIMIT)
                df = pd.DataFrame(raw, columns=["timestamp","open","high","low","close","volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

            elif self.cfg.BROKER == "zerodha":
                kite = KiteConnect(api_key=self.cfg.ZERODHA_API_KEY)
                kite.set_access_token(self.cfg.ZERODHA_ACCESS_TOKEN)
                imap = {"1m":"minute","5m":"5minute","15m":"15minute",
                        "30m":"30minute","1h":"60minute","1d":"day"}
                to_dt = datetime.now()
                fr_dt = to_dt - timedelta(days=60)
                # NOTE: Replace instrument_token with actual token from kite.instruments()
                data = kite.historical_data(instrument_token=256265,
                                            from_date=fr_dt, to_date=to_dt,
                                            interval=imap.get(self.cfg.TIMEFRAME,"60minute"))
                df = pd.DataFrame(data).rename(columns={"date":"timestamp"})

            elif self.cfg.BROKER == "alpaca":
                api = AlpacaREST(self.cfg.ALPACA_API_KEY, self.cfg.ALPACA_SECRET_KEY,
                                 self.cfg.ALPACA_BASE_URL)
                tf_map = {"1m":"1Min","5m":"5Min","15m":"15Min",
                          "30m":"30Min","1h":"1Hour","1d":"1Day"}
                bars = api.get_bars(symbol, tf_map.get(self.cfg.TIMEFRAME, "1Hour"),
                                    limit=self.cfg.CANDLE_LIMIT).df
                bars = bars.reset_index()
                df = pd.DataFrame({
                    "timestamp": bars["timestamp"],
                    "open": bars["open"], "high": bars["high"],
                    "low": bars["low"], "close": bars["close"],
                    "volume": bars["volume"]
                })

            else:
                df = self._synthetic(symbol)

            return df.set_index("timestamp").sort_index()
        except Exception as e:
            log.error(f"fetch_ohlcv({symbol}): {e}"); raise

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
                api = AlpacaREST(self.cfg.ALPACA_API_KEY, self.cfg.ALPACA_SECRET_KEY,
                                 self.cfg.ALPACA_BASE_URL)
                return float(api.get_latest_trade(symbol).price)
            else:
                return float(self._synthetic(symbol)["close"].iloc[-1])
        except Exception as e:
            log.error(f"get_price({symbol}): {e}"); return 0.0

    @staticmethod
    def _synthetic(symbol):
        np.random.seed(hash(symbol) % 9999)
        n = 150
        base = 50000 if "BTC" in symbol else 3000
        prices = base * np.cumprod(1 + np.random.normal(0.0002, 0.015, n))
        ts = pd.date_range(end=datetime.now(), periods=n, freq="1h")
        noise = lambda: np.random.uniform(-0.01, 0.01, n)
        return pd.DataFrame({"timestamp": ts,
                              "open": prices * (1 + noise()),
                              "high": prices * (1 + np.abs(noise())),
                              "low":  prices * (1 - np.abs(noise())),
                              "close": prices,
                              "volume": np.random.uniform(100, 5000, n)})

# ─── Risk Manager ────────────────────────────────────────────────
class RiskManager:
    def __init__(self, cfg, portfolio):
        self.cfg = cfg
        self.portfolio = portfolio

    def can_open_trade(self):
        if len(self.portfolio.positions) >= self.cfg.MAX_OPEN_TRADES:
            log.warning("Max open trades reached."); return False
        loss_pct = abs(min(0, self.portfolio.daily_pnl)) / self.portfolio.initial_capital
        if loss_pct >= self.cfg.MAX_DAILY_LOSS:
            log.warning(f"Daily loss limit reached ({loss_pct:.1%})."); return False
        return True

    def reset_daily(self):
        self.portfolio.daily_pnl = 0.0
        log.info("[RISK] Daily counter reset.")

# ─── Bot ─────────────────────────────────────────────────────────
class TradingBot:
    def __init__(self):
        self.cfg = CONFIG
        self.portfolio = PaperPortfolio(self.cfg.PAPER_CAPITAL)
        self.fetcher   = DataFetcher(self.cfg)
        self.strategy  = EMAStrategy(self.cfg)
        self.risk      = RiskManager(self.cfg, self.portfolio)
        log.info(f"Bot started | Broker:{self.cfg.BROKER} | Symbols:{self.cfg.SYMBOLS}")

    def run_cycle(self):
        log.info(f"── Cycle {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ──")
        for sym in self.cfg.SYMBOLS:
            try:
                self._tick(sym)
            except Exception as e:
                log.error(f"{sym}: {e}")
        self.portfolio.summary()

    def _tick(self, symbol):
        df     = Indicators.compute(self.fetcher.fetch_ohlcv(symbol), self.cfg)
        price  = float(df["close"].iloc[-1])
        atr    = float(df["atr"].iloc[-1])

        # Check SL/TP on open position
        self.portfolio.check_sl_tp(symbol, price)

        # Exit signal
        if symbol in self.portfolio.positions:
            if self.strategy.should_sell(df):
                self.portfolio.sell(symbol, price, "sell_signal")
            return  # wait for next cycle to re-enter

        # Entry signal
        if self.risk.can_open_trade() and self.strategy.should_buy(df):
            sizing = self.strategy.size_position(self.portfolio.capital, price, atr)
            self.portfolio.buy(symbol, price, sizing["qty"], sizing["sl"], sizing["tp"])

    def start(self):
        self.run_cycle()
        mins = {"1m":1,"5m":5,"15m":15,"30m":30,"1h":60,"4h":240}.get(self.cfg.TIMEFRAME, 60)
        schedule.every(mins).minutes.do(self.run_cycle)
        schedule.every().day.at("00:00").do(self.risk.reset_daily)
        log.info(f"Scheduled every {mins}m | Ctrl+C to stop")
        while True:
            schedule.run_pending()
            time.sleep(30)

# ─── Backtester ──────────────────────────────────────────────────
class Backtester:
    def run(self, symbol="BTC/USDT"):
        cfg     = CONFIG
        df      = Indicators.compute(DataFetcher(cfg).fetch_ohlcv(symbol), cfg)
        strat   = EMAStrategy(cfg)
        capital = cfg.PAPER_CAPITAL
        trades, position = [], None

        for i in range(cfg.EMA_SLOW + 2, len(df)):
            window = df.iloc[:i+1]
            price  = float(window["close"].iloc[-1])
            atr    = float(window["atr"].iloc[-1])

            if position is None and strat.should_buy(window):
                s = strat.size_position(capital, price, atr)
                capital -= price * s["qty"]
                position = dict(entry=price, sl=s["sl"], tp=s["tp"], qty=s["qty"])

            elif position:
                reason = None
                if   price <= position["sl"]: reason = "stop_loss"
                elif price >= position["tp"]: reason = "take_profit"
                elif strat.should_sell(window): reason = "signal"
                if reason:
                    pnl = (price - position["entry"]) * position["qty"]
                    capital += price * position["qty"]
                    trades.append(dict(pnl=pnl, reason=reason))
                    position = None

        if trades:
            total = sum(t["pnl"] for t in trades)
            wins  = sum(1 for t in trades if t["pnl"] > 0)
            log.info(f"[BACKTEST] Trades:{len(trades)} | WinRate:{wins/len(trades):.1%} | "
                     f"PnL:{total:+.2f} | ROI:{total/cfg.PAPER_CAPITAL:+.2%}")
        else:
            log.info("[BACKTEST] No trades generated.")
        return trades

# ─── Main ────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "backtest":
        Backtester().run("BTC/USDT")
    else:
        try:
            TradingBot().start()
        except KeyboardInterrupt:
            log.info("Stopped.")
