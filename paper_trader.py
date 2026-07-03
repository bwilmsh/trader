#!/usr/bin/env python3
"""
Paper trader — runs a strategy live against real exchange prices, NO real money.
Logs every signal, every virtual trade, and tracks virtual equity.

This is the bridge between backtest and live. A strategy that passes the backtest
gate runs here for a while (days/weeks) to prove the backtest results hold in real
market conditions before any real money is risked.

Flow:
  1. Poll exchange for latest candle on the strategy's timeframe.
  2. Feed candle to strategy.evaluate().
  3. If signal → record virtual trade in paper_trade_log.json.
  4. Track open virtual position, check stop/target on each new candle.
  5. Update virtual equity curve.

Usage:
  python paper_trader.py strategies.macd_ema200 --symbol BTC/USDT --timeframe 4h

Runs as a long-lived loop. Ctrl+C to stop. State persists in logs/ so restart
continues from where it left off.
"""
import sys
import os
import json
import time
import signal as sig_module
import importlib
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

import ccxt
from data.loader import to_dataframe
from strategies.base import Strategy, Signal, ExitSignal
from backtest.metrics import TradeResult

PAPER_STATE_FILE = Path(__file__).parent / "logs" / "paper_trader_state.json"
TRADE_LOG_FILE = Path(__file__).parent / "logs" / "paper_trade_log.json"


def _state_path(strategy_name, symbol, timeframe):
    safe = f"{strategy_name}_{symbol.replace('/', '')}_{timeframe}"
    return Path(__file__).parent / "logs" / f"paper_state_{safe}.json"


def _log_path(strategy_name, symbol, timeframe):
    safe = f"{strategy_name}_{symbol.replace('/', '')}_{timeframe}"
    return Path(__file__).parent / "logs" / f"paper_log_{safe}.json"


def load_state(state_file):
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {"open_trade": None, "equity": 1000.0, "trade_count": 0, "last_candle_ts": 0}


def save_state(state, state_file):
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2, default=str)


def load_trade_log(log_file):
    if log_file.exists():
        with open(log_file) as f:
            return json.load(f)
    return []


def append_trade(trade_dict, log_file):
    log = load_trade_log(log_file)
    log.append(trade_dict)
    with open(log_file, "w") as f:
        json.dump(log, f, indent=2, default=str)


def fetch_latest_candles(exchange_id, symbol, timeframe, limit=500):
    """Fetch the most recent N candles for live evaluation."""
    exchange = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    candles = [
        {
            "timestamp": c[0],
            "datetime": datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc).isoformat(),
            "open": float(c[1]), "high": float(c[2]),
            "low": float(c[3]), "close": float(c[4]), "volume": float(c[5]),
        }
        for c in ohlcv
    ]
    return candles


def check_stop_target(open_trade_dict, candle):
    """Check if the open virtual trade's stop or target was hit on this candle."""
    direction = open_trade_dict["direction"]
    stop = open_trade_dict["stop_price"]
    target = open_trade_dict["target_price"]

    if direction == "long":
        if candle["low"] <= stop:
            return True, stop, "stop hit"
        if candle["high"] >= target:
            return True, target, "target hit"
    else:  # short
        if candle["high"] >= stop:
            return True, stop, "stop hit"
        if candle["low"] <= target:
            return True, target, "target hit"
    return False, 0.0, ""


def close_virtual_trade(open_trade_dict, exit_price, exit_time, reason, state, state_file, log_file):
    """Close the virtual trade, compute PnL, append to log, update equity."""
    direction_factor = 1 if open_trade_dict["direction"] == "long" else -1
    pos_usd = open_trade_dict["position_size_usd"]
    entry = open_trade_dict["entry_price"]
    gross = (exit_price - entry) * direction_factor * (pos_usd / entry)
    # Simulate 0.1% fee on entry + exit
    fee = (entry * (pos_usd / entry) * 0.001) + (exit_price * (pos_usd / entry) * 0.001)
    net = gross - fee

    initial_risk = pos_usd * abs(entry - open_trade_dict["stop_price"]) / entry
    r_mult = net / initial_risk if initial_risk > 0 else 0.0

    trade = {
        "entry_time": open_trade_dict["entry_time"],
        "exit_time": exit_time,
        "direction": direction,
        "entry_price": entry, "exit_price": exit_price,
        "stop_price": open_trade_dict["stop_price"],
        "target_price": open_trade_dict["target_price"],
        "position_size_usd": pos_usd,
        "pnl_usd": net, "r_multiple": r_mult,
        "win": net > 0, "reason": reason,
        "mode": "paper",
    }
    append_trade(trade, log_file)

    state["equity"] += net
    state["trade_count"] += 1
    state["open_trade"] = None
    print(f"  [PAPER CLOSE] {direction} @ {exit_price:.2f} — {reason}")
    print(f"    PnL: ${net:+.2f}  ({r_mult:+.2f}R)  equity=${state['equity']:.2f}")
    save_state(state, state_file)


def open_virtual_trade(signal_dict, candle, state, state_file):
    """Open a virtual trade from a signal."""
    entry = signal_dict["entry_price"]
    stop = signal_dict["stop_price"]
    equity = state["equity"]
    # Position size: risk 1% of equity
    stop_dist = abs(entry - stop) / entry
    if stop_dist == 0:
        return
    risk_usd = equity * 0.01
    pos_usd = risk_usd / stop_dist

    trade = {
        "entry_time": candle["datetime"],
        "direction": signal_dict["direction"],
        "entry_price": entry,
        "stop_price": stop,
        "target_price": signal_dict["target_price"],
        "position_size_usd": pos_usd,
        "reason": signal_dict["reason"],
        "mode": "paper",
    }
    state["open_trade"] = trade
    print(f"  [PAPER OPEN] {trade['direction']} @ {entry:.2f}")
    print(f"    stop={stop:.2f}  target={signal_dict['target_price']:.2f}  size=${pos_usd:.2f}")
    print(f"    reason: {signal_dict['reason']}")
    save_state(state, state_file)


