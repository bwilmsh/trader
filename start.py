#!/usr/bin/env python3
"""
Start the trading bot — runs quick backtests to generate data, then starts the web dashboard.
Usage: python start.py
Then open: http://localhost:8776
"""
import subprocess, sys, os, time

os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("=" * 50)
print("  TRADING BOT — STARTING UP")
print("=" * 50)
print()

# 1. Quick backtests to generate dashboard data
print("Step 1/2: Running quick backtests (this takes ~30 seconds)...")
print("  Pulling real BTC data from Binance and backtesting strategies...")
print()

strategies = [
    ("strategies.supertrend",  "BTC/USDT", "1d", "2023-01-01T00:00:00Z"),
    ("strategies.macd_ema200", "BTC/USDT", "4h", "2024-01-01T00:00:00Z"),
    ("strategies.wavetrend",   "BTC/USDT", "4h", "2024-01-01T00:00:00Z",
     '{"oversold": -50, "stop_atr": 2.0, "target_r": 2.0}'),
    ("strategies.supertrend",  "BTC/USDT", "1h", "2024-01-01T00:00:00Z"),
    ("strategies.ut_bot",      "BTC/USDT", "1h", "2024-01-01T00:00:00Z"),
    ("strategies.rsi2_mr",     "BTC/USDT", "1h", "2024-01-01T00:00:00Z"),
]

for s in strategies:
    cmd = [sys.executable, "run_backtest.py", s[0],
           "--symbol", s[1], "--timeframe", s[2], "--since", s[3]]
    if len(s) > 4:
        cmd.extend(["--params", s[4]])
    print(f"  → {s[0].split('.')[-1]} {s[2]}...", end=" ", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        # Extract the expectancy line from output
        for line in result.stdout.split("\n"):
            if "Expectancy" in line:
                print(line.strip())
                break
        else:
            print("done")
    else:
        print(f"error: {result.stderr[-100:]}")
    time.sleep(0.5)

print()
print("  Backtests done. Dashboard data ready.")
print()

# 2. Generate learning log
print("  Generating league table...", end=" ", flush=True)
subprocess.run([sys.executable, "learning_log.py"], capture_output=True, timeout=10)
print("done")
print()

# 3. Start web dashboard
print("Step 2/2: Starting web dashboard on port 8776...")
print("  → http://localhost:8776")
print("  → Ctrl+C to stop")
print("=" * 50)
print()

os.execv(sys.executable, [sys.executable, "-u", "web_app.py"])
