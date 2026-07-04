#!/usr/bin/env python3
"""
Live trader — places REAL orders on Binance when live_trading is true.
Same logic as paper_trader.py but sends real exchange orders instead of logging virtual trades.

SAFETY:
  - live_trading must be true in config/config.yaml
  - Hard caps enforced regardless of strategy: max position size, daily loss limit, max open trades
  - Reads API keys from .env file (BINANCE_API_KEY, BINANCE_API_SECRET)
  - Logs every real trade to logs/live_trade_log.json

Usage:
  python live_trader.py strategies.macd_ema200 --symbol BTC/USDT --timeframe 4h
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

ROOT = Path(__file__).parent
CONFIG_FILE = ROOT / "config" / "config.yaml"
LIVE_LOG = ROOT / "logs" / "live_trade_log.json"


def load_config():
    if CONFIG_FILE.exists():
        import yaml
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f)
    return {}


def _state_path(strategy_name, symbol, timeframe):
    safe = f"{strategy_name}_{symbol.replace('/', '')}_{timeframe}"
    return ROOT / "logs" / f"live_state_{safe}.json"


def load_state(state_file):
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {
        "open_trade": None, "equity": 1000.0,
        "trade_count": 0, "last_candle_ts": 0,
        "daily_pnl": 0.0, "daily_pnl_date": "",
        "trading_halted": False,
    }


def save_state(state, state_file):
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2, default=str)


def append_live_trade(trade_dict):
    log = []
    if LIVE_LOG.exists():
        with open(LIVE_LOG) as f:
            log = json.load(f)
    log.append(trade_dict)
    with open(LIVE_LOG, "w") as f:
        json.dump(log, f, indent=2, default=str)


def load_api_keys():
    """Load Binance API keys from .env file."""
    env_file = ROOT / ".env"
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")

    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("BINANCE_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                elif line.startswith("BINANCE_API_SECRET="):
                    api_secret = line.split("=", 1)[1].strip()

    return api_key, api_secret


def create_exchange(api_key, api_secret, testnet=False):
    """Create a ccxt exchange instance with API keys."""
    exchange = ccxt.binance({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
    })
    if testnet:
        exchange.set_sandbox_mode(True)
    return exchange


def place_market_buy(exchange, symbol, usd_amount):
    """Place a real market buy order. Returns the order dict."""
    # Convert USD to base currency amount
    ticker = exchange.fetch_ticker(symbol)
    price = ticker["last"]
    base_amount = usd_amount / price
    # Binance requires specific precision — use ccxt's amount_to_precision
    base_amount = exchange.amount_to_precision(symbol, base_amount)
    order = exchange.create_market_buy_order(symbol, base_amount)
    return order, float(price)


def place_market_sell(exchange, symbol, base_amount):
    """Place a real market sell order. Returns the order dict."""
    base_amount = exchange.amount_to_precision(symbol, base_amount)
    ticker = exchange.fetch_ticker(symbol)
    price = ticker["last"]
    order = exchange.create_market_sell_order(symbol, base_amount)
    return order, float(price)


def check_daily_reset(state):
    """Reset daily PnL counter if it's a new day."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("daily_pnl_date", "") != today:
        state["daily_pnl"] = 0.0
        state["daily_pnl_date"] = today
        state["trading_halted"] = False
    return state


