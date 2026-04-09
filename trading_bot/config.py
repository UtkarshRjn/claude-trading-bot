import os
from dataclasses import dataclass, field


@dataclass
class Config:
    BROKER: str = field(default_factory=lambda: os.getenv("BROKER", "paper"))
    STRATEGY: str = field(default_factory=lambda: os.getenv("STRATEGY", "multi_factor"))

    # Zerodha KiteConnect
    ZERODHA_API_KEY: str = field(default_factory=lambda: os.getenv("ZERODHA_API_KEY", ""))
    ZERODHA_API_SECRET: str = field(default_factory=lambda: os.getenv("ZERODHA_API_SECRET", ""))
    ZERODHA_ACCESS_TOKEN: str = field(default_factory=lambda: os.getenv("ZERODHA_ACCESS_TOKEN", ""))

    # Binance
    BINANCE_API_KEY: str = field(default_factory=lambda: os.getenv("BINANCE_API_KEY", ""))
    BINANCE_SECRET: str = field(default_factory=lambda: os.getenv("BINANCE_SECRET", ""))

    # Alpaca (US Stocks)
    ALPACA_API_KEY: str = field(default_factory=lambda: os.getenv("ALPACA_API_KEY", ""))
    ALPACA_SECRET_KEY: str = field(default_factory=lambda: os.getenv("ALPACA_SECRET_KEY", ""))
    ALPACA_BASE_URL: str = field(default_factory=lambda: os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2"))

    # Symbols
    SYMBOLS: list = field(default_factory=lambda: ["AAPL", "GOOGL", "MSFT", "NVDA", "AMZN"])

    # --- EMA ---
    EMA_FAST: int = 9
    EMA_SLOW: int = 21

    # --- RSI ---
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: float = 70       # used by ema_rsi strategy
    RSI_OVERSOLD: float = 30
    RSI_ENTRY_LOW: float = 30.0      # used by multi_factor strategy
    RSI_ENTRY_HIGH: float = 65.0
    RSI_EXIT: float = 75.0

    # --- ATR ---
    ATR_PERIOD: int = 14

    # --- ADX ---
    ADX_PERIOD: int = 14
    ADX_THRESHOLD: float = 20.0

    # --- MACD ---
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9

    # --- Volume ---
    VOLUME_MA_PERIOD: int = 20

    # --- Risk ---
    RISK_PER_TRADE: float = 0.01
    ATR_STOP_MULTIPLIER: float = 2.5
    TAKE_PROFIT_RATIO: float = 3.0
    MAX_OPEN_TRADES: int = 2
    MAX_DAILY_LOSS: float = 0.05
    MAX_POSITION_PCT: float = 0.25

    # --- Trailing Stop ---
    TRAILING_BREAKEVEN_ATR: float = 1.5
    TRAILING_ATR_MULTIPLIER: float = 1.5

    # --- Pairs Trading ---
    PAIRS_ENTRY_Z: float = 2.0       # open pair when |z| > 2.0
    PAIRS_EXIT_Z: float = 0.5        # close pair when |z| < 0.5 (near mean)
    PAIRS_STOP_Z: float = 4.0        # stop loss when |z| > 4.0 (blowout)
    PAIRS_LOOKBACK: int = 60         # rolling window for z-score
    PAIRS_COINT_LOOKBACK: int = 252  # lookback for cointegration test

    TIMEFRAME: str = "1h"
    CANDLE_LIMIT: int = 200

    PAPER_CAPITAL: float = 10000.0
