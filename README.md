# Claude Trading Bot

Automated trading bot for Indian markets (NSE/BSE) and Crypto, built with Python.

## Strategy

**EMA Crossover + RSI Filter** with ATR-based risk management:

- **BUY** when fast EMA (9) crosses above slow EMA (21) and RSI < 70
- **SELL** when fast EMA crosses below slow EMA or RSI ≥ 70
- **Stop Loss** at 2× ATR below entry price
- **Take Profit** at 2:1 risk-reward ratio

## Risk Management

- Max 1% of capital risked per trade
- Max 3 concurrent open positions
- Trading halts if daily loss exceeds 5%
- Daily PnL resets at midnight

## Supported Brokers

| Mode | Use Case |
|---|---|
| `paper` | Virtual trading with synthetic data — good for testing |
| `binance` | Live crypto trading via Binance API (24/7) |
| `zerodha` | Live NSE/BSE trading via KiteConnect API |

## Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install ccxt kiteconnect pandas numpy schedule requests python-dotenv

# Copy and fill in your credentials
cp .env.example .env
```

## Usage

```bash
# Paper trade (test mode)
python trading_bot.py

# Backtest on historical data
python trading_bot.py backtest
```

## Configuration

Set your broker credentials in `.env`:

```env
BROKER=paper                    # paper | binance | zerodha

# Zerodha (NSE/BSE)
ZERODHA_API_KEY=
ZERODHA_API_SECRET=
ZERODHA_ACCESS_TOKEN=

# Binance (Crypto)
BINANCE_API_KEY=
BINANCE_SECRET=
```

## Hosting 24/7

| Platform | Cost | Notes |
|---|---|---|
| AWS EC2 (t3.micro) | ~₹600/mo | Free tier 1 year |
| Google Cloud (e2-micro) | Free tier | Always-free tier available |
| DigitalOcean | ~₹840/mo | Simple, reliable |
| Hetzner VPS | ~₹350/mo | Best value |

```bash
# Run in background
nohup python trading_bot.py &
```

## Disclaimer

Always backtest thoroughly and start with paper trading. Algo trading carries real financial risk. SEBI regulations require registered brokers for Indian market algo trading — use platforms like Zerodha, Angel One, or Upstox with their official APIs.
