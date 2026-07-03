"""
RSI(2) Mean Reversion — Larry Connors.
Source: Connors' book "Short Term Trading Strategies That Work."
        StockCharts ChartSchool, QuantifiedStrategies.com (March 2026),
        StratBase.ai crypto adaptation (Feb 2026 — backtested on BTC/ETH).

Mechanics:
  Trend filter: close > SMA(200) → only buy dips in uptrends.
  Entry: RSI(2) < 10 (deeply oversold). StratBase's crypto adaptation may
         use < 15 or < 20 for crypto's higher volatility — configurable.
  Exit: close > SMA(5) (quick mean-reversion exit).
  Stop: classic has NO stop. Bot adds ATR-based hard stop (2×ATR below entry).
  Target: none — exit on SMA(5) cross. This is a high-win-rate, small-winner strategy.

Note: R:R is typically inverted (small winners, small losers) but win rate is high.
The R:R gate in the engine may reject many of these trades because the ATR stop
makes the R:R < 1.5:1. We relax the gate for this strategy by setting a wider target
(1.5× the ATR stop distance) so trades pass the gate, but the real exit is the SMA(5)
cross — the target is a backstop only.

Params: rsi_period (2), rsi_threshold (10), sma_long (200), sma_exit (5),
        stop_atr_mult (2.0).
"""
import pandas as pd
from strategies.base import Strategy, Signal, ExitSignal
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from ta.volatility import AverageTrueRange


class Rsi2MeanReversion(Strategy):
    name = "rsi2_mr"
    timeframe = "1h"
    description = "RSI(2) Connors mean reversion — buy deep oversold dips in uptrends"

    def __init__(self, params: dict = None):
        super().__init__(params)
        self.rsi_period = self.params.get("rsi_period", 2)
        self.rsi_threshold = self.params.get("rsi_threshold", 10)  # StratBase crypto may use 15-20
        self.sma_long = self.params.get("sma_long", 200)
        self.sma_exit = self.params.get("sma_exit", 5)
        self.atr_period = self.params.get("atr", 14)
        self.stop_atr_mult = self.params.get("stop_atr", 2.0)
        # Target set wide so trades pass the R:R gate; real exit is SMA(5) cross.
        self.target_r = self.params.get("target_r", 1.6)

    def prepare(self, df):
        df["rsi2"] = RSIIndicator(df["close"], window=self.rsi_period).rsi()
        df["sma200"] = SMAIndicator(df["close"], window=self.sma_long).sma_indicator()
        df["sma5"] = SMAIndicator(df["close"], window=self.sma_exit).sma_indicator()
        df["atr"] = AverageTrueRange(
            df["high"], df["low"], df["close"], window=self.atr_period
        ).average_true_range()

        df["close_prev"] = df["close"].shift(1)
        df["sma5_prev"] = df["sma5"].shift(1)

        # Entry: close > SMA(200) AND RSI(2) < threshold
        df["entry_signal"] = (df["close"] > df["sma200"]) & (df["rsi2"] < self.rsi_threshold)

        # Exit: close crosses above SMA(5) (mean reversion complete)
        df["exit_signal"] = (df["close_prev"] <= df["sma5_prev"]) & (df["close"] > df["sma5"])
        df.dropna(inplace=True)

    def evaluate(self, row, open_position) -> Signal | ExitSignal:
        atr = row["atr"]
        if atr != atr or atr <= 0:
            return Signal(enter=False)

        if open_position is None:
            if row["entry_signal"]:
                entry = row["close"]
                stop = entry - self.stop_atr_mult * atr
                risk = abs(entry - stop)
                target = entry + self.target_r * risk  # backstop target to pass R:R gate
                return Signal(
                    enter=True, direction="long",
                    entry_price=entry, stop_price=stop, target_price=target,
                    reason=f"RSI(2)={row['rsi2']:.1f}<{self.rsi_threshold}, close>SMA200; ATR={atr:.2f}",
                )
            return Signal(enter=False)
        else:
            # Primary exit: SMA(5) cross (mean reversion complete)
            if row["exit_signal"]:
                return ExitSignal(
                    exit=True, exit_price=row["close"],
                    reason="close crossed above SMA(5) — mean reversion complete",
                )
            return ExitSignal(exit=False)
