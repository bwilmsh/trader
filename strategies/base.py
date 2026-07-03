"""
Base strategy class. Every strategy implements this contract.
The backtest engine calls should_enter() and should_exit() on each candle.
A strategy never decides position sizing — the engine does, based on risk config.
A strategy just says: enter yes/no, and if yes, at what price, stop, and target.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Signal:
    """A strategy's decision on a given candle."""
    enter: bool = False
    direction: str = "long"            # "long" or "short"
    entry_price: float = 0.0
    stop_price: float = 0.0
    target_price: float = 0.0
    reason: str = ""                   # human-readable trigger reason, for the log


@dataclass
class ExitSignal:
    exit: bool = False
    exit_price: float = 0.0
    reason: str = ""


class Strategy(ABC):
    """
    Subclass this to make a strategy. Implement:
      name, timeframe, prepare(df), evaluate(row, position) -> Signal/ExitSignal
    """
    name: str = "base"
    timeframe: str = "1h"
    description: str = ""

    def __init__(self, params: dict = None):
        self.params = params or {}

    @abstractmethod
    def prepare(self, df):
        """Precompute indicators on full dataframe. Mutate df in place."""
        pass

    @abstractmethod
    def evaluate(self, row, open_position) -> Signal | ExitSignal:
        """
        Called per candle. If no open position, return Signal(enter=...).
        If there's an open position, return ExitSignal(exit=...).

        row: pandas Series — one candle with all precomputed indicator columns.
        open_position: the open TradeResult or None.
        """
        pass

    def __repr__(self):
        return f"<Strategy {self.name} params={self.params}>"