def run_live(strategy, config, exchange_id="binance", symbol="BTC/USDT", timeframe="4h", poll_seconds=900):
    """
    Main live trading loop. Same structure as paper trader but places REAL orders.
    """
    live_cfg = config.get("live_trading", False)
    if not live_cfg:
        print("[LIVE TRADER] ❌ live_trading is FALSE in config. Not starting.")
        print("  To enable: set live_trading: true in config/config.yaml")
        print("  And create .env with BINANCE_API_KEY and BINANCE_API_SECRET")
        return

    max_position = config.get("live_max_position_usd", 50.0)
    daily_loss_limit = config.get("live_daily_loss_limit", 25.0)
    max_open = config.get("live_max_open_trades", 3)

    api_key, api_secret = load_api_keys()
    if not api_key or not api_secret:
        print("[LIVE TRADER] ❌ No API keys found.")
        print("  Create a .env file with:")
        print("    BINANCE_API_KEY=your_key_here")
        print("    BINANCE_API_SECRET=your_secret_here")
        return

    # Check if we should use testnet
    testnet = config.get("testnet", False)
    exchange = create_exchange(api_key, api_secret, testnet)

    # Verify API keys work
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance.get("USDT", {}).get("free", 0)
        print(f"[LIVE TRADER] ✅ API keys valid. USDT balance: ${usdt_balance:.2f}")
    except Exception as e:
        print(f"[LIVE TRADER] ❌ API key check failed: {e}")
        return

    mode = "TESTNET" if testnet else "🔴 LIVE REAL MONEY"
    print(f"[LIVE TRADER] starting — {mode}")
    print(f"  strategy: {strategy.name}")
    print(f"  symbol:   {symbol} {timeframe}")
    print(f"  caps:      max ${max_position}/position, ${daily_loss_limit} daily loss, {max_open} max open")
    print(f"  poll:     every {poll_seconds}s")
    print(f"  Ctrl+C to stop. State persists.")
    print()

    state_file = _state_path(strategy.name, symbol, timeframe)
    state = load_state(state_file)
    print(f"  resuming: equity=${state['equity']:.2f}  trades={state['trade_count']}  "
          f"halted={state.get('trading_halted', False)}")

    def handle_sigint(sig, frame):
        print("\n[LIVE TRADER] stopping — saving state...")
        save_state(state, state_file)
        sys.exit(0)
    sig_module.signal(sig_module.SIGINT, handle_sigint)

    tf_seconds = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}.get(timeframe, 3600)

    while True:
        try:
            state = check_daily_reset(state)

            # Check if trading is halted due to daily loss limit
            if state.get("trading_halted", False):
                print(f"  [HALTED] daily loss limit reached (${state.get('daily_pnl', 0):.2f}). Waiting for new day.")
                time.sleep(poll_seconds)
                continue

            # Fetch latest candles
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=300)
            candles = [
                {
                    "timestamp": c[0],
                    "datetime": datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc).isoformat(),
                    "open": float(c[1]), "high": float(c[2]),
                    "low": float(c[3]), "close": float(c[4]), "volume": float(c[5]),
                }
                for c in ohlcv
            ]
            df = to_dataframe(candles)
            df_closed = df.iloc[:-1].copy()
            strategy.prepare(df_closed)

            latest_closed = df_closed.iloc[-1]
            latest_ts = latest_closed.name
            ts_int = int(latest_ts.timestamp() * 1000)

            if ts_int <= state["last_candle_ts"]:
                time.sleep(poll_seconds)
                continue

            state["last_candle_ts"] = ts_int

            # 1. Check open trade for exit
            if state["open_trade"]:
                open_trade = state["open_trade"]
                # Check stop/target
                hit_stop = False
                hit_target = False
                exit_price = 0.0
                exit_reason = ""

                if open_trade["direction"] == "long":
                    if latest_closed["low"] <= open_trade["stop_price"]:
                        hit_stop = True
                        exit_price = open_trade["stop_price"]
                        exit_reason = "stop hit"
                    elif latest_closed["high"] >= open_trade["target_price"]:
                        hit_target = True
                        exit_price = open_trade["target_price"]
                        exit_reason = "target hit"
                else:
                    if latest_closed["high"] >= open_trade["stop_price"]:
                        hit_stop = True
                        exit_price = open_trade["stop_price"]
                        exit_reason = "stop hit"
                    elif latest_closed["low"] <= open_trade["target_price"]:
                        hit_target = True
                        exit_price = open_trade["target_price"]
                        exit_reason = "target hit"

                # Check strategy exit signal
                if not hit_stop and not hit_target:
                    ex = strategy.evaluate(latest_closed, open_trade)
                    if isinstance(ex, ExitSignal) and ex.exit:
                        hit_stop = True
                        exit_price = ex.exit_price
                        exit_reason = ex.reason

                if hit_stop or hit_target:
                    # PLACE REAL SELL ORDER
                    base_amount = open_trade["position_size_base"]
                    print(f"  [LIVE SELL] {open_trade['direction']} {base_amount} {symbol} — {exit_reason}")
                    order, fill_price = place_market_sell(exchange, symbol, base_amount)

                    # Calculate PnL
                    direction_factor = 1 if open_trade["direction"] == "long" else -1
                    gross = (fill_price - open_trade["entry_price"]) * direction_factor * base_amount
                    fees = (open_trade["entry_price"] * base_amount * 0.001) + (fill_price * base_amount * 0.001)
                    net = gross - fees
                    initial_risk = base_amount * abs(open_trade["entry_price"] - open_trade["stop_price"])
                    r_mult = net / initial_risk if initial_risk > 0 else 0

                    trade = {
                        "entry_time": open_trade["entry_time"],
                        "exit_time": str(latest_ts),
                        "direction": open_trade["direction"],
                        "entry_price": open_trade["entry_price"],
                        "exit_price": fill_price,
                        "stop_price": open_trade["stop_price"],
                        "target_price": open_trade["target_price"],
                        "position_size_usd": open_trade["position_size_usd"],
                        "position_size_base": base_amount,
                        "pnl_usd": net,
                        "r_multiple": r_mult,
                        "win": net > 0,
                        "reason": exit_reason,
                        "mode": "LIVE",
                        "order_id": order.get("id", ""),
                    }
                    append_live_trade(trade)

                    state["equity"] += net
                    state["trade_count"] += 1
                    state["daily_pnl"] += net
                    state["open_trade"] = None

                    print(f"  [LIVE CLOSE] PnL: ${net:+.2f} ({r_mult:+.2f}R) — equity=${state['equity']:.2f}")
                    print(f"    daily PnL: ${state['daily_pnl']:.2f} (limit: -${daily_loss_limit})")

                    # Check daily loss limit
                    if state["daily_pnl"] <= -daily_loss_limit:
                        state["trading_halted"] = True
                        print(f"  ⚠️  DAILY LOSS LIMIT HIT — trading halted until tomorrow")

            # 2. Check for new entry
            if not state["open_trade"] and not state.get("trading_halted", False):
                sig = strategy.evaluate(latest_closed, None)
                if isinstance(sig, Signal) and sig.enter:
                    # R:R gate
                    risk = abs(sig.entry_price - sig.stop_price)
                    reward = abs(sig.target_price - sig.entry_price)
                    if risk > 0 and (reward / risk) >= 1.5:
                        # Cap position size
                        stop_dist = abs(sig.entry_price - sig.stop_price) / sig.entry_price
                        risk_usd = min(state["equity"] * 0.01, max_position * stop_dist)
                        pos_usd = min(risk_usd / stop_dist, max_position)

                        if pos_usd < 10:  # Binance minimum order
                            print(f"  [SKIP] position too small (${pos_usd:.2f})")
                        else:
                            # PLACE REAL BUY ORDER
                            print(f"  [LIVE BUY] {sig.direction} ${pos_usd:.2f} {symbol}")
                            print(f"    stop={sig.stop_price:.2f}  target={sig.target_price:.2f}")
                            print(f"    reason: {sig.reason}")
                            order, fill_price = place_market_buy(exchange, symbol, pos_usd)
                            base_amount = pos_usd / fill_price

                            state["open_trade"] = {
                                "entry_time": str(latest_ts),
                                "direction": sig.direction,
                                "entry_price": fill_price,
                                "stop_price": sig.stop_price,
                                "target_price": sig.target_price,
                                "position_size_usd": pos_usd,
                                "position_size_base": base_amount,
                                "reason": sig.reason,
                                "order_id": order.get("id", ""),
                            }
                            print(f"  [LIVE OPEN] filled @ {fill_price:.2f} — order {order.get('id', '')}")
                    else:
                        print(f"  [SKIP] R:R below 1.5 gate")

            save_state(state, state_file)
            time.sleep(min(poll_seconds, tf_seconds // 4))

        except (ccxt.NetworkError, ccxt.RequestTimeout) as e:
            print(f"  [WARN] network error: {e} — retrying in {poll_seconds}s")
            time.sleep(poll_seconds)
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(poll_seconds)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("strategy", help="e.g. strategies.macd_ema200")
    p.add_argument("--symbol", default="BTC/USDT")
    p.add_argument("--timeframe", default="4h")
    p.add_argument("--poll", type=int, default=900)
    p.add_argument("--params", default=None)
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
    config = load_config()

    run_live(strategy, config, "binance", args.symbol, args.timeframe, args.poll)


if __name__ == "__main__":
    main()
