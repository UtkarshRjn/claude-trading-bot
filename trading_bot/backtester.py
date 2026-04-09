import logging
import numpy as np
import pandas as pd

from trading_bot.indicators import Indicators
from trading_bot.data_fetcher import DataFetcher
from trading_bot.strategies import get_strategy

log = logging.getLogger(__name__)


class Backtester:
    def __init__(self, cfg):
        self.cfg = cfg

    def run(self, symbol, start="2025-04-09", end="2026-04-09"):
        cfg = self.cfg
        fetcher = DataFetcher(cfg)
        if cfg.BROKER in ("alpaca",):
            raw_df = fetcher.fetch_ohlcv_range(symbol, start, end)
        else:
            raw_df = fetcher.fetch_ohlcv(symbol)
        df = Indicators.compute(raw_df, cfg)
        strat = get_strategy(cfg.STRATEGY, cfg)
        capital = cfg.PAPER_CAPITAL
        trades, position = [], None
        equity_curve = [capital]

        warmup = max(cfg.EMA_SLOW, cfg.ADX_PERIOD * 2, cfg.MACD_SLOW) + 2

        for i in range(warmup, len(df)):
            window = df.iloc[: i + 1]
            row = df.iloc[i]
            price = float(row["close"])
            high = float(row["high"])
            low = float(row["low"])
            atr = float(row["atr"])

            if position is None and strat.should_buy(window):
                s = strat.size_position(capital, price, atr)
                if s["qty"] <= 0:
                    continue
                capital -= price * s["qty"]
                position = dict(
                    entry=price, sl=s["sl"], tp=s["tp"], qty=s["qty"],
                    highest=price, trailing_active=False,
                )

            elif position:
                # Track highest
                if high > position["highest"]:
                    position["highest"] = high

                # Trailing stop logic
                profit_from_entry = position["highest"] - position["entry"]
                if not position["trailing_active"] and profit_from_entry >= atr * cfg.TRAILING_BREAKEVEN_ATR:
                    position["sl"] = position["entry"]
                    position["trailing_active"] = True
                if position["trailing_active"]:
                    new_trail = position["highest"] - atr * cfg.TRAILING_ATR_MULTIPLIER
                    if new_trail > position["sl"]:
                        position["sl"] = new_trail

                # Check SL/TP using high/low
                reason = None
                exit_price = price
                if low <= position["sl"]:
                    reason = "stop_loss"
                    exit_price = position["sl"]
                elif high >= position["tp"]:
                    reason = "take_profit"
                    exit_price = position["tp"]
                elif strat.should_sell(window):
                    reason = "signal"
                    exit_price = price

                if reason:
                    pnl = (exit_price - position["entry"]) * position["qty"]
                    capital += exit_price * position["qty"]
                    trades.append(dict(pnl=pnl, reason=reason))
                    position = None

            # Track total portfolio value (cash + open position value)
            port_value = capital
            if position:
                port_value += price * position["qty"]
            equity_curve.append(port_value)

        # Close any open position at end
        if position:
            price = float(df["close"].iloc[-1])
            pnl = (price - position["entry"]) * position["qty"]
            capital += price * position["qty"]
            trades.append(dict(pnl=pnl, reason="end_of_period"))
            equity_curve.append(capital)
            position = None

        self._print_metrics(symbol, trades, equity_curve, cfg)
        return trades

    def _print_metrics(self, symbol, trades, equity_curve, cfg):
        if not trades:
            log.info(f"[BACKTEST] {symbol}: No trades generated.")
            return

        pnls = [t["pnl"] for t in trades]
        total_pnl = sum(pnls)
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        win_rate = len(wins) / len(pnls)

        # Profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Sharpe ratio (per-trade, annualized approx)
        returns = pd.Series(pnls) / cfg.PAPER_CAPITAL
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0

        # Max drawdown
        equity = pd.Series(equity_curve)
        rolling_max = equity.cummax()
        drawdown = (equity - rolling_max) / rolling_max
        max_dd = drawdown.min()

        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0

        sl_count = sum(1 for t in trades if t["reason"] == "stop_loss")
        tp_count = sum(1 for t in trades if t["reason"] == "take_profit")
        sig_count = sum(1 for t in trades if t["reason"] == "signal")

        log.info(f"[BACKTEST] === {symbol} ({cfg.STRATEGY}) ===")
        log.info(f"  Trades: {len(trades)} | Win Rate: {win_rate:.1%}")
        log.info(f"  PnL: ${total_pnl:+.2f} | ROI: {total_pnl / cfg.PAPER_CAPITAL:+.2%}")
        log.info(f"  Profit Factor: {profit_factor:.2f} | Sharpe: {sharpe:.2f}")
        log.info(f"  Max Drawdown: {max_dd:.2%}")
        log.info(f"  Avg Win: ${avg_win:+.2f} | Avg Loss: ${avg_loss:+.2f}")
        log.info(f"  Exits — Signal:{sig_count} | SL:{sl_count} | TP:{tp_count}")
