# Claude Trading Bot

Automated trading bot with modular strategies for US stocks, Indian markets (NSE/BSE), and Crypto.

## Strategies

Switch strategies via `STRATEGY=` in `.env`:

### `ema_rsi` — EMA Crossover + RSI Filter
- **BUY** when EMA(9) crosses above EMA(21) and RSI < 70
- **SELL** when EMA crosses down or RSI >= 70
- Backtested: **+10.3% annual ROI**, 64.5% win rate (166 trades)

### `multi_factor` — VWAP + MACD + RSI + ADX + Volume
- **BUY** when all 6 conditions align (EMA cross, price > VWAP, MACD confirmation, ADX > 20, RSI 30-65, volume above average)
- **SELL** when EMA crosses down or RSI > 75
- More selective, lower drawdowns, best on low-volatility stocks

See [BACKTEST_REPORT.md](BACKTEST_REPORT.md) for full results.

## Risk Management

- Max 1% of capital risked per trade
- Max 33% of capital in a single position
- Max 3 concurrent open positions
- Chandelier trailing stop (breakeven at 1.5x ATR, trail at 1.5x ATR)
- Trading halts if daily loss exceeds 5%

## Supported Brokers

| Mode | Use Case |
|---|---|
| `paper` | Virtual trading with synthetic data |
| `alpaca` | US stocks via Alpaca API (free) |
| `binance` | Crypto trading via Binance API (24/7) |
| `zerodha` | NSE/BSE trading via KiteConnect API |

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install ccxt kiteconnect pandas numpy schedule requests python-dotenv alpaca-trade-api
cp .env.example .env   # fill in your credentials
```

## Usage

```bash
# Live/paper trading
python -m trading_bot

# Backtest current strategy
python -m trading_bot backtest

# Compare all strategies side by side
python -m trading_bot compare
```

## Configuration

Set credentials and strategy in `.env`:

```env
BROKER=alpaca                   # paper | alpaca | binance | zerodha
STRATEGY=multi_factor           # multi_factor | ema_rsi

ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=https://paper-api.alpaca.markets/v2
```

## Project Structure

```
trading_bot/
├── main.py              # Entry point
├── config.py            # Configuration
├── indicators.py        # Technical indicators (EMA, RSI, ATR, MACD, ADX, VWAP)
├── portfolio.py         # Paper portfolio with trailing stops
├── risk.py              # Risk manager
├── data_fetcher.py      # Multi-broker data fetching
├── backtester.py        # Backtester with Sharpe, drawdown, profit factor
├── bot.py               # Trading engine
└── strategies/
    ├── base.py          # Base strategy class
    ├── ema_rsi.py       # EMA + RSI strategy
    └── multi_factor.py  # VWAP + MACD + RSI + ADX + Volume strategy
```

## Disclaimer

Always backtest thoroughly and start with paper trading. Algo trading carries real financial risk. SEBI regulations require registered brokers for Indian market algo trading.
