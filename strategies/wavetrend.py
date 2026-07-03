"""
WaveTrend+ — oscillator reversal with ATR trailing stop + take profit.
Source: TradingView "WaveTrend+ Strategy [SystemAlpha]".
        https://www.tradingview.com/script/bPJohkjs-WaveTrend-Strategy-SystemAlpha/
        Script desc: "WaveTrend strategy based on WaveTrend Oscillator. In addition
        to crossovers, we use trend filters, trailing stop loss and take profit targets.
        Developed for crypto, forex and stocks for 15 minutes to daily timeframe."
        Underlying WaveTrend Oscillator by LazyBear (2014). PickMyTrade blog claims
        "WaveTrend 70% win rates on BTC" (April 2026, unverified vendor claim).

Mechanics:
  WaveTrend Oscillator:
    1. hlc3 = (high + low + close) / 3
    2. esa = EMA(hlc3, channel_length)                      # smoothed HLC3
    3. d = EMA(abs(hlc3 - esa), channel_length)           # mean absolute deviation
    4. ci = (hlc3 - esa) / (0.015 * d)                     # channel index (WT1)
    5. wt1 = EMA(ci, ema_length)                           # final WT1 line
    6. wt2 = SMA(wt1, sma_length)                          # signal line (WT2)

  Entry (long):  wt1 crosses ABOVE wt2 AND wt1 < oversold level (default -60)
                 (crossover happens in oversold territory — reversal up)
  Entry (short): wt1 crosses BELOW wt2 AND wt1 > overbought (default +60)

  Exit: wt1 crosses back below wt2 (oscillator reversal) OR ATR trailing stop hit
        OR take-profit target hit (whichever first — engine handles stop/target).

  Stop: ATR-based — stop_atr_mult × ATR below entry (bot adds this; base has no hard stop).
  Target: target_r × the ATR stop distance (configurable R:R, default 2.0).

Params: channel_length (default 10), ema_length (default 21), sma_length (default 4),
        oversold (default -60), overbought (default 60), stop_atr_mult (default 2.0),
        target_r (default 2.0), atr_period (default 14).
"""
import pandas as pd
from strategies.base import Strategy, Signal, ExitSignal
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange


def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


class WaveTrend(Strategy):
    name = "wavetrend"
    timeframe = "1h"
    description = "WaveTrend+ oscillator reversal w/ ATR stop + TP (SystemAlpha)"

    def __init__(self, params: dict = None):
        super().__init__(params)
        self.channel_length = self.params.get("channel_length", 10)
        self.ema_length = self.params.get("ema_length", 21)
        self.sma_length = self.params.get("sma_length", 4)
        self.oversold = self.params.get("oversold", -60)
        self.overbought = self.params.get("overbought", 60)
        self.atr_period = self.params.get("atr", 14)
        self.stop_atr_mult = self.params.get("stop_atr", 2.0)
        self.target_r = self.params.get("target_r", 2.0)

    def prepare(self, df):
        hlc3 = (df["high"] + df["low"] + df["close"]) / 3.0
        esa = EMAIndicator(hlc3, window=self.channel_length).ema_indicator()
        d = EMAIndicator(abs(hlc3 - esa), window=self.channel_length).ema_indicator()
        # Guard against division by zero
        d_safe = d.replace(0, 1e-10)
        ci = (hlc3 - esa) / (0.015 * d_safe)
        wt1 = EMAIndicator(ci, window=self.ema_length).ema_indicator()
        wt2 = _sma(wt1, self.sma_length)

        df["wt1"] = wt1
        df["wt2"] = wt2
        df["atr"] = AverageTrueRange(
            df["high"], df["low"], df["close"], window=self.atr_period
        ).average_true_range()

        df["wt1_prev"] = df["wt1"].shift(1)
        df["wt2_prev"] = df["wt2"].shift(1)

        # Bullish cross: wt1 was below wt2, now above. AND wt1 < oversold.
        df["wt_bull_cross"] = (df["wt1_prev"] <= df["wt2_prev"]) & (df["wt1"] > df["wt2"])
        df["entry_signal"] = df["wt_bull_cross"] & (df["wt1"] < self.oversold)

        # Bearish cross (exit): wt1 crosses below wt2.
        df["wt_bear_cross"] = (df["wt1_prev"] >= df["wt2_prev"]) & (df["wt1"] < df["wt2"])
        df["exit_signal"] = df["wt_bear_cross"]
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
                    reason=f"WT1 crossed above WT2 in oversold ({row['wt1']:.1f}<-{self.oversold}); ATR={atr:.2f}",
                )
            return Signal(enter=False)
        else:
            if row["exit_signal"]:
                return ExitSignal(
                    exit=True, exit_price=row["close"],
                    reason=f"WT1 crossed below WT2 — oscillator reversal exit",
                )
            return ExitSignal(exit=False)
