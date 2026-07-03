"""
UT Bot Alerts — ATR trailing stop SAR system.
Source: TradingView Pine Script "UT Bot Alerts" by QuantNomad.
        https://www.tradingview.com/script/n8ss8BID-UT-Bot-Alerts/

Mechanics (exact Pine Script logic):
  nLoss = keyvalue × ATR
  nRes[i] = if close[i] > nRes[i-1] and close[i-1] > nRes[i-1]:
               max(nRes[i-1], close[i] - nLoss[i])     ← ratchet up (long trailing)
            elif close[i] < nRes[i-1] and close[i-1] < nRes[i-1]:
               min(nRes[i-1], close[i] + nLoss[i])     ← ratchet down (short trailing)
            else:
               close[i] - nLoss[i] if close[i] >= close[i-1]   ← reset/fallback
               close[i] + nLoss[i] if close[i] < close[i-1]

  Buy signal:  close crosses above nRes  (close[1] <= nRes[1] and close > nRes)
  Sell signal: close crosses below nRes  (close[1] >= nRes[1] and close < nRes)

This is a stop-and-reverse (always-in-market) system. For spot crypto (long-only)
we enter on buy signals and exit on sell signals (or stop/target hit in the engine).

Params: keyvalue (default 3), atr_period (default 10).
"""
import pandas as pd
from strategies.base import Strategy, Signal, ExitSignal
from ta.volatility import AverageTrueRange


class UTBot(Strategy):
    name = "ut_bot"
    timeframe = "1h"
    description = "UT Bot Alerts — ATR trailing stop SAR (QuantNomad)"

    def __init__(self, params: dict = None):
        super().__init__(params)
        self.keyvalue = self.params.get("keyvalue", 3)
        self.atr_period = self.params.get("atr_period", 10)

    def prepare(self, df):
        df["atr"] = AverageTrueRange(
            df["high"], df["low"], df["close"], window=self.atr_period
        ).average_true_range()
        nLoss = self.keyvalue * df["atr"]

        # Build nRes trailing stop iteratively with exact Pine Script semantics
        closes = df["close"].values
        nloss = nLoss.values
        nres = [0.0] * len(closes)
        for i in range(len(closes)):
            c = closes[i]
            cl = nloss[i]
            if i == 0 or nres[i-1] == 0:
                # First bar: initialize
                nres[i] = c - cl if c >= c else c + cl  # default to long-side
                # Actually Pine nz(nRes[1], 0) → 0 on first bar, so close > 0 and close[1]=0 → falls to else
                nres[i] = c - cl
                continue
            prev_nres = nres[i-1]
            prev_close = closes[i-1]
            if c > prev_nres and prev_close > prev_nres:
                # Both above → ratchet up: trailing stop only moves up
                nres[i] = max(prev_nres, c - cl)
            elif c < prev_nres and prev_close < prev_nres:
                # Both below → ratchet down: trailing stop only moves down
                nres[i] = min(prev_nres, c + cl)
            else:
                # Reset/fallback: compare close to prev close to decide direction
                if c >= prev_close:
                    nres[i] = c - cl
                else:
                    nres[i] = c + cl

        df["nRes"] = nres
        df["nRes_prev"] = df["nRes"].shift(1)
        df["close_prev"] = df["close"].shift(1)

        # Cross signals
        df["buy_signal"] = (df["close_prev"] <= df["nRes_prev"]) & (df["close"] > df["nRes"])
        df["sell_signal"] = (df["close_prev"] >= df["nRes_prev"]) & (df["close"] < df["nRes"])
        df.dropna(inplace=True)

    def evaluate(self, row, open_position) -> Signal | ExitSignal:
        atr = row["atr"]
        if atr != atr or atr <= 0:
            return Signal(enter=False)

        if open_position is None:
            if row["buy_signal"]:
                entry = row["close"]
                stop = row["nRes"]  # the trailing stop IS the stop
                risk = abs(entry - stop)
                target = entry + 2 * risk  # 2R fixed target (SAR has no native target)
                return Signal(
                    enter=True, direction="long",
                    entry_price=entry, stop_price=stop, target_price=target,
                    reason=f"close crossed above ATR trailing stop; ATR={atr:.2f}",
                )
            return Signal(enter=False)
        else:
            if row["sell_signal"]:
                return ExitSignal(
                    exit=True, exit_price=row["close"],
                    reason="trailing stop crossed down — SAR exit",
                )
            return ExitSignal(exit=False)
