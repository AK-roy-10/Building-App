"""Deterministic backtester.

Replays a list of Bar through a strategy-like callable. The callable receives
the bars-up-to-now and returns a list of (side, qty) decisions per bar. The
backtester tracks a single-symbol position, computes P&L, win rate, max
drawdown and trade count.

This is intentionally minimal: it's the foundation for richer backtesting
(multi-symbol, slippage models, fees), not a full quant framework.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional

from .types import Bar


Decision = tuple[str, float]  # ("buy"|"sell"|"hold", qty)


@dataclass
class BacktestResult:
    n_bars: int
    n_trades: int
    starting_cash: float
    ending_equity: float
    pnl: float
    pnl_pct: float
    max_drawdown_pct: float
    win_rate: float
    trades: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {**self.__dict__}


def run_backtest(
    bars: list[Bar],
    decide: Callable[[list[Bar]], Optional[Decision]],
    *,
    starting_cash: float = 100_000.0,
    fee_bps: float = 5.0,
) -> BacktestResult:
    if not bars:
        return BacktestResult(0, 0, starting_cash, starting_cash, 0.0, 0.0, 0.0, 0.0)

    cash = starting_cash
    qty = 0.0
    avg_cost = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = []
    realized_wins = 0
    realized_trades = 0

    for i, b in enumerate(bars):
        window = bars[: i + 1]
        decision = decide(window) or ("hold", 0.0)
        side, dq = decision
        px = b.close
        if side == "buy" and dq > 0:
            cost = px * dq * (1 + fee_bps / 1e4)
            if cost <= cash:
                # Update average cost basis
                new_qty = qty + dq
                avg_cost = (avg_cost * qty + px * dq) / new_qty if new_qty else 0.0
                qty = new_qty
                cash -= cost
                trades.append({"i": i, "side": "buy", "qty": dq, "price": px, "cash_after": cash})
        elif side == "sell" and dq > 0 and qty >= dq:
            proceeds = px * dq * (1 - fee_bps / 1e4)
            realized_pnl = (px - avg_cost) * dq
            realized_trades += 1
            if realized_pnl > 0:
                realized_wins += 1
            qty -= dq
            if qty == 0:
                avg_cost = 0.0
            cash += proceeds
            trades.append({"i": i, "side": "sell", "qty": dq, "price": px,
                           "cash_after": cash, "realized_pnl": realized_pnl})
        # mark-to-market equity
        equity = cash + qty * px
        equity_curve.append(equity)

    ending = equity_curve[-1]
    pnl = ending - starting_cash
    pnl_pct = pnl / starting_cash if starting_cash else 0.0
    # Max drawdown
    peak = equity_curve[0]
    max_dd = 0.0
    for e in equity_curve:
        if e > peak:
            peak = e
        dd = (peak - e) / peak if peak else 0.0
        if dd > max_dd:
            max_dd = dd
    win_rate = (realized_wins / realized_trades) if realized_trades else 0.0
    return BacktestResult(
        n_bars=len(bars), n_trades=len(trades),
        starting_cash=starting_cash, ending_equity=ending,
        pnl=pnl, pnl_pct=pnl_pct,
        max_drawdown_pct=max_dd, win_rate=win_rate,
        trades=trades[-100:],  # cap so the response stays small
    )
