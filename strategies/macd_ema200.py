"""
MACD + 200 EMA Trend Filter — trend-continuation with momentum reversal.
Source: YouTube "200 EMA + MACD Trading Strategy Tested 100 Times"
        https://www.youtube.com/watch?v=kr_kGf7fENI
        TradingView Pine Script: "MACD strategy combine with a 200 EMA —
        Buy when price above 200 EMA and MACD is crossing the signal line under 0.
        Probado en cryptos en velas de 4 horas, muy eficiente!"
        MQL5 port claims 65% win rate on 30m.

Mechanics:
  Trend filter: close above 200 EMA → only longs.
  Entry trigger: MACD line crosses above signal line AND crossover is below zero
                 (momentum reversal within the uptrend).
  Exit: MACD crosses below signal line (momentum reversal against position).
  Stop: ATR-based — 1.5×ATR below entry (bot adds this; base strategy has no hard stop).
  Target: 2× the ATR stop distance (1.5R — slightly above the 1.5 min R:R gate).

Params: ema_period (200), macd_fast (12), macd_slow (26), macd_signal (9),
        stop_atr_mult (1.5), target_r (2.0).
"""
import pandas as pd
from strategies.base import Strategy, Signal, ExitSignal
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange


class MacdEma200(Strategy):
    name = "macd_ema200"
    timeframe = "4h"
    description = "MACD bullish cross below zero + price above 200 EMA (YouTube-tested)"

    def __init__(self, params: dict = None):
        super().__init__(params)
        self.ema_period = self.params.get("ema", 200)
        self.macd_fast = self.params.get("macd_fast", 12)
        self.macd_slow = self.params.get("macd_slow", 26)
        self.macd_signal = self.params.get("macd_signal", 9)
        self.atr_period = self.params.get("atr", 14)
        self.stop_atr_mult = self.params.get("stop_atr", 1.5)
        self.target_r = self.params.get("target_r", 2.0)

    def prepare(self, df):
        df["ema200"] = EMAIndicator(df["close"], window=self.ema_period).ema_indicator()
        macd = MACD(
            df["close"],
            window_fast=self.macd_fast,
            window_slow=self.macd_slow,
            window_sign=self.macd_signal,
        )
        df["macd_line"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_diff"] = macd.macd_diff()
        df["atr"] = AverageTrueRange(
            df["high"], df["low"], df["close"], window=self.atr_period
        ).average_true_range()

        df["macd_line_prev"] = df["macd_line"].shift(1)
        df["macd_signal_prev"] = df["macd_signal"].shift(1)
        df["close_prev"] = df["close"].shift(1)
        df["ema200_prev"] = df["ema200"].shift(1)

        # Bullish cross: MACD line was below signal, now above. Cross below zero.
        df["macd_bull_cross"] = (
            (df["macd_line_prev"] <= df["macd_signal_prev"]) &
            (df["macd_line"] > df["macd_signal"])
        )
        # Crossover occurs below zero line (both lines < 0)
        df["cross_below_zero"] = (df["macd_line"] < 0) & (df["macd_signal"] < 0)
        # Price above 200 EMA
        df["above_ema200"] = df["close"] > df["ema200"]

        # Entry: all three
        df["entry_signal"] = df["macd_bull_cross"] & df["cross_below_zero"] & df["above_ema200"]

        # Exit: MACD crosses below signal (momentum reversal)
        df["macd_bear_cross"] = (
            (df["macd_line_prev"] >= df["macd_signal_prev"]) &
            (df["macd_line"] < df["macd_signal"])
        )
        df["exit_signal"] = df["macd_bear_cross"]
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
                target = entry + self.target_r * risk
                return Signal(
                    enter=True, direction="long",
                    entry_price=entry, stop_price=stop, target_price=target,
                    reason=f"MACD bull cross below zero, price > 200EMA; ATR={atr:.2f}",
                )
            return Signal(enter=False)
        else:
            if row["exit_signal"]:
                return ExitSignal(
                    exit=True, exit_price=row["close"],
                    reason="MACD bear cross — momentum exit",
                )
            return ExitSignal(exit=False)