def signal_to_dict(sig: Signal) -> dict:
    return {
        "enter": sig.enter, "direction": sig.direction,
        "entry_price": sig.entry_price, "stop_price": sig.stop_price,
        "target_price": sig.target_price, "reason": sig.reason,
    }


def exit_to_dict(ex: ExitSignal) -> dict:
    return {"exit": ex.exit, "exit_price": ex.exit_price, "reason": ex.reason}


def run_paper(strategy: Strategy, exchange_id: str, symbol: str, timeframe: str, poll_seconds: int = 60):
    """
    Main paper trading loop. Polls exchange every poll_seconds for new closed candle.
    Only evaluates on NEW closed candles (not the in-progress one).
    """
    print(f"[PAPER TRADER] starting")
    print(f"  strategy: {strategy.name}")
    print(f"  symbol:   {symbol} {timeframe}")
    print(f"  exchange: {exchange_id}")
    print(f"  poll:     every {poll_seconds}s")
    state_file = _state_path(strategy.name, symbol, timeframe)
    log_file = _log_path(strategy.name, symbol, timeframe)
    print(f"  state:    {state_file}")
    print(f"  log:      {log_file}")
    print(f"  Ctrl+C to stop. State persists — restart continues from where it left off.")
    print()

    state = load_state(state_file)
    print(f"  resuming: equity=${state['equity']:.2f}  trades={state['trade_count']}  open_trade={'yes' if state['open_trade'] else 'no'}")

    # Graceful shutdown
    def handle_sigint(sig, frame):
        print("\n[PAPER TRADER] stopping — saving state...")
        save_state(state, state_file)
        sys.exit(0)
    sig_module.signal(sig_module.SIGINT, handle_sigint)

    # Timeframe to seconds (for knowing when a new candle should appear)
    tf_seconds = {
        "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400,
    }.get(timeframe, 3600)

    while True:
        try:
            candles = fetch_latest_candles(exchange_id, symbol, timeframe, limit=300)
            df = to_dataframe(candles)
            # Only evaluate on CLOSED candles — exclude the last one (in progress)
            df_closed = df.iloc[:-1].copy()
            strategy.prepare(df_closed)

            latest_closed = df_closed.iloc[-1]
            latest_ts = latest_closed.name

            # Only process if this is a new candle we haven't seen
            ts_int = int(latest_ts.timestamp() * 1000)
            if ts_int <= state["last_candle_ts"]:
                # No new closed candle yet
                time.sleep(poll_seconds)
                continue

            state["last_candle_ts"] = ts_int

            # 1. Check open trade for stop/target hit on this candle
            if state["open_trade"]:
                hit, price, reason = check_stop_target(state["open_trade"], {
                    "high": latest_closed["high"], "low": latest_closed["low"],
                })
                if hit:
                    close_virtual_trade(state["open_trade"], price, str(latest_ts), reason, state, state_file, log_file)
                else:
                    # Ask strategy for exit signal
                    ex = strategy.evaluate(latest_closed, state["open_trade"])
                    if isinstance(ex, ExitSignal) and ex.exit:
                        close_virtual_trade(state["open_trade"], ex.exit_price, str(latest_ts), ex.reason, state, state_file, log_file)

            # 2. Check for new entry
            if not state["open_trade"]:
                sig = strategy.evaluate(latest_closed, None)
                if isinstance(sig, Signal) and sig.enter:
                    sig_d = signal_to_dict(sig)
                    # R:R gate (same as backtest)
                    risk = abs(sig.entry_price - sig.stop_price)
                    reward = abs(sig.target_price - sig.entry_price)
                    if risk > 0 and (reward / risk) >= 1.5:
                        open_virtual_trade(sig_d, {"datetime": str(latest_ts), "high": latest_closed["high"], "low": latest_closed["low"]}, state, state_file)
                    else:
                        print(f"  [PAPER SKIP] signal rejected — R:R below 1.5 gate")

            save_state(state, state_file)
            # Wait for next poll. For long timeframes, poll less frequently.
            time.sleep(min(poll_seconds, tf_seconds // 4))

        except (ccxt.NetworkError, ccxt.RequestTimeout) as e:
            print(f"  [PAPER WARN] network error: {e} — retrying in {poll_seconds}s")
            time.sleep(poll_seconds)
        except Exception as e:
            print(f"  [PAPER ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(poll_seconds)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("strategy", help="e.g. strategies.macd_ema200")
    p.add_argument("--symbol", default="BTC/USDT")
    p.add_argument("--timeframe", default="4h")
    p.add_argument("--exchange", default="binance")
    p.add_argument("--poll", type=int, default=120, help="seconds between polls")
    p.add_argument("--params", default=None, help="JSON string of strategy params")
    args = p.parse_args()

    mod = importlib.import_module(args.strategy)
    strategy_cls = None
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
            strategy_cls = obj
            break
    if not strategy_cls:
        print(f"No Strategy subclass found in {args.strategy}")
        sys.exit(1)

    params = json.loads(args.params) if args.params else None
    strategy = strategy_cls(params)

    run_paper(strategy, args.exchange, args.symbol, args.timeframe, args.poll)


if __name__ == "__main__":
    main()
