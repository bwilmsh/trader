#!/usr/bin/env python3
"""
Parameter sweep — runs a strategy across a grid of parameters and reports
the best combinations by expectancy. Used to tune strategies that are close
to the gate (like WaveTrend 4h at break-even) to find a positive edge.

Usage:
  python param_sweep.py strategies.wavetrend --symbol BTC/USDT --timeframe 4h --since 2024-01-01 --params-grid '{"oversold": [-60, -50, -40, -30], "stop_atr": [1.5, 2.0, 2.5, 3.0], "target_r": [1.5, 2.0, 2.5, 3.0]}'
"""
import sys
import json
import argparse
import importlib
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data.loader import load_ohlcv, to_dataframe
from backtest.engine import run_backtest, BacktestConfig
from backtest.metrics import BacktestMetrics
from strategies.base import Strategy


def main():
    p = argparse.ArgumentParser()
    p.add_argument("strategy", help="e.g. strategies.wavetrend")
    p.add_argument("--symbol", default="BTC/USDT")
    p.add_argument("--timeframe", default="4h")
    p.add_argument("--since", default="2024-01-01T00:00:00Z")
    p.add_argument("--capital", type=float, default=1000.0)
    p.add_argument("--params-grid", default=None, help="JSON dict of param → list of values")
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

    grid = json.loads(args.params_grid) if args.params_grid else {}
    if not grid:
        print("No params grid provided. Use --params-grid '{\"param\": [val1, val2, ...]}'")
        sys.exit(1)

    # Load data once — reuse for all runs
    print(f"Loading data {args.symbol} {args.timeframe} from {args.since[:10]}...")
    candles = load_ohlcv("binance", args.symbol, args.timeframe, args.since)
    df = to_dataframe(candles)
    print(f"  {len(df)} candles loaded. Running sweep...")

    # Build all param combinations
    keys = list(grid.keys())
    value_lists = [grid[k] for k in keys]
    combos = list(product(*value_lists))
    print(f"  {len(combos)} parameter combinations to test")

    config = BacktestConfig(initial_capital=args.capital)

    results = []
    for i, combo in enumerate(combos):
        params = dict(zip(keys, combo))
        strategy = strategy_cls(params)
        # Each run needs a fresh copy of df because prepare() mutates it
        df_copy = df.copy()
        try:
            metrics = run_backtest(df_copy, strategy, config)
            results.append({
                "params": params,
                "trades": metrics.total_trades,
                "win_rate": round(metrics.win_rate_pct, 1),
                "rr_ratio": round(metrics.rr_ratio, 2),
                "expectancy_r": round(metrics.expectancy_r, 4),
                "profit_factor": round(metrics.profit_factor, 2),
                "max_dd_pct": round(metrics.max_drawdown_pct, 1),
                "sharpe": round(metrics.sharpe_ratio, 2),
                "passes": metrics.passes_gate(),
                "final_capital": round(metrics.final_capital, 2),
            })
        except Exception as e:
            results.append({"params": params, "error": str(e)})

    # Sort by expectancy descending
    valid = [r for r in results if "error" not in r and r["trades"] > 0]
    valid.sort(key=lambda r: r["expectancy_r"], reverse=True)

    print(f"\n{'='*80}")
    print(f"PARAMETER SWEEP RESULTS — {strategy_cls.__name__}")
    print(f"  {args.symbol} {args.timeframe}, {len(combos)} combinations tested")
    print(f"{'='*80}")
    print(f"{'Rank':<5} {'Params':<50} {'Trades':<7} {'Win%':<6} {'R:R':<5} {'Exp(R)':<8} {'PF':<5} {'MaxDD%':<7} {'Pass'}")
    print(f"{'-'*110}")
    for i, r in enumerate(valid[:20], 1):  # top 20
        p_str = json.dumps(r["params"])
        passes = "✅" if r["passes"] else "❌"
        print(f"{i:<5} {p_str:<50} {r['trades']:<7} {r['win_rate']:<6} {r['rr_ratio']:<5} {r['expectancy_r']:<8} {r['profit_factor']:<5} {r['max_dd_pct']:<7} {passes}")

    # Show any that pass the gate
    gate_passers = [r for r in valid if r["passes"]]
    if gate_passers:
        print(f"\n{'='*80}")
        print(f"✅ {len(gate_passers)} combinations PASS the gate (positive expectancy + R:R >= 1.5):")
        for r in gate_passers:
            print(f"   {json.dumps(r['params'])}  →  +{r['expectancy_r']}R  R:R={r['rr_ratio']}  win={r['win_rate']}%  DD={r['max_dd_pct']}%")
    else:
        print(f"\n❌ No combinations pass the gate. Best result:")
        if valid:
            r = valid[0]
            print(f"   {json.dumps(r['params'])}  →  {r['expectancy_r']}R  R:R={r['rr_ratio']}  win={r['win_rate']}%" + ('' if not r.get('error') else f"  ERROR: {r['error']}"))

    # Save full results to JSON (convert numpy types to native Python)
    out_file = Path(__file__).parent / "logs" / f"sweep_{strategy_cls.__name__}_{args.symbol.replace('/', '')}_{args.timeframe}.json"
    serializable = []
    for r in valid:
        clean = {}
        for k, v in r.items():
            if hasattr(v, "item"):  # numpy scalar
                clean[k] = v.item()
            else:
                clean[k] = v
        serializable.append(clean)
    with open(out_file, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"\nFull results saved: {out_file}")


if __name__ == "__main__":
    main()
