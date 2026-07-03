# Trader — Learning Crypto Trading Bot

Research → Backtest → Paper Trade → Live Gate (OFF by default).

Strategies sourced from YouTube educators and TradingView Pine Scripts. Backtested on real Binance OHLCV data with risk-based position sizing, R:R gating, fees, and slippage. Paper trades live against real prices with no real money. Live trading is gated OFF — you flip it only after paper results prove a strategy.

## Quick Start

```bash
cd trader

# 1. Install dependencies
pip install -r requirements.txt

# 2. Run a backtest (tests a strategy on historical data)
python run_backtest.py strategies.supertrend --symbol BTC/USDT --timeframe 1d --since 2023-01-01T00:00:00Z

# 3. See all strategy results ranked
python learning_log.py

# 4. Start paper trading (live prices, no money)
python paper_trader.py strategies.macd_ema200 --symbol BTC/USDT --timeframe 4h --poll 900

# 5. Start the web dashboard
python web_app.py
# Then open http://localhost:8776
```

## What's in here

```
trader/
├── strategies/          # Trading strategies (each is a Python module)
│   ├── base.py          # Strategy/Signal/ExitSignal contract
│   ├── ema_cross.py     # EMA crossover (smoke test)
│   ├── ut_bot.py        # UT Bot Alerts — ATR trailing stop SAR
│   ├── supertrend.py    # Supertrend — ATR trend-following SAR
│   ├── macd_ema200.py   # MACD + 200 EMA trend filter
│   ├── rsi2_mr.py       # RSI(2) Connors mean reversion
│   └── wavetrend.py     # WaveTrend+ oscillator reversal
├── backtest/            # Backtesting engine
│   ├── engine.py        # Event-driven backtest with risk-based position sizing
│   └── metrics.py       # Win rate, R:R, expectancy, drawdown, Sharpe, profit factor
├── data/ppy
│   └── loader.py        # ccxt OHLCV fetcher with disk cache
├── config/
│   └── config.yaml      # All settings (live_trading: false by default)
├── research/
│   ├── strategy_research_report.md  # 12 strategies from YouTube/TradingView with sources
│   └── learning_log.md              # Strategy league table — ranked by expectancy
├── logs/ Prices (Binance via ccxt, cached on disk)
│   ├── *_BTCUSDT_*.json             # Backtest result logs
│   ├── paper_state_*.json          # Paper trader state (persists across restarts)
│   └── paper_log_*.jsonNC          # Paper trade logs
├── run_backtest.py Total  # CLI — run any strategy on any symbol/timeframe
├── paper_trader.pyIA via ccxt  # Live paper trading loop (polls exchange, logs virtual trades)
├── learning_log.py                 # Aggregates all backtests into ranked league table
├── param_sweep.pyyment  # Parameter grid search (finds optimal strategy params)
├── web_app.pyL真人     # Web dashboard server (port 8776)
└── requirements.txtRUE       # Dependencies
```

## Strategies that pass the gate (positive expectancy + R:R ≥ 1.5)

| Strategy | Timeframe | Expectancy | Win% | R:R | Max DD |
|---|---|---|---|---|---|
| Supertrend | 1d | +0.146R | 47% | 1.54 | 3.7% |
| MACD+200EMA | 4h | +0.143R | 42% | 1.74 | 4.0% |
| WaveTrend (tuned) | 4h | +0.055R | 38% | 1.94 | 3.9% |

All three are paper trading live. Results in `research/learning_log.md`.

## Key Commands

```bash
# Backtest any strategy
python run_backtest.py strategies.<name> --symbol BTC/USDT --timeframe 4h --since 2024-01-01

# Backtest with custom params
python run_backtest.py strategies.wavetrend --timeframe 4h --params '{"oversold": -50, "stop_atr": 2.0}'

# Walk-forward test (70% train, 30% test)
python run_backtest.py strategies.macd_ema200 --timeframe 4h --walk-forward

# Parameter sweep (grid search)
python param_sweep.py strategies.wavetrend --timeframe 4h --params-grid '{"oversold": [-60,-50,-40], "stop_atr": [2,3]}'

# Paper trade (live, no money)
python paper_trader.py strategies.supertrend --symbol BTC/USDT --timeframe 1d --poll 1800

# Web dashboard
python web_app.py

# Regenerate the league table
python learning_log.py
```

## Risk Management (built into the engine)

- **1% risk per trade** — position size calculated from stop distance, not fixed quantity
- **R:R gate ≥ 1.5** — trades with risk:reward below 1.5 are rejected automatically
- **Fees + slippage** — 0.1% taker fee + 0.05% slippage simulated on every trade
- **Live gate OFF** — `config/config.yaml` has `live_trading: false` by default
- When enabled: max $50/position, $25 daily loss limit, 3 max open trades

## Data

All historical data pulled from Binance via ccxt, cached on disk in `data/cache/`. No API key needed for public OHLCV data.
