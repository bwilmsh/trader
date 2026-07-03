"""
Data loader — pulls historical OHLCV data from crypto exchanges via ccxt.
Caches to disk so backtests don't re-download on every run.
"""
import os
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import ccxt

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(exchange_id, symbol, timeframe, since):
    raw = f"{exchange_id}|{symbol}|{timeframe}|{since}"
    return hashlib.md5(raw.encode()).hexdigest() + ".json"


def load_ohlcv(
    exchange_id: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    since: str = "2023-01-01T00:00:00Z",
    limit_per_fetch: int = 1000,
    max_retries: int = 3,
) -> list[dict]:
    """
    Fetch OHLCV candles from exchange, with disk caching.
    Returns list of dicts: [{timestamp, open, high, low, close, volume}, ...]
    """
    cache_file = CACHE_DIR / _cache_key(exchange_id, symbol, timeframe, since)
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    exchange = getattr(ccxt, exchange_id)({"enableRateLimit": True})

    since_ms = int(
        datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp() * 1000
    )
    now_ms = int(time.time() * 1000)

    all_candles = []
    cursor = since_ms

    for attempt in range(max_retries):
        while cursor < now_ms:
            try:
                batch = exchange.fetch_ohlcv(
                    symbol, timeframe, since=cursor, limit=limit_per_fetch
                )
            except (ccxt.NetworkError, ccxt.DDoSProtection, ccxt.RequestTimeout) as e:
                if attempt == max_retries - 1:
                    raise
                print(f"  retry {attempt+1}/{max_retries} after error: {e}")
                time.sleep(2 ** attempt * 2)
                continue

            if not batch:
                break

            all_candles.extend(batch)
            cursor = batch[-1][0] + 1  # +1 ms to avoid dup

            # Respect rate limit
            time.sleep(exchange.rateLimit / 1000)

        if all_candles:
            break

    # Convert to dicts
    formatted = [
        {
            "timestamp": c[0],
            "datetime": datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc).isoformat(),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]),
        }
        for c in all_candles
    ]

    # Dedupe (in case of overlap) and sort
    seen = {}
    unique = []
    for c in formatted:
        if c["timestamp"] not in seen:
            seen[c["timestamp"]] = True
            unique.append(c)
    unique.sort(key=lambda x: x["timestamp"])

    with open(cache_file, "w") as f:
        json.dump(unique, f)

    print(f"  loaded {len(unique)} candles {symbol} {timeframe} from {since[:10]}")
    return unique


def to_dataframe(candles: list[dict]):
    """Convert candle dicts to a pandas DataFrame with datetime index."""
    import pandas as pd

    df = pd.DataFrame(candles)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    return df[["open", "high", "low", "close", "volume"]]
