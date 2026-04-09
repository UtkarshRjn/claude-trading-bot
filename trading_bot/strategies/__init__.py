from trading_bot.strategies.base import BaseStrategy
from trading_bot.strategies.ema_rsi import EmaRsiStrategy
from trading_bot.strategies.multi_factor import MultiFactorStrategy

STRATEGIES = {
    "ema_rsi": EmaRsiStrategy,
    "multi_factor": MultiFactorStrategy,
}


def get_strategy(name, cfg) -> BaseStrategy:
    if name not in STRATEGIES:
        raise ValueError(f"Unknown strategy '{name}'. Available: {list(STRATEGIES.keys())}")
    return STRATEGIES[name](cfg)
