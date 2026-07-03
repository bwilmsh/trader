# Strategy League Table — Learning Log

Generated: 2026-07-03 11:30 UTC
Source: backtest logs in `logs/` (real Binance OHLCV, event-driven engine)

Ranking: expectancy (R per trade) first, then R:R ratio. A strategy must pass the gate (expectancy > 0 AND R:R >= 1.5) to be a real contender.

| Rank | Strategy | Split | Trades | Win% | Avg Win R | Avg Loss R | R:R | Expectancy (R) | Profit Factor | Max DD% | Passes Gate |
|------|----------|-------|--------|------|-----------|------------|-----|-----------------|---------------|--------|-------------|
| 1 | supertrend | full | 17 | 47.1% | +1.16R | -0.75R | 1.54 | +0.146R | 1.34 | 3.7% | ✅ YES |
| 2 | macd | full | 33 | 42.4% | +1.54R | -0.89R | 1.74 | +0.143R | 1.26 | 4.0% | ✅ YES |
| 3 | wavetrend | full | 63 | 38.1% | +0.90R | -0.47R | 1.94 | +0.055R | 1.18 | 3.9% | ✅ YES |
| 4 | wavetrend | full | 32 | 34.4% | +0.89R | -0.48R | 1.86 | -0.008R | 0.96 | 5.0% | ❌ NO |
| 5 | ut | full | 275 | 33.8% | +1.35R | -0.80R | 1.70 | -0.070R | 0.87 | 25.2% | ✅ YES |
| 6 | supertrend | full | 55 | 36.4% | +0.93R | -0.67R | 1.39 | -0.087R | 0.79 | 7.2% | ✅ YES |
| 7 | supertrend | full | 261 | 33.7% | +1.19R | -0.77R | 1.55 | -0.109R | 0.78 | 27.7% | ✅ YES |
| 8 | macd | full | 11 | 36.4% | +1.07R | -0.80R | 1.34 | -0.119R | 0.76 | 2.3% | ❌ NO |
| 9 | wavetrend | full | 136 | 36.0% | +1.00R | -0.77R | 1.29 | -0.134R | 0.72 | 17.8% | ❌ NO |
| 10 | rsi2 | full | 197 | 51.3% | +0.39R | -0.73R | 0.53 | -0.157R | 0.58 | 33.5% | ❌ NO |
| 11 | rsi2 | full | 519 | 36.8% | +0.26R | -0.55R | 0.47 | -0.255R | 0.28 | 73.7% | ❌ NO |
| 12 | ema | full | 244 | 31.1% | +1.14R | -1.00R | 1.14 | -0.331R | 0.52 | 56.9% | ✅ YES |

## Strategy details

### supertrend
- Trades: 17 (8W / 9L)
- Win rate: 47.1%
- R:R ratio: 1.54  (avg win +1.16R / avg loss -0.75R)
- Expectancy: +0.146R per trade
- Profit factor: 1.34
- Max drawdown: 3.7% ($38.89)
- Sharpe: 11.50
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

### wavetrend
- Trades: 63 (24W / 39L)
- Win rate: 38.1%
- R:R ratio: 1.94  (avg win +0.90R / avg loss -0.47R)
- Expectancy: +0.055R per trade
- Profit factor: 1.18
- Max drawdown: 3.9% ($40.28)
- Sharpe: 5.72
- Passes gate: True

### ut
- Trades: 275 (93W / 182L)
- Win rate: 33.8%
- R:R ratio: 1.70  (avg win +1.35R / avg loss -0.80R)
- Expectancy: -0.070R per trade
- Profit factor: 0.87
- Max drawdown: 25.2% ($268.95)
- Sharpe: -5.86
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
