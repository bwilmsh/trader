"""
Backtest engine — walks candles through a strategy, sizes positions by risk,
tracks open trades, applies fees and slippage, and returns real performance metrics.

Position sizing logic (the core of risk management):
  - Strategy gives entry, stop, target.
  - Risk per trade = risk_per_trade_pct * current_equity.
  - Stop distance % = abs(entry - stop) / entry.
  - Position size (USD notional) = risk_per_trade_usd / stop_distance_pct.
  - If R:R (target vs stop) < rr_min, trade is REJECTED — logged but not taken.
  - Fees and slippage applied on both entry and exit.

This is event-driven on candle close, not tick-level. Crypto spot, no leverage.
"""
from dataclasses import dataclass
from typing import Optional

from strategies.base import Signal, ExitSignal, Strategy
from backtest.metrics import TradeResult, compute_metrics, BacktestMetrics


@dataclass
class BacktestConfig:
    initial_capital: float = 1000.0
    fee_pct: float = 0.001         # 0.1% per side
    slippage_pct: float = 0.0005  # 0.05%
    risk_per_trade_pct: float = 0.01
    rr_min: float = 1.5


def _apply_slippage(price: float, direction: str, slip: float) -> float:
    """Slippage: buy higher, sell lower."""
    if direction == "long":
        return price * (1 + slip)   # buying — pay more
    else:
        return price * (1 - slip)   # selling — get less


def _size_position(entry: float, stop: float, equity: float, risk_pct: float):
    """
    Return (position_usd, risk_usd, stop_distance_pct).
    Position sized so that if stop hits, we lose exactly risk_pct of equity.
    """
    stop_dist = abs(entry - stop) / entry
    if stop_dist == 0:
        return 0.0, 0.0, 0.0
    risk_usd = equity * risk_pct
    position_usd = risk_usd / stop_dist
    return position_usd, risk_usd, stop_dist


def _check_rr(entry: float, stop: float, target: float, rr_min: float) -> bool:
    """Reject trades that don't meet minimum R:R."""
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk == 0:
        return False
    return (reward / risk) >= rr_min


