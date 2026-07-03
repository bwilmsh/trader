"""
Supertrend — ATR trend-following SAR.
Source: TradingView "Stella's SuperTrend Basic" by StellaEntry.
        https://www.tradingview.com/script/c7l4zdiN-Stella-s-SuperTrend-Basic/
        FXOpen, goodcrypto.app guides. PickMyTrade blog (April 2026).

Mechanics:
  upper_band = (high + low)/2 + multiplier × ATR
  lower_band = (high + low)/2 - multiplier × ATR
  Supertrend line flips between upper (resistance, when close < upper) and
  lower (support, when close > lower). Buy when close crosses above the
  Supertrend line (line was acting as resistance, now acts as support). SAR exit
  on opposite flip.

Params: atr_period (default 10), multiplier (default 3). Stella's crypto-optimized.
"""
import numpy as np
import pandas as pd
from strategies.base import Strategy, Signal, ExitSignal
from ta.volatility import AverageTrueRange


class Supertrend(Strategy):
    name = "supertrend"
    timeframe = "1h"
    description = "Supertrend ATR trend-following SAR (Stella's crypto variant)"

    def __init__(self, params: dict = None):
        super().__init__(params)
        self.atr_period = self.params.get("atr_period", 10)
        self.multiplier = self.params.get("multiplier", 3.0)

    def prepare(self, df):
        df["atr"] = AverageTrueRange(
            df["high"], df["low"], df["close"], window=self.atr_period
        ).average_true_range()
        hl2 = (df["high"] + df["low"]) / 2.0
        upper_basic = hl2 + self.multiplier * df["atr"]
        lower_basic = hl2 - self.multiplier * df["atr"]

        # Final upper/lower bands: ratchet logic (only moves in trend direction)
        upper = pd.Series(index=df.index, dtype=float)
        lower = pd.Series(index=df.index, dtype=float)
        for i in range(len(df)):
            if i == 0:
                upper.iloc[i] = upper_basic.iloc[i]
                lower.iloc[i] = lower_basic.iloc[i]
                continue
            prev_upper = upper.iloc[i-1]
            prev_lower = lower.iloc[i-1]
            prev_close = df["close"].iloc[i-1]
            # Upper band: ratchets down (tightens) only if new upper < prev upper AND close prev < prev upper
            if upper_basic.iloc[i] < prev_upper or prev_close > prev_upper:
                upper.iloc[i] = upper_basic.iloc[i]
            else:
                upper.iloc[i] = prev_upper
            # Lower band: ratchets up only if new lower > prev lower AND prev close > prev lower
            if lower_basic.iloc[i] > prev_lower or prev_close < prev_lower:
                lower.iloc[i] = lower_basic.iloc[i]
            else:
                lower.iloc[i] = prev_lower

        # Supertrend line: if close > prev_upper → lower band (support); else → upper band (resistance)
        st = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)  # 1 = up, -1 = down
        for i in range(len(df)):
            if i == 0:
                st.iloc[i] = upper.iloc[i]
                direction.iloc[i] = -1
                continue
            prev_dir = direction.iloc[i-1]
            if prev_dir == 1 and df["close"].iloc[i] < lower.iloc[i]:
                st.iloc[i] = upper.iloc[i]
                direction.iloc[i] = -1
            elif prev_dir == -1 and df["close"].iloc[i] > upper.iloc[i]:
                st.iloc[i] = lower.iloc[i]
                direction.iloc[i] = 1
            else:
                st.iloc[i] = lower.iloc[i] if prev_dir == 1 else upper.iloc[i]
                direction.iloc[i] = prev_dir

        df["supertrend"] = st
        df["st_dir"] = direction
        df["st_dir_prev"] = df["st_dir"].shift(1)

        # Flip signals: direction changes
        df["buy_signal"] = (df["st_dir_prev"] == -1) & (df["st_dir"] == 1)
        df["sell_signal"] = (df["st_dir_prev"] == 1) & (df["st_dir"] == -1)
        df.dropna(inplace=True)

    def evaluate(self, row, open_position) -> Signal | ExitSignal:
        atr = row["atr"]
        if atr != atr or atr <= 0:
            return Signal(enter=False)

        if open_position is None:
            if row["buy_signal"]:
                entry = row["close"]
                stop = row["supertrend"]
                risk = abs(entry - stop)
                target = entry + 2 * risk  # 2R fixed target (SAR has no native target)
                return Signal(
                    enter=True, direction="long",
                    entry_price=entry, stop_price=stop, target_price=target,
                    reason=f"Supertrend flip up; ATR={atr:.2f} stop={stop:.2f}",
                )
            return Signal(enter=False)
        else:
            if row["sell_signal"]:
                return ExitSignal(
                    exit=True, exit_price=row["close"],
                    reason="Supertrend flip down — SAR exit",
                )
            return ExitSignal(exit=False)
