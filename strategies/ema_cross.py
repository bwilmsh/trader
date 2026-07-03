"""
EMA crossover — classic trend-following strategy. Smoke test for the engine.
Not a real contender — this is the "does the engine actually run" strategy.

Rules:
  - Fast EMA (e.g. 12) crosses above Slow EMA (e.g. 26) → long entry
  - Stop: 2 * ATR below entry
  - Target: 3 * ATR above entry (gives 1.5 R:R)
  - Exit on stop, target, or opposite cross
  - Long-only for spot crypto (no shorts on spot)
"""
from strategies.base import Strategy, Signal, ExitSignal
from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator


class EmaCross(Strategy):
    name = "ema_cross"
    timeframe = "1h"
    description = "EMA 12/26 crossover with ATR-based stop and target"

    def __init__(self, params: dict = None):
        super().__init__(params)
        self.fast = self.params.get("fast", 12)
        self.slow = self.params.get("slow", 26)
        self.atr_window = self.params.get("atr", 14)
        self.stop_atr_mult = self.params.get("stop_atr", 2.0)
        self.target_atr_mult = self.params.get("target_atr", 3.0)

    def prepare(self, df):
        df["ema_fast"] = EMAIndicator(df["close"], window=self.fast).ema_indicator()
        df["ema_slow"] = EMAIndicator(df["close"], window=self.slow).ema_indicator()
        df["atr"] = AverageTrueRange(
            df["high"], df["low"], df["close"], window=self.atr_window
        ).average_true_range()
        # Previous values for cross detection
        df["ema_fast_prev"] = df["ema_fast"].shift(1)
        df["ema_slow_prev"] = df["ema_slow"].shift(1)
        df.dropna(inplace=True)

    def evaluate(self, row, open_position) -> Signal | ExitSignal:
        # Cross detection: fast was below, now above
        crossed_up = (
            row["ema_fast_prev"] <= row["ema_slow_prev"]
            and row["ema_fast"] > row["ema_slow"]
        )
        crossed_dn = (
            row["ema_fast_prev"] >= row["ema_slow_prev"]
            and row["ema_fast"] < row["ema_slow"]
        )

        atr = row["atr"]
        if atr != atr or atr <= 0:  # NaN check
            return Signal(enter=False)

        if open_position is None:
            if crossed_up:
                entry = row["close"]
                stop = entry - self.stop_atr_mult * atr
                target = entry + self.target_atr_mult * atr
                return Signal(
                    enter=True, direction="long",
                    entry_price=entry, stop_price=stop, target_price=target,
                    reason=f"EMA {self.fast} crossed above {self.slow}; ATR={atr:.2f}",
                )
            return Signal(enter=False)
        else:
            # Exit on opposite cross
            if crossed_dn:
                return ExitSignal(
                    exit=True, exit_price=row["close"],
                    reason="EMA cross down — exit signal",
                )
            return ExitSignal(exit=False)
