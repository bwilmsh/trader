"""
Trading bot web dashboard — pure Python stdlib HTTP server.
Serves a single-page dashboard + JSON API that reads from the bot's
existing data: backtest logs, learning log, paper trader state.

No third-party ASGI server needed — uses asyncio + raw HTTP.
Run:  python web_app.py  (starts on port 8776)
"""
import json
import glob
import os
import asyncio
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent
LOG_DIR = ROOT / "logs"
RESEARCH_DIR = ROOT / "research"

# ─── Data readers (fresh read every request — no caching) ──────────────

def _read_json(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None

def _load_backtest_logs():
    files = sorted(glob.glob(str(LOG_DIR / "*_BTCUSDT_*.json")))
    files = [f for f in files if "paper_" not in os.path.basename(f) and "sweep_" not in os.path.basename(f)]
    results = []
    for f in files:
        try:
            with open(f) as fh:
                data = json.load(fh)
            base = os.path.basename(f).replace(".json", "")
            if "BTCUSDT" in base:
                strategy_part, rest = base.split("BTCUSDT", 1)
                strategy = strategy_part.rstrip("_")
                tf = rest.strip("_").split("_")[0]
            else:
                strategy = base.split("_")[0]
                tf = ""
            data["_strategy"] = strategy
            data["_timeframe"] = tf
            data["_file"] = base
            results.append(data)
        except (json.JSONDecodeError, KeyError):
            continue
    return results

def _load_paper_states():
    files = sorted(glob.glob(str(LOG_DIR / "paper_state_*.json")))
    states = []
    for f in files:
        try:
            with open(f) as fh:
                data = json.load(fh)
            base = os.path.basename(f).replace("paper_state_", "").replace(".json", "")
            if "BTCUSDT" in base:
                strategy_part, rest = base.split("BTCUSDT", 1)
                strategy = strategy_part.rstrip("_")
                tf = rest.strip("_")
            else:
                strategy = base.split("_")[0]
                tf = ""
            data["_strategy"] = strategy
            data["_timeframe"] = tf
            states.append(data)
        except (json.JSONDecodeError, KeyError):
            continue
    return states

def _load_paper_trades():
    files = sorted(glob.glob(str(LOG_DIR / "paper_log_*.json")))
    all_trades = []
    for f in files:
        try:
            with open(f) as fh:
                trades = json.load(fh)
            base = os.path.basename(f).replace("paper_log_", "").replace(".json", "")
            if "BTCUSDT" in base:
                strategy = base.split("BTCUSDT")[0].rstrip("_")
            else:
                strategy = base.split("_")[0]
            for t in trades:
                t["_strategy"] = strategy
            all_trades.extend(trades)
        except (json.JSONDecodeError, KeyError):
            continue
    return all_trades

def _build_equity_curve(trades, initial_capital=1000.0):
    equity = initial_capital
    points = [{"trade": 0, "equity": equity, "pnl": 0}]
    for i, t in enumerate(trades, 1):
        equity += t.get("pnl_usd", 0)
        points.append({"trade": i, "equity": round(equity, 2), "pnl": round(t.get("pnl_usd", 0), 2)})
    return points

# ─── API handlers ──────────────────────────────────────────────────────

def handle_overview():
    backtests = _load_backtest_logs()
    paper_states = _load_paper_states()
    paper_trades = _load_paper_trades()
    valid = [b for b in backtests if b.get("total_trades", 0) > 0]
    valid.sort(key=lambda b: (b.get("expectancy_r", -9), b.get("rr_ratio", 0)), reverse=True)
    return {
        "backtests": valid,
        "paper_traders": paper_states,
        "paper_trade_count": len(paper_trades),
        "total_backtests": len(valid),
        "updated": datetime.now(timezone.utc).isoformat(),
    }

def handle_backtest_detail(query):
    strategy = query.get("strategy", [""])[0]
    timeframe = query.get("timeframe", [""])[0]
    backtests = _load_backtest_logs()
    matches = [b for b in backtests if b.get("_strategy", "").startswith(strategy) and b.get("_timeframe") == timeframe]
    if not matches:
        return {"error": "not found", "debug": {"strategy": strategy, "timeframe": timeframe, "count": len(backtests), "first": (backtests[0].get("_strategy"), backtests[0].get("_timeframe")) if backtests else None}}, 404
    latest = matches[-1]
    trades = latest.get("trades", [])
    equity_curve = _build_equity_curve(trades, latest.get("initial_capital", 1000.0))
    return {
        "metrics": {k: v for k, v in latest.items() if k != "trades"},
        "trades": trades,
        "equity_curve": equity_curve,
    }, 200

def handle_paper_trades():
    trades = _load_paper_trades()
    return {"trades": trades, "count": len(trades)}

def handle_paper_status():
    states = _load_paper_states()
    return {"traders": states}

def handle_health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

# ─── Dashboard HTML (same as before) ────────────────────────────────────
# (imported from a separate file to keep this readable)

DASHBOARD_HTML = open(ROOT / "web" / "dashboard.html").read()

# ─── HTTP server ────────────────────────────────────────────────────────

class HTTPRequestHandler:
    """Simple HTTP request handler for the dashboard API + static HTML."""
    
    def __init__(self, reader, writer, addr):
        self.reader = reader
        self.writer = writer
        self.addr = addr
    
    async def handle(self):
        try:
            request_line = await self.reader.readline()
            if not request_line:
                return
            parts = request_line.decode().strip().split()
            if len(parts) < 3:
                return
            method, path, version = parts[0], parts[1], parts[2]
            
            # Read headers
            headers = {}
            while True:
                header_line = await self.reader.readline()
                if header_line in (b"\r\n", b"\n", b""):
                    break
                h = header_line.decode().strip().split(":", 1)
                if len(h) == 2:
                    headers[h[0].strip()] = h[1].strip()
            
            # Parse path and query
            parsed = urllib.parse.urlparse(path)
            route = parsed.path
            query = urllib.parse.parse_qs(parsed.query)
            
            # Route the request
            status = 200
            content_type = "application/json"
            body = ""
            
            if route == "/" or route == "/dashboard":
                content_type = "text/html"
                body = DASHBOARD_HTML
            elif route == "/api/overview":
                body = json.dumps(handle_overview(), default=str)
            elif route == "/api/backtest":
                result, status = handle_backtest_detail(query)
                body = json.dumps(result, default=str)
            elif route == "/api/paper-trades":
                body = json.dumps(handle_paper_trades(), default=str)
            elif route == "/api/paper-status":
                body = json.dumps(handle_paper_status(), default=str)
            elif route == "/health":
                body = json.dumps(handle_health())
            else:
                status = 404
                body = json.dumps({"error": "not found"})
            
            # Send response
            response = (
                f"HTTP/1.1 {status} OK\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(body.encode())}\r\n"
                f"Access-Control-Allow-Origin: *\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            )
            self.writer.write(response.encode())
            self.writer.write(body.encode())
            await self.writer.drain()
        except Exception as e:
            print(f"  [HTTP] error from {addr}: {e}")
        finally:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except:
                pass

async def handle_client(reader, writer, addr=None):
    handler = HTTPRequestHandler(reader, writer, addr)
    await handler.handle()

async def start_server(port=8776, host="0.0.0.0"):
    # SO_REUSEADDR to avoid "address in use" after restart
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(128)
    
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w), sock=sock
    )
    print(f"Trading Bot Dashboard running on http://{host}:{port}")
    print(f"  Open: http://localhost:{port}")
    print(f"  (or http://134.199.151.198:{port} if port published)")
    print(f"  Ctrl+C to stop.")
    async with server:
        await server.serve_forever()

def run(port=8776):
    try:
        asyncio.run(start_server(port))
    except KeyboardInterrupt:
        print("\nStopping...")

if __name__ == "__main__":
    run()
