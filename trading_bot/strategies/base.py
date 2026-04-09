class BaseStrategy:
    """Base class for all trading strategies."""

    def __init__(self, cfg):
        self.cfg = cfg

    def should_buy(self, df) -> bool:
        raise NotImplementedError

    def should_sell(self, df) -> bool:
        raise NotImplementedError

    def size_position(self, capital, price, atr) -> dict:
        """ATR-based position sizing with notional cap."""
        if capital <= 0 or price <= 0 or atr <= 0:
            return dict(qty=0, sl=0, tp=0)
        sl_dist = atr * self.cfg.ATR_STOP_MULTIPLIER
        sl = price - sl_dist
        tp = price + sl_dist * self.cfg.TAKE_PROFIT_RATIO
        risk_amount = capital * self.cfg.RISK_PER_TRADE
        qty = risk_amount / sl_dist
        # Cap notional at MAX_POSITION_PCT of capital, and never exceed available capital
        max_qty = (capital * self.cfg.MAX_POSITION_PCT) / price
        affordable_qty = capital * 0.95 / price  # keep 5% cash buffer
        qty = min(qty, max_qty, affordable_qty)
        if qty <= 0:
            return dict(qty=0, sl=0, tp=0)
        return dict(qty=qty, sl=sl, tp=tp)
