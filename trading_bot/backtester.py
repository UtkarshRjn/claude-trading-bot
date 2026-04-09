import logging
import numpy as np
import pandas as pd

from trading_bot.indicators import Indicators
from trading_bot.data_fetcher import DataFetcher
from trading_bot.strategies import get_strategy

log = logging.getLogger(__name__)

SLIPPAGE_PCT = 0.001  # 0.1% slippage per trade (entry + exit)


class Backtester:
    def __init__(self, cfg):
        self.cfg = cfg

    def run(self, symbol, start="2025-04-09", end="2026-04-09"):
        """Single-stock backtest (for per-stock analysis)."""
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
                entry_price = price * (1 + SLIPPAGE_PCT)  # slippage on entry
                s = strat.size_position(capital, entry_price, atr)
                if s["qty"] <= 0:
                    continue
                capital -= entry_price * s["qty"]
                position = dict(
                    entry=entry_price, sl=s["sl"], tp=s["tp"], qty=s["qty"],
                    highest=entry_price, trailing_active=False,
                )

            elif position:
                if high > position["highest"]:
                    position["highest"] = high

                profit_from_entry = position["highest"] - position["entry"]
                if not position["trailing_active"] and profit_from_entry >= atr * cfg.TRAILING_BREAKEVEN_ATR:
                    position["sl"] = position["entry"]
                    position["trailing_active"] = True
                if position["trailing_active"]:
                    new_trail = position["highest"] - atr * cfg.TRAILING_ATR_MULTIPLIER
                    if new_trail > position["sl"]:
                        position["sl"] = new_trail

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
                    exit_price *= (1 - SLIPPAGE_PCT)  # slippage on exit
                    pnl = (exit_price - position["entry"]) * position["qty"]
                    capital += exit_price * position["qty"]
                    trades.append(dict(pnl=pnl, reason=reason))
                    position = None

            port_value = capital
            if position:
                port_value += price * position["qty"]
            equity_curve.append(port_value)

        if position:
            price = float(df["close"].iloc[-1]) * (1 - SLIPPAGE_PCT)
            pnl = (price - position["entry"]) * position["qty"]
            capital += price * position["qty"]
            trades.append(dict(pnl=pnl, reason="end_of_period"))
            equity_curve.append(capital)
            position = None

        self._print_metrics(symbol, trades, equity_curve, cfg)
        return trades

    def run_portfolio(self, symbols, start="2025-04-09", end="2026-04-09"):
        """
        Multi-stock backtest with chronological interleaving.
        Processes all stocks at each timestamp before moving to the next.
        This is the realistic simulation.
        """
        cfg = self.cfg
        fetcher = DataFetcher(cfg)
        strat = get_strategy(cfg.STRATEGY, cfg)
        capital = cfg.PAPER_CAPITAL
        positions = {}  # symbol -> position dict
        trades = []
        equity_curve = [capital]

        warmup = max(cfg.EMA_SLOW, cfg.ADX_PERIOD * 2, cfg.MACD_SLOW) + 2

        # Load and compute indicators for all stocks
        stock_data = {}
        for symbol in symbols:
            if cfg.BROKER in ("alpaca",):
                raw_df = fetcher.fetch_ohlcv_range(symbol, start, end)
            else:
                raw_df = fetcher.fetch_ohlcv(symbol)
            stock_data[symbol] = Indicators.compute(raw_df, cfg)

        # Build unified timeline from all stocks
        all_timestamps = sorted(set().union(
            *(df.index.tolist() for df in stock_data.values())
        ))

        for ts in all_timestamps:
            # Check SL/TP and exits for open positions first
            for symbol in list(positions.keys()):
                df = stock_data[symbol]
                if ts not in df.index:
                    continue
                idx = df.index.get_loc(ts)
                if idx < warmup:
                    continue

                window = df.iloc[: idx + 1]
                row = df.iloc[idx]
                price = float(row["close"])
                high = float(row["high"])
                low = float(row["low"])
                atr = float(row["atr"])
                pos = positions[symbol]

                if high > pos["highest"]:
                    pos["highest"] = high

                profit = pos["highest"] - pos["entry"]
                if not pos["trailing_active"] and profit >= atr * cfg.TRAILING_BREAKEVEN_ATR:
                    pos["sl"] = pos["entry"]
                    pos["trailing_active"] = True
                if pos["trailing_active"]:
                    new_trail = pos["highest"] - atr * cfg.TRAILING_ATR_MULTIPLIER
                    if new_trail > pos["sl"]:
                        pos["sl"] = new_trail

                reason = None
                exit_price = price
                if low <= pos["sl"]:
                    reason = "stop_loss"
                    exit_price = pos["sl"]
                elif high >= pos["tp"]:
                    reason = "take_profit"
                    exit_price = pos["tp"]
                elif strat.should_sell(window):
                    reason = "signal"
                    exit_price = price

                if reason:
                    exit_price *= (1 - SLIPPAGE_PCT)
                    pnl = (exit_price - pos["entry"]) * pos["qty"]
                    capital += exit_price * pos["qty"]
                    trades.append(dict(pnl=pnl, reason=reason, symbol=symbol, time=ts))
                    del positions[symbol]

            # Check entries (only if we have room for more positions)
            if len(positions) < cfg.MAX_OPEN_TRADES:
                for symbol in symbols:
                    if symbol in positions:
                        continue
                    if len(positions) >= cfg.MAX_OPEN_TRADES:
                        break
                    df = stock_data[symbol]
                    if ts not in df.index:
                        continue
                    idx = df.index.get_loc(ts)
                    if idx < warmup:
                        continue

                    window = df.iloc[: idx + 1]
                    row = df.iloc[idx]
                    price = float(row["close"])
                    atr = float(row["atr"])

                    if strat.should_buy(window):
                        entry_price = price * (1 + SLIPPAGE_PCT)
                        s = strat.size_position(capital, entry_price, atr)
                        if s["qty"] <= 0:
                            continue
                        capital -= entry_price * s["qty"]
                        positions[symbol] = dict(
                            entry=entry_price, sl=s["sl"], tp=s["tp"], qty=s["qty"],
                            highest=entry_price, trailing_active=False,
                        )

            # Track portfolio value
            port_value = capital
            for sym, pos in positions.items():
                df = stock_data[sym]
                if ts in df.index:
                    port_value += float(df.loc[ts, "close"]) * pos["qty"]
            equity_curve.append(port_value)

        # Close remaining positions
        for symbol, pos in list(positions.items()):
            price = float(stock_data[symbol]["close"].iloc[-1]) * (1 - SLIPPAGE_PCT)
            pnl = (price - pos["entry"]) * pos["qty"]
            capital += price * pos["qty"]
            trades.append(dict(pnl=pnl, reason="end_of_period", symbol=symbol))
        positions.clear()

        self._print_metrics("PORTFOLIO", trades, equity_curve, cfg)
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

        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        returns = pd.Series(pnls) / cfg.PAPER_CAPITAL
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0

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
        log.info(f"  (includes {SLIPPAGE_PCT*100:.1f}% slippage per trade)")
