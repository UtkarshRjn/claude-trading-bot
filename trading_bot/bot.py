import logging
import time

import schedule

from trading_bot.indicators import Indicators
from trading_bot.data_fetcher import DataFetcher
from trading_bot.portfolio import PaperPortfolio
from trading_bot.risk import RiskManager
from trading_bot.strategies import get_strategy

log = logging.getLogger(__name__)


class TradingBot:
    def __init__(self, cfg):
        self.cfg = cfg
        self.portfolio = PaperPortfolio(cfg.PAPER_CAPITAL)
        self.fetcher = DataFetcher(cfg)
        self.strategy = get_strategy(cfg.STRATEGY, cfg)
        self.risk = RiskManager(cfg, self.portfolio)
        log.info(
            f"Bot started | Broker:{cfg.BROKER} | Strategy:{cfg.STRATEGY} | "
            f"Symbols:{cfg.SYMBOLS}"
        )

    def run_cycle(self):
        from datetime import datetime
        log.info(f"── Cycle {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ──")
        for sym in self.cfg.SYMBOLS:
            try:
                self._tick(sym)
            except Exception as e:
                log.error(f"{sym}: {e}")
        self.portfolio.summary()

    def _tick(self, symbol):
        df = Indicators.compute(self.fetcher.fetch_ohlcv(symbol), self.cfg)
        price = float(df["close"].iloc[-1])
        atr = float(df["atr"].iloc[-1])
        candle_high = float(df["high"].iloc[-1])
        candle_low = float(df["low"].iloc[-1])

        # Check SL/TP with trailing stop
        self.portfolio.check_sl_tp(symbol, price, candle_high, candle_low, atr, self.cfg)

        # Exit signal
        if symbol in self.portfolio.positions:
            if self.strategy.should_sell(df):
                self.portfolio.sell(symbol, price, "sell_signal")
            return

        # Entry signal
        if self.risk.can_open_trade() and self.strategy.should_buy(df):
            sizing = self.strategy.size_position(self.portfolio.capital, price, atr)
            self.portfolio.buy(symbol, price, sizing["qty"], sizing["sl"], sizing["tp"])

    def start(self):
        self.run_cycle()
        mins = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240}.get(
            self.cfg.TIMEFRAME, 60
        )
        schedule.every(mins).minutes.do(self.run_cycle)
        schedule.every().day.at("00:00").do(self.risk.reset_daily)
        log.info(f"Scheduled every {mins}m | Ctrl+C to stop")
        while True:
            schedule.run_pending()
            time.sleep(30)