def run_backtest(df, strategy: Strategy, config: BacktestConfig) -> BacktestMetrics:
    """
    Run a strategy over a dataframe of candles. df must have OHLCV columns.
    Strategy.prepare(df) is called first to precompute indicators.
    Then we iterate row by row.
    """
    strategy.prepare(df)

    trades: list[TradeResult] = []
    open_trade: Optional[TradeResult] = None
    equity = config.initial_capital
    rejected = 0

    for idx, row in df.iterrows():
        # If we have an open trade, check for exit first (stop, target, or strategy signal)
        if open_trade is not None:
            # 1. Check stop and target hits against this candle's high/low
            hit_stop = False
            hit_target = False
            exit_price = 0.0
            exit_reason = ""

            if open_trade.direction == "long":
                if row["low"] <= open_trade.stop_price:
                    hit_stop = True
                    exit_price = open_trade.stop_price
                    exit_reason = "stop hit"
                elif row["high"] >= open_trade.target_price:
                    hit_target = True
                    exit_price = open_trade.target_price
                    exit_reason = "target hit"
            else:  # short
                if row["high"] >= open_trade.stop_price:
                    hit_stop = True
                    exit_price = open_trade.stop_price
                    exit_reason = "stop hit"
                elif row["low"] <= open_trade.target_price:
                    hit_target = True
                    exit_price = open_trade.target_price
                    exit_reason = "target hit"

            # 2. If no stop/target hit, ask strategy if it wants to exit
            if not hit_stop and not hit_target:
                ex = strategy.evaluate(row, open_trade)
                if isinstance(ex, ExitSignal) and ex.exit:
                    hit_stop = True  # reuse path
                    exit_price = _apply_slippage(ex.exit_price, open_trade.direction, config.slippage_pct)
                    # invert slippage for exit: long sells → lower; short buys → higher
                    if open_trade.direction == "long":
                        exit_price = ex.exit_price * (1 - config.slippage_pct)
                    else:
                        exit_price = ex.exit_price * (1 + config.slippage_pct)
                    exit_reason = ex.reason or "strategy exit"

            if hit_stop or hit_target:
                # Apply slippage to stop/target exits too
                if exit_reason in ("stop hit", "target hit"):
                    if open_trade.direction == "long":
                        exit_price = exit_price * (1 - config.slippage_pct)  # sell lower
                    else:
                        exit_price = exit_price * (1 + config.slippage_pct)  # buy higher

                # Compute PnL
                direction_factor = 1 if open_trade.direction == "long" else -1
                gross_pnl = (exit_price - open_trade.entry_price) * direction_factor * (
                    open_trade.position_size_usd / open_trade.entry_price
                )
                # Fees: entry + exit
                fees = (
                    open_trade.entry_price * (open_trade.position_size_usd / open_trade.entry_price) * config.fee_pct
                    + exit_price * (open_trade.position_size_usd / open_trade.entry_price) * config.fee_pct
                )
                net_pnl = gross_pnl - fees
                open_trade.pnl_usd = net_pnl
                open_trade.exit_price = exit_price
                open_trade.exit_time = idx
                open_trade.win = net_pnl > 0

                # R multiple
                initial_risk = open_trade.position_size_usd * abs(open_trade.entry_price - open_trade.stop_price) / open_trade.entry_price
                open_trade.r_multiple = net_pnl / initial_risk if initial_risk > 0 else 0.0
                open_trade.bars_held = len(trades)  # placeholder; will fix below if needed

                equity += net_pnl
                trades.append(open_trade)
                open_trade = None

        # If no open trade, ask strategy if it wants to enter on this candle's close
        if open_trade is None:
            sig = strategy.evaluate(row, None)
            if isinstance(sig, Signal) and sig.enter:
                # R:R gate
                if not _check_rr(sig.entry_price, sig.stop_price, sig.target_price, config.rr_min):
                    rejected += 1
                    continue

                entry = _apply_slippage(sig.entry_price, sig.direction, config.slippage_pct)
                # For a long, slippage makes entry higher; adjust stop/target proportionally? 
                # We'll keep them as strategy specified (they're relative to original entry).
                # Simpler: use strategy's original entry_price for stop/target math,
                # but actual fill is `entry`. The small discrepancy is realistic.

                pos_usd, risk_usd, stop_dist = _size_position(
                    entry, sig.stop_price, equity, config.risk_per_trade_pct
                )

                if pos_usd <= 0:
                    continue

                open_trade = TradeResult(
                    entry_time=idx, exit_time=None, direction=sig.direction,
                    entry_price=entry, exit_price=0.0,
                    stop_price=sig.stop_price, target_price=sig.target_price,
                    position_size_usd=pos_usd, pnl_usd=0.0, pnl_pct=0.0,
                    r_multiple=0.0, bars_held=0, win=False,
                )

    # Close any still-open trade at last close
    if open_trade is not None:
        last_row = df.iloc[-1]
        exit_price = last_row["close"]
        direction_factor = 1 if open_trade.direction == "long" else -1
        gross = (exit_price - open_trade.entry_price) * direction_factor * (
            open_trade.position_size_usd / open_trade.entry_price
        )
        fees = (
            open_trade.entry_price * (open_trade.position_size_usd / open_trade.entry_price) * config.fee_pct
            + exit_price * (open_trade.position_size_usd / open_trade.entry_price) * config.fee_pct
        )
        net = gross - fees
        open_trade.pnl_usd = net
        open_trade.exit_price = exit_price
        open_trade.exit_time = df.index[-1]
        open_trade.win = net > 0
        initial_risk = open_trade.position_size_usd * abs(open_trade.entry_price - open_trade.stop_price) / open_trade.entry_price
        open_trade.r_multiple = net / initial_risk if initial_risk > 0 else 0.0
        equity += net
        trades.append(open_trade)

    metrics = compute_metrics(trades, config.initial_capital)
    print(f"  {strategy.name}: {len(trades)} trades taken, {rejected} rejected by R:R gate")
    return metrics


def run_walk_forward(df, strategy: Strategy, config: BacktestConfig, train_frac: float = 0.7):
    """
    Walk-forward: train (tune params) on first 70%, test on remaining 30%.
    For now just splits and runs both. Real param optimization comes later.
    """
    n = int(len(df) * train_frac)
    train_df = df.iloc[:n].copy()
    test_df = df.iloc[n:].copy()

    print(f"  walk-forward train={len(train_df)} test={len(test_df)} bars")
    train_m = run_backtest(train_df, strategy, config)
    test_m = run_backtest(test_df, strategy, config)

    print("  TRAIN:")
    print(train_m.summary())
    print("  TEST:")
    print(test_m.summary())
    return train_m, test_m
