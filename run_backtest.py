#!/usr/bin/env python3
"""
Main runner. Usage:
  python run_backtest.py <strategy_module> [--symbol BTC/USDT] [--timeframe 1h] [--since 2023-01-01]

Example:
  python run_backtest.py strategies.ema_cross
"""
import sys
import argparse
import importlib
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from data.loader import load_ohlcv, to_dataframe
from backtest.engine import run_backtest, BacktestConfig, run_walk_forward
from backtest.metrics import BacktestMetrics
from strategies.base import Strategy


LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("strategy", help="e.g. strategies.ema_cross (module path)")
    p.add_argument("--symbol", default="BTC/USDT")
    p.add_argument("--timeframe", default="1h")
    p.add_argument("--since", default="2023-01-01T00:00:00Z")
    p.add_argument("--capital", type=float, default=1000.0)
    p.add_argument("--walk-forward", action="store_true", help="split train/test")
    p.add_argument("--params", default=None, help="JSON string of strategy params")
    args = p.parse_args()

    # Import strategy module
    mod = importlib.import_module(args.strategy)
    # Find the Strategy subclass in the module
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

    print(f"Strategy: {strategy.name}")
    print(f"Symbol:   {args.symbol} {args.timeframe} from {args.since[:10]}")
    print(f"Loading data...")

    candles = load_ohlcv("binance", args.symbol, args.timeframe, args.since)
    df = to_dataframe(candles)

    print(f"Data: {len(df)} candles, {df.index[0]} to {df.index[-1]}")

    config = BacktestConfig(initial_capital=args.capital)

    if args.walk_forward:
        train_m, test_m = run_walk_forward(df, strategy, config)
        all_metrics = {"train": _metrics_dict(train_m), "test": _metrics_dict(test_m)}
    else:
        metrics = run_backtest(df, strategy, config)
        print()
        print("=" * 50)
        print(metrics.summary())
        all_metrics = _metrics_dict(metrics)

    # Save trade log + metrics
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{strategy.name}_{args.symbol.replace('/', '')}_{args.timeframe}_{timestamp}.json"
    with open(log_file, "w") as f:
        json.dump(all_metrics, f, indent=2, default=str)
    print(f"Log saved: {log_file}")


def _metrics_dict(m: BacktestMetrics) -> dict:
    return {
        "strategy": m.trades[0].direction if m.trades else "none",
        "initial_capital": m.initial_capital,
        "final_capital": m.final_capital,
        "total_return_pct": m.total_return_pct,
        "total_trades": m.total_trades,
        "wins": m.wins,
        "losses": m.losses,
        "win_rate_pct": m.win_rate_pct,
        "avg_win_r": m.avg_win_r,
        "avg_loss_r": m.avg_loss_r,
        "rr_ratio": m.rr_ratio,
        "expectancy_r": m.expectancy_r,
        "profit_factor": m.profit_factor,
        "max_drawdown_pct": m.max_drawdown_pct,
        "max_drawdown_usd": m.max_drawdown_usd,
        "sharpe": m.sharpe_ratio,
        "passes_gate": m.passes_gate(),
        "trades": [
            {
                "entry_time": str(t.entry_time), "exit_time": str(t.exit_time),
                "direction": t.direction, "entry_price": t.entry_price,
                "exit_price": t.exit_price, "stop_price": t.stop_price,
                "target_price": t.target_price, "position_size_usd": t.position_size_usd,
                "pnl_usd": t.pnl_usd, "r_multiple": t.r_multiple, "win": t.win,
            } for t in m.trades
        ],
    }


if __name__ == "__main__":
    main()
