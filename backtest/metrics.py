"""
Metrics — computes the real performance numbers for a backtest.
Win rate, R:R, expectancy, max drawdown, profit factor, Sharpe.
These are the numbers that decide if a strategy leaves paper mode.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class TradeResult:
    """One closed trade. Long or short."""
    entry_time: object       # datetime
    exit_time: object
    direction: str           # "long" or "short"
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    position_size_usd: float # actual USD notional
    pnl_usd: float           # realized PnL after fees
    pnl_pct: float
    r_multiple: float        # pnl / initial_risk (1R = amount risked)
    bars_held: int
    win: bool


@dataclass
class BacktestMetrics:
    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_trades: int
    wins: int
    losses: int
    win_rate_pct: float
    avg_win_r: float         # in R multiples
    avg_loss_r: float
    rr_ratio: float           # avg win / avg loss (absolute, in R)
    expectancy_r: float      # E[R] per trade = win%*avg_win_R - loss%*avg_loss_R
    profit_factor: float      # gross win / gross loss
    max_drawdown_pct: float
    max_drawdown_usd: float
    sharpe_ratio: float
    trades: List[TradeResult] = field(default_factory=list)

    def passes_gate(self, rr_min: float = 1.5, expectancy_min: float = 0.0) -> bool:
        """Does this strategy meet the minimum bar to be considered real?"""
        return self.expectancy_r > expectancy_min and self.rr_ratio >= rr_min

    def summary(self) -> str:
        return (
            f"Capital:     ${self.initial_capital:,.0f} → ${self.final_capital:,.2f}\n"
            f"Return:       {self.total_return_pct:+.2f}%\n"
            f"Trades:       {self.total_trades}  ({self.wins}W / {self.losses}L)\n"
            f"Win rate:     {self.win_rate_pct:.1f}%\n"
            f"Avg win:      +{self.avg_win_r:.2f}R\n"
            f"Avg loss:     {self.avg_loss_r:.2f}R\n"
            f"R:R ratio:    {self.rr_ratio:.2f}\n"
            f"Expectancy:   {self.expectancy_r:+.3f}R per trade\n"
            f"Profit factor: {self.profit_factor:.2f}\n"
            f"Max DD:       {self.max_drawdown_pct:.1f}%  (${self.max_drawdown_usd:.2f})\n"
            f"Sharpe:       {self.sharpe_ratio:.2f}\n"
            f"Passes gate:  {self.passes_gate()}\n"
        )


def compute_metrics(trades: List[TradeResult], initial_capital: float) -> BacktestMetrics:
    """Run the numbers on a list of closed trades."""
    if not trades:
        return BacktestMetrics(
            initial_capital=initial_capital, final_capital=initial_capital,
            total_return_pct=0.0, total_trades=0, wins=0, losses=0,
            win_rate_pct=0.0, avg_win_r=0.0, avg_loss_r=0.0, rr_ratio=0.0,
            expectancy_r=0.0, profit_factor=0.0, max_drawdown_pct=0.0,
            max_drawdown_usd=0.0, sharpe_ratio=0.0, trades=[],
        )

    wins = [t for t in trades if t.win]
    losses = [t for t in trades if not t.win]

    # Capital curve: walk through trades tracking equity
    equity = initial_capital
    peak = equity
    max_dd_usd = 0.0
    max_dd_pct = 0.0
    equities = []

    for t in trades:
        equity += t.pnl_usd
        equities.append(equity)
        if equity > peak:
            peak = equity
        dd_usd = peak - equity
        if dd_usd > max_dd_usd:
            max_dd_usd = dd_usd
            max_dd_pct = (dd_usd / peak * 100.0) if peak > 0 else 0.0

    final_capital = equity
    total_return = ((final_capital - initial_capital) / initial_capital) * 100.0

    win_rate = len(wins) / len(trades) * 100.0
    avg_win_r = sum(t.r_multiple for t in wins) / len(wins) if wins else 0.0
    avg_loss_r = sum(t.r_multiple for t in losses) / len(losses) if losses else 0.0

    # R:R ratio — average win size vs average loss size, in R multiples
    avg_win_abs = abs(avg_win_r)
    avg_loss_abs = abs(avg_loss_r)
    rr_ratio = avg_win_abs / avg_loss_abs if avg_loss_abs > 0 else float("inf")

    # Expectancy in R per trade
    win_frac = len(wins) / len(trades)
    loss_frac = len(losses) / len(trades)
    expectancy_r = win_frac * avg_win_r + loss_frac * avg_loss_r

    # Profit factor
    gross_win = sum(t.pnl_usd for t in wins)
    gross_loss = abs(sum(t.pnl_usd for t in losses))
    profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf")

    # Sharpe (per-trade, annualized assumes ~8k0 trades/yr for 1h tf on 24/7 crypto)
    import numpy as np
    returns_per_trade = [t.pnl_usd / initial_capital for t in trades]
    if len(returns_per_trade) > 1 and np.std(returns_per_trade) > 0:
        sharpe = np.mean(returns_per_trade) / np.std(returns_per_trade)
        # annualize: sqrt(trades_per_year). 1h tf on crypto = ~8,760 bars/yr. Assume 1 trade/bar max → 8,760.
        # Use actual trade count vs time span if possible, else default.
        trades_per_year = 8760
        sharpe_annual = sharpe * np.sqrt(trades_per_year)
    else:
        sharpe_annual = 0.0

    return BacktestMetrics(
        initial_capital=initial_capital, final_capital=final_capital,
        total_return_pct=total_return, total_trades=len(trades),
        wins=len(wins), losses=len(losses), win_rate_pct=win_rate,
        avg_win_r=avg_win_r, avg_loss_r=avg_loss_r, rr_ratio=rr_ratio,
        expectancy_r=expectancy_r, profit_factor=profit_factor,
        max_drawdown_pct=max_dd_pct, max_drawdown_usd=max_dd_usd,
        sharpe_ratio=sharpe_annual, trades=trades,
    )
