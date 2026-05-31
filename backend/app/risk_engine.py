"""Deterministic risk engine. NO LLM. Pure functions over (proposal, account, policy)."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal

Verdict = Literal["approved", "rejected", "requires_user_approval"]


@dataclass
class Proposal:
    symbol: str
    side: str  # buy / sell
    qty: float
    order_type: str = "market"
    limit_price: float | None = None


@dataclass
class AccountState:
    cash_cents: int
    positions: dict  # {symbol: {qty, avg_price}}
    realised_pnl_today_cents: int = 0


@dataclass
class RiskPolicy:
    automation: str                          # suggest | paper | live_manual | live_auto
    trade_scope: str                         # paper | live
    max_position_notional_cents: int = 5_000_00
    max_orders_per_run: int = 3
    allowed_symbols: list[str] = field(default_factory=list)   # empty => any
    org_daily_loss_limit_cents: int = 10_000_00
    org_kill_switch: bool = False
    risk_ack_accepted: bool = True
    price_hint: float = 0.0                  # best-known price for notional math


@dataclass
class RiskVerdict:
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate(proposal: Proposal, account: AccountState, policy: RiskPolicy,
             *, orders_already_this_run: int = 0, now: datetime | None = None) -> RiskVerdict:
    """Apply checks in order. Any HARD failure → rejected. Any SOFT failure → requires_user_approval.
    All checks pass + automation == live_manual → requires_user_approval. Else approved.
    """
    reasons: list[str] = []
    checks: dict = {}
    hard_fail = False
    soft_fail = False

    def hard(name: str, ok: bool, msg: str):
        nonlocal hard_fail
        checks[name] = bool(ok)
        if not ok:
            hard_fail = True
            reasons.append(f"HARD: {msg}")

    def soft(name: str, ok: bool, msg: str):
        nonlocal soft_fail
        checks[name] = bool(ok)
        if not ok:
            soft_fail = True
            reasons.append(f"SOFT: {msg}")

    # --- Hard checks: refuse outright ---
    hard("risk_ack_accepted", policy.risk_ack_accepted, "Org has not accepted risk disclaimer")
    hard("kill_switch_off", not policy.org_kill_switch, "Org kill-switch is engaged")
    hard("suggest_mode_no_orders", policy.automation != "suggest",
         "Agent is in suggest-only mode; no orders may be placed")
    hard("valid_side", proposal.side in ("buy", "sell"), f"Invalid side: {proposal.side}")
    hard("positive_qty", proposal.qty > 0, "Quantity must be positive")
    hard("valid_symbol", bool(proposal.symbol) and proposal.symbol.isascii(), "Invalid symbol")
    if policy.allowed_symbols:
        hard("symbol_in_allowlist", proposal.symbol.upper() in [s.upper() for s in policy.allowed_symbols],
             f"Symbol {proposal.symbol} not in agent allowlist")

    hard("orders_per_run", orders_already_this_run < policy.max_orders_per_run,
         f"Exceeded max_orders_per_run ({policy.max_orders_per_run})")
    hard("daily_loss_limit", account.realised_pnl_today_cents > -policy.org_daily_loss_limit_cents,
         f"Org daily loss limit hit ({policy.org_daily_loss_limit_cents} cents)")

    # Live trading requires live scope on broker
    if policy.automation in ("live_manual", "live_auto"):
        hard("live_scope_on_broker", policy.trade_scope == "live",
             "Live automation requires a broker connection with trade_scope=live")

    # --- Notional / cash check ---
    px = policy.price_hint or proposal.limit_price or 0.0
    notional_cents = int(round(px * proposal.qty * 100)) if px else 0
    checks["notional_cents"] = notional_cents
    if notional_cents:
        hard("max_position_notional", notional_cents <= policy.max_position_notional_cents,
             f"Order notional ({notional_cents}c) exceeds per-order cap "
             f"({policy.max_position_notional_cents}c)")
        if proposal.side == "buy":
            hard("sufficient_cash", notional_cents <= account.cash_cents,
                 f"Insufficient cash ({account.cash_cents}c) for notional ({notional_cents}c)")
        else:
            pos_qty = float(account.positions.get(proposal.symbol, {}).get("qty", 0))
            hard("sufficient_position", pos_qty >= proposal.qty,
                 f"Insufficient position to sell ({pos_qty} held, want {proposal.qty})")

    # --- Soft checks: would auto-execute become an approval prompt? ---
    # Large notional relative to cash → require human nod even in live_auto.
    if notional_cents and account.cash_cents > 0:
        ratio = notional_cents / account.cash_cents
        soft("notional_below_25pct_cash", ratio <= 0.25,
             f"Order is {ratio:.0%} of cash; requires explicit approval")

    if hard_fail:
        return RiskVerdict("rejected", reasons, checks)

    # Manual automation → always asks the human
    if policy.automation == "live_manual":
        if "Live automation: manual approval required" not in reasons:
            reasons.append("Live automation: manual approval required")
        return RiskVerdict("requires_user_approval", reasons, checks)

    if soft_fail:
        return RiskVerdict("requires_user_approval", reasons, checks)

    return RiskVerdict("approved", reasons or ["All checks passed"], checks)
