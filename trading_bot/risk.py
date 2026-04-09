import logging

log = logging.getLogger(__name__)


class RiskManager:
    def __init__(self, cfg, portfolio):
        self.cfg = cfg
        self.portfolio = portfolio

    def can_open_trade(self):
        if len(self.portfolio.positions) >= self.cfg.MAX_OPEN_TRADES:
            log.warning("Max open trades reached.")
            return False
        loss_pct = abs(min(0, self.portfolio.daily_pnl)) / self.portfolio.initial_capital
        if loss_pct >= self.cfg.MAX_DAILY_LOSS:
            log.warning(f"Daily loss limit reached ({loss_pct:.1%}).")
            return False
        return True

    def reset_daily(self):
        self.portfolio.daily_pnl = 0.0
        log.info("[RISK] Daily counter reset.")
