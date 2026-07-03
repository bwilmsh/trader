# Strategy League Table — Learning Log

Generated: 2026-07-03 11:18 UTC
Source: backtest logs in `logs/` (real Binance OHLCV, event-driven engine)

Ranking: expectancy (R per trade) first, then R:R ratio. A strategy must pass the gate (expectancy > 0 AND R:R >= 1.5) to be a real contender.

| Rank | Strategy | Split | Trades | Win% | Avg Win R | Avg Loss R | R:R | Expectancy (R) | Profit Factor | Max DD% | Passes Gate |
|------|----------|-------|--------|------|-----------|------------|-----|-----------------|---------------|--------|-------------|
| 1 | ut | full | 1 | 100.0% | +1.74R | 0.00R | inf | +1.739R | inf | 0.0% | ✅ YES |
| 2 | macd | full | 33 | 42.4% | +1.54R | -0.89R | 1.74 | +0.143R | 1.26 | 4.0% | ✅ YES |
| 3 | ut | full | 275 | 33.8% | +1.35R | -0.80R | 1.70 | -0.070R | 0.87 | 25.2% | ✅ YES |
| 4 | supertrend | full | 55 | 36.4% | +0.93R | -0.67R | 1.39 | -0.087R | 0.79 | 7.2% | ✅ YES |
| 5 | supertrend | full | 261 | 33.7% | +1.19R | -0.77R | 1.55 | -0.109R | 0.78 | 27.7% | ✅ YES |
| 6 | rsi2 | full | 197 | 51.3% | +0.39R | -0.73R | 0.53 | -0.157R | 0.58 | 33.5% | ❌ NO |
| 7 | rsi2 | full | 519 | 36.8% | +0.26R | -0.55R | 0.47 | -0.255R | 0.28 | 73.7% | ❌ NO |
| 8 | ema | full | 244 | 31.1% | +1.14R | -1.00R | 1.14 | -0.331R | 0.52 | 56.9% | ✅ YES |

## Strategy details

### ut
- Trades: 1 (1W / 0L)
- Win rate: 100.0%
- R:R ratio: inf  (avg win +1.74R / avg loss 0.00R)
- Expectancy: +1.739R per trade
- Profit factor: inf
- Max drawdown: 0.0% ($0.00)
- Sharpe: 0.00
- Passes gate: True

### macd
- Trades: 33 (14W / 19L)
- Win rate: 42.4%
- R:R ratio: 1.74  (avg win +1.54R / avg loss -0.89R)
- Expectancy: +0.143R per trade
- Profit factor: 1.26
- Max drawdown: 4.0% ($43.15)
- Sharpe: 9.73
- Passes gate: True

### supertrend
- Trades: 55 (20W / 35L)
- Win rate: 36.4%
- R:R ratio: 1.39  (avg win +0.93R / avg loss -0.67R)
- Expectancy: -0.087R per trade
- Profit factor: 0.79
- Max drawdown: 7.2% ($73.58)
- Sharpe: -8.84
- Passes gate: False

### rsi2
- Trades: 197 (101W / 96L)
- Win rate: 51.3%
- R:R ratio: 0.53  (avg win +0.39R / avg loss -0.73R)
- Expectancy: -0.157R per trade
- Profit factor: 0.58
- Max drawdown: 33.5% ($361.22)
- Sharpe: -19.69
- Passes gate: False

### ema
- Trades: 244 (76W / 168L)
- Win rate: 31.1%
- R:R ratio: 1.14  (avg win +1.14R / avg loss -1.00R)
- Expectancy: -0.331R per trade
- Profit factor: 0.52
- Max drawdown: 56.9% ($571.37)
- Sharpe: -29.07
- Passes gate: False
