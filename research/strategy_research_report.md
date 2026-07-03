# Crypto Trading Strategy Research Report

**Goal:** Find crypto trading strategies with clear, testable, mechanical rules for a Python backtesting bot using ccxt (Binance/Bybit) OHLCV data. Timeframe: 1h–1d. Prioritize defined R:R ratios and stop losses.

---

## Top 5 Strategies (ranked by testability + risk management fit)

### 1. UT Bot Alerts (ATR Trailing Stop) — testability 5/5
- **Source:** TradingView Pine Script "UT Bot Alerts" by QuantNomad (https://www.tradingview.com/script/n8ss8BID-UT-Bot-Alerts/). Also covered in Medium "I Found 5 Highly Shared Pine Script Strategies" (betashorts1998, April 2026) and YouTube "66% Win Rate!? UT Bot Alerts TradingView Strategy Tested on Crypto!" (Jan 2025).
- **Timeframe:** 1h–1d (commonly 4h for crypto).
- **Indicators:** ATR (default period 10), optional Heikin-Ashi smoothing.
- **Entry (long):** Close crosses above ATR trailing stop (`nRes = close - keyvalue × ATR`). Default `keyvalue=3`, `atr_period=10`.
- **Entry (short):** Close crosses below trailing stop.
- **Exit:** SAR system — exit long when close crosses below trailing stop.
- **Stop:** The trailing stop IS the stop. Initial stop ≈ entry − (keyvalue × ATR). Ratchets upward.
- **R:R:** Variable (trend-following SAR). Source claims win/loss ratio stretches above 3.0 in trending markets.
- **Claimed (unverified):** ~60–66% win rate on major crypto pairs. Caveat: whipsaws badly in choppy/range-bound BTC markets (279 trades, mostly stopped out quickly in 2025 chop).
- **Why #1:** Fully mechanical. ~30 lines of Python. Defined stop. Always-in-market SAR simplifies logic.

### 2. Supertrend Basic (ATR Trend Following) — testability 5/5
- **Source:** TradingView "Stella's SuperTrend Basic" by StellaEntry (https://www.tradingview.com/script/c7l4zdiN-Stella-s-SuperTrend-Basic/). FXOpen article, goodcrypto.app guide. TradeSearcher ran 148 backtests on a supertrend variant. PickMyTrade blog claims "SuperTrend and WaveTrend excel, 70% win rates on BTC" (April 2026, unverified vendor claim).
- **Timeframe:** 1h–1d. Stella's variant explicitly optimized for crypto (BTC, SOL).
- **Indicators:** ATR, Supertrend (built from ATR + multiplier).
- **Entry (long):** Close crosses above Supertrend line (flips green). Defaults: `atr_period=10`, `multiplier=3`.
- **Entry (short):** Close crosses below Supertrend line.
- **Exit:** SAR — exit long when Supertrend flips down. Stella's variant adds optional % take-profit.
- **Stop:** Supertrend line acts as trailing stop. Initial stop = entry − (multiplier × ATR). Stella adds separate built-in % stop loss as backstop.
- **R:R:** Variable (trend-following SAR). Can layer fixed R:R by adding TP at N×ATR.
- **Why #2:** Near-identical math to UT Bot. Stella's crypto optimization + optional % stop/TP layer fits risk-managed philosophy better than pure SAR.

### 3. MACD + 200 EMA Trend Filter — testability 5/5
- **Source:** YouTube "200 EMA + MACD Trading Strategy Tested 100 Times" (https://www.youtube.com/watch?v=kr_kGf7fENI). TradingView Pine Script description: "MACD strategy combine with a 200 EMA — Buy when price above 200 EMA and MACD is crossing the signal line under 0. Probado en cryptos en velas de 4 horas, muy eficiente!" MQL5 port claims "65% win rate on the 30 minute time frame."
- **Timeframe:** 4h (per Pine Script) to 1d.
- **Indicators:** EMA(200), MACD(12, 26, 9).
- **Entry (long):** Price closes ABOVE 200 EMA (trend filter) AND MACD line crosses ABOVE signal line AND crossover occurs BELOW zero line (momentum reversal within uptrend).
- **Entry (short):** Price below 200 EMA AND MACD crosses below signal AND crossover above zero line.
- **Exit:** Opposite MACD signal (MACD crosses below signal for long exit). Some variants add trailing stop after entry.
- **Stop:** Swing-low stop (lowest low of last 10–20 bars) or ATR stop (1.5×ATR). Base strategy lacks hard stop — bot must add one.
- **R:R:** YouTube "tested 100 times" methodology typically targets 1:1.5 to 1:2.
- **Claimed (unverified):** MQL5 port: 65% win rate on 30m. Pine Script: "very efficient on 4h crypto candles."
- **Why #3:** Fully mechanical, dual-indicator conjunction. Classic trend-continuation pattern. Weakness: base has no hard stop — bot adds ATR stop.

### 4. RSI(2) Mean Reversion (Larry Connors) — testability 5/5
- **Source:** Larry Connors' book "Short Term Trading Strategies That Work." StockCharts ChartSchool, QuantifiedStrategies.com (March 2026), StratBase.ai crypto adaptation (Feb 2026 — "backtested on BTC and ETH with optimized thresholds").
- **Timeframe:** 1h–1d. StratBase adapted for BTC/ETH on 1h–4h.
- **Indicators:** RSI(2) (2-period, NOT standard 14), SMA(200), SMA(5).
- **Entry (long):** Close > SMA(200) (uptrend filter) AND RSI(2) < 10 (deeply oversold). StratBase's crypto adaptation may use RSI(2) < 15 or < 20 for crypto's higher volatility.
- **Entry (short):** Close < SMA(200) AND RSI(2) > 90.
- **Exit (long):** Close > SMA(5) (quick mean-reversion exit). Alternative: RSI(2) > 50 or 65.
- **Stop:** Classic has NO stop loss (reliance on mean-reversion exit). Bot must add: 2–3×ATR below entry, or fixed % (e.g., -5%). Documented 34% max drawdown — stop is advisable.
- **R:R:** Inverted (mean reversion) — high win rate, small average win. Roughly 1:0.5 to 1:1 per trade. Not a "let winners run" strategy.
- **Claimed (unverified):** Connors' original: ~70–80% win rate on equities with RSI(2) < 5. QuantifiedStrategies: 34% max drawdown. StratBase: crypto-optimized results exist but specifics not in snippet.
- **Why #4:** Most codeable strategy in the pool (~20 lines of Python). Mean-reversion logic diversifies the trend-following strategies 1–3. Weakness: no native stop, 34% drawdown in volatile regimes.

### 5. WaveTrend+ Strategy (SystemAlpha) — testability 4.5/5
- **Source:** TradingView "WaveTrend+ Strategy [SystemAlpha]" (https://www.tradingview.com/script/bPJohkjs-WaveTrend-Strategy-SystemAlpha/). Script description: "WaveTrend strategy based on WaveTrend Oscillator. In addition to crossovers, we use trend filters, trailing stop loss and take profit targets. Developed for crypto, forex and stocks for 15 minutes to daily timeframe." Underlying WaveTrend Oscillator by LazyBear (2014). PickMyTrade blog claims "WaveTrend 70% win rates on BTC" (April 2026, unverified).
- **Timeframe:** 15m–1d. Sweet spot 1h–4h for bot.
- **Indicators:** WaveTrend Oscillator (WT1, WT2 lines — HLC3 channel average + double-EMA smoothing), optional trend filter, ATR for trailing stop.
- **Entry (long):** WT1 crosses ABOVE WT2 AND WT1 is below oversold level at crossover (default oversold = -60). Optional trend filter confirmation.
- **Entry (short):** WT1 crosses BELOW WT2 AND WT1 is above overbought (default +53 to +60).
- **Exit:** Base: WT1 crosses back through WT2 opposite direction. WT+ variant: ATR trailing stop OR take-profit target.
- **Stop:** WT+ variant: ATR-based trailing stop. Base LazyBear: no hard stop.
- **R:R:** WT+ script supports configurable TP — R:R can be set (e.g., 1:2 by setting TP at 2× ATR stop distance).
- **Claimed (unverified):** PickMyTrade: 70% win rate on BTC (vendor claim). No audited results on script page.
- **Why #5:** Mechanical crossover + zone check. WT+ variant explicitly adds trailing stop + TP, fits risk-managed philosophy. More complex WT calculation (~40 lines Python) with more parameters → higher overfitting risk.

---

## Candidates 6–12 (ranked below top 5)

| # | Strategy | Source | TF | Testability |
|---|---|---|---|---|
| 6 | Bollinger Bands Squeeze Breakout | TitanFX, AlgoKing, tapbit, LiteFinance (TTM Squeeze) | 1h–1d | 4.5 |
| 7 | Triple EMA Crossover (9/21/50) + ATR Trailing Stop | YouTube Aug 2025, GitHub hasnocool, Strategester | 1h–4h | 4.5 |
| 8 | BTC Momentum (RSI + Stoch RSI + EMA Exit) | TradingView script LkZ1hQMj, coindar.org | 1h–4h | 4.0 |
| 9 | SMA Crossover (50/200 Golden/Death Cross) | NeuroBacktest, QuantifiedStrategies | 1d | 4.0 |
| 10 | Smart Money Concepts (ICT) | GitHub joshyattridge/smart-money-concepts (PyPI package) | 1h–1d | 3.0 |
| 11 | Grid Trading Bot (Neutral Grid) | Binance/Bybit native, dev.to backtest, YouTube | continuous | 4.0 |
| 12 | DCA + RSI Filter (Smart DCA) | Radiant, 3Commas, Coin Bureau | 1d | 4.0 |

---

## Implementation order for the bot

The top 5 cover three strategy families:
- **Trend-following SAR:** #1 UT Bot + #2 Supertrend (near-identical math — implement one, get the other by param change)
- **Trend-continuation w/ momentum filter:** #3 MACD + 200 EMA
- **Mean reversion:** #4 RSI(2) Connors (portfolio diversifier, opposite family)
- **Oscillator reversal w/ risk mgmt:** #5 WaveTrend+ (built-in trailing stop + TP)

All five translate to: indicator calc (EMA/RSI/ATR/MACD/WaveTrend via `ta` lib) + threshold comparison + entry/exit trigger. All have defined stop logic (some need ATR stop added by the bot).

All claimed win rates are vendor/unverified — the bot's own backtests on real ccxt data are the source of truth.
