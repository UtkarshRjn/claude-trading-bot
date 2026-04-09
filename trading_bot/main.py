"""
====================================================================
  AUTOMATED TRADING BOT — Modular Strategy Framework
  Supports: Zerodha, Binance, Alpaca, Paper Trading
  Strategies: ema_rsi, multi_factor (switchable via STRATEGY env var)
====================================================================

SETUP:
  pip install kiteconnect ccxt pandas numpy schedule requests alpaca-trade-api python-dotenv

USAGE:
  python -m trading_bot              # live/paper trading
  python -m trading_bot backtest     # backtest current strategy
  python -m trading_bot compare      # compare all strategies
====================================================================
"""

import sys
import logging

from dotenv import load_dotenv
load_dotenv()

from trading_bot.config import Config
from trading_bot.bot import TradingBot
from trading_bot.backtester import Backtester

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("trading_bot.log"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)


def main():
    cfg = Config()

    if len(sys.argv) > 1 and sys.argv[1] == "backtest":
        bt = Backtester(cfg)
        # Per-stock analysis
        for symbol in cfg.SYMBOLS:
            bt.run(symbol)
        # Realistic portfolio backtest (chronological interleaving)
        log.info(f"\n{'='*50}")
        log.info("PORTFOLIO (all stocks interleaved)")
        log.info(f"{'='*50}")
        bt.run_portfolio(cfg.SYMBOLS)

    elif len(sys.argv) > 1 and sys.argv[1] == "pairs":
        bt = Backtester(cfg)
        # Use more stocks for better pair discovery
        symbols = cfg.SYMBOLS
        if len(sys.argv) > 2:
            symbols = sys.argv[2].split(",")
        bt.run_pairs(symbols)

    elif len(sys.argv) > 1 and sys.argv[1] == "compare":
        for strat_name in ["ema_rsi", "multi_factor"]:
            log.info(f"\n{'='*50}")
            log.info(f"Strategy: {strat_name}")
            log.info(f"{'='*50}")
            cfg_copy = Config()
            cfg_copy.STRATEGY = strat_name
            bt = Backtester(cfg_copy)
            bt.run_portfolio(cfg.SYMBOLS)
        # Also run pairs
        log.info(f"\n{'='*50}")
        log.info("Strategy: pairs")
        log.info(f"{'='*50}")
        bt = Backtester(cfg)
        bt.run_pairs(cfg.SYMBOLS)

    else:
        bot = TradingBot(cfg)
        try:
            bot.start()
        except KeyboardInterrupt:
            log.info("Stopped.")


if __name__ == "__main__":
    main()
