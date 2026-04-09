import logging
from datetime import datetime

log = logging.getLogger(__name__)


class PaperPortfolio:
    def __init__(self, capital):
        self.capital = capital
        self.initial_capital = capital
        self.positions = {}
        self.trade_log = []
        self.daily_pnl = 0.0

    def buy(self, symbol, price, qty, sl, tp):
        if price * qty > self.capital:
            log.warning(f"[PAPER] Insufficient capital to buy {symbol}")
            return False
        self.capital -= price * qty
        self.positions[symbol] = dict(
            qty=qty, entry=price, sl=sl, tp=tp,
            highest=price, trailing_active=False,
        )
        self.trade_log.append(dict(
            time=datetime.now(), symbol=symbol, action="BUY",
            price=price, qty=qty, sl=sl, tp=tp,
        ))
        log.info(
            f"[PAPER] BUY  {symbol} | Qty:{qty:.4f} @ {price:.2f} | "
            f"SL:{sl:.2f} | TP:{tp:.2f}"
        )
        return True

    def sell(self, symbol, price, reason="signal"):
        if symbol not in self.positions:
            return
        pos = self.positions.pop(symbol)
        pnl = (price - pos["entry"]) * pos["qty"]
        self.capital += price * pos["qty"]
        self.daily_pnl += pnl
        self.trade_log.append(dict(
            time=datetime.now(), symbol=symbol, action="SELL",
            price=price, pnl=pnl, reason=reason,
        ))
        log.info(
            f"[PAPER] SELL {symbol} | Price:{price:.2f} | "
            f"PnL:{pnl:+.2f} | Reason:{reason}"
        )

    def check_sl_tp(self, symbol, current_price, candle_high, candle_low, atr, cfg):
        """Check stop-loss / take-profit using candle high/low + trailing stop."""
        pos = self.positions.get(symbol)
        if not pos:
            return

        # Track highest price since entry
        if candle_high > pos["highest"]:
            pos["highest"] = candle_high

        profit_from_entry = pos["highest"] - pos["entry"]

        # Stage 1: Move SL to breakeven after TRAILING_BREAKEVEN_ATR profit
        if not pos["trailing_active"] and profit_from_entry >= atr * cfg.TRAILING_BREAKEVEN_ATR:
            pos["sl"] = pos["entry"]
            pos["trailing_active"] = True
            log.info(f"[TRAIL] {symbol} SL moved to breakeven @ {pos['sl']:.2f}")

        # Stage 2: Trail SL at TRAILING_ATR_MULTIPLIER below highest
        if pos["trailing_active"]:
            new_trail_sl = pos["highest"] - atr * cfg.TRAILING_ATR_MULTIPLIER
            if new_trail_sl > pos["sl"]:
                pos["sl"] = new_trail_sl

        # Check SL/TP using candle high/low
        if candle_low <= pos["sl"]:
            self.sell(symbol, pos["sl"], "stop_loss")
        elif candle_high >= pos["tp"]:
            self.sell(symbol, pos["tp"], "take_profit")

    def summary(self):
        roi = (self.capital - self.initial_capital) / self.initial_capital * 100
        log.info(
            f"[PORTFOLIO] Capital:{self.capital:.2f} | ROI:{roi:+.2f}% | "
            f"Open:{len(self.positions)} | DailyPnL:{self.daily_pnl:+.2f}"
        )
