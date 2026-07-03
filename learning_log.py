#!/usr/bin/env python3
"""
Learning log — aggregates all backtest results into a ranked strategy league table.
Reads every JSON log in logs/, extracts the metrics, ranks by expectancy (R per trade)
then by R:R ratio, and writes a markdown summary + a JSON ranked file.

This is the "keep what works, kill what doesn't" system.
Run it after every batch of backtests.
"""
import json
import glob
from pathlib import Path
from datetime import datetime

LOG_DIR = Path(__file__).parent / "logs"
OUT_DIR = Path(__file__).parent / "research"


def load_all_results():
    files = sorted(glob.glob(str(LOG_DIR / "*.json")))
    results = []
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
        # The log file is either a single metrics dict or {"train": ..., "test": ...}
        if "train" in data and "test" in data:
            for split in ("train", "test"):
                m = data[split]
                m["source_file"] = f
                m["split"] = split
                results.append(m)
        else:
            data["source_file"] = f
            data["split"] = "full"
            results.append(data)
    return results


def rank(results):
    """Rank by expectancy (R per trade) desc, then R:R desc."""
    # Filter out zero-trade runs
    valid = [r for r in results if r.get("total_trades", 0) > 0]
    valid.sort(key=lambda r: (r.get("expectancy_r", -9), r.get("rr_ratio", 0)), reverse=True)
    return valid


def to_markdown(ranked):
    lines = [
        f"# Strategy League Table — Learning Log",
        f"",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}",
        f"Source: backtest logs in `logs/` (real Binance OHLCV, event-driven engine)",
        f"",
        f"Ranking: expectancy (R per trade) first, then R:R ratio. A strategy must pass the gate (expectancy > 0 AND R:R >= 1.5) to be a real contender.",
        f"",
        f"| Rank | Strategy | Split | Trades | Win% | Avg Win R | Avg Loss R | R:R | Expectancy (R) | Profit Factor | Max DD% | Passes Gate |",
        f"|------|----------|-------|--------|------|-----------|------------|-----|-----------------|---------------|--------|-------------|",
    ]
    for i, r in enumerate(ranked, 1):
        # Strategy name from filename: <name>_<symbol><timeframe>_<timestamp>.json
        import os
        base = os.path.basename(r["source_file"])
        # Try to extract strategy name from the file content if present, else from filename
        strat = r.get("strategy", "unknown")
        # Better: parse from filename
        parts = base.split("_")
        strat = parts[0] if parts else "unknown"
        split = r.get("split", "full")
        passes = "✅ YES" if r.get("passes_gate") else "❌ NO"
        lines.append(
            f"| {i} | {strat} | {split} | {r['total_trades']} | {r['win_rate_pct']:.1f}% | "
            f"+{r['avg_win_r']:.2f}R | {r['avg_loss_r']:.2f}R | {r['rr_ratio']:.2f} | "
            f"{r['expectancy_r']:+.3f}R | {r['profit_factor']:.2f} | {r['max_drawdown_pct']:.1f}% | {passes} |"
        )

    lines.append("")
    lines.append("## Strategy details")
    lines.append("")
    # Group by strategy name, show the best split for each
    seen = set()
    for r in ranked:
        import os
        base = os.path.basename(r["source_file"])
        parts = base.split("_")
        strat = parts[0] if parts else "unknown"
        if strat in seen:
            continue
        seen.add(strat)
        lines.append(f"### {strat}")
        lines.append(f"- Trades: {r['total_trades']} ({r['wins']}W / {r['losses']}L)")
        lines.append(f"- Win rate: {r['win_rate_pct']:.1f}%")
        lines.append(f"- R:R ratio: {r['rr_ratio']:.2f}  (avg win +{r['avg_win_r']:.2f}R / avg loss {r['avg_loss_r']:.2f}R)")
        lines.append(f"- Expectancy: {r['expectancy_r']:+.3f}R per trade")
        lines.append(f"- Profit factor: {r['profit_factor']:.2f}")
        lines.append(f"- Max drawdown: {r['max_drawdown_pct']:.1f}% (${r['max_drawdown_usd']:.2f})")
        lines.append(f"- Sharpe: {r['sharpe']:.2f}")
        lines.append(f"- Passes gate: {r['passes_gate']}")
        lines.append("")

    return "\n".join(lines)


def main():
    results = load_all_results()
    if not results:
        print("No backtest logs found in logs/. Run some backtests first.")
        return
    ranked = rank(results)
    md = to_markdown(ranked)

    out_md = OUT_DIR / "learning_log.md"
    out_md.parent.mkdir(exist_ok=True)
    with open(out_md, "w") as f:
        f.write(md)

    out_json = OUT_DIR / "learning_log.json"
    with open(out_json, "w") as f:
        json.dump(ranked, f, indent=2, default=str)

    print(f"Loaded {len(results)} backtest results from {len(set(r['source_file'] for r in results))} files")
    print(f"Ranked {len(ranked)} valid runs (non-zero trades)")
    print(f"Saved: {out_md}")
    print()
    print(md)


if __name__ == "__main__":
    main()
