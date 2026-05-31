"""In-process paper broker. State is persisted on the BrokerConnection row.

Uses a deterministic synthetic price generator so the system runs offline.
"""
from __future__ import annotations
import hashlib
import math
from datetime import datetime
from sqlalchemy.orm import Session

from .. import models
from .base import BrokerConnector, BrokerOrder, BrokerAccount, BrokerError


def _synthetic_price(symbol: str, now: datetime | None = None) -> float:
    """Stable, deterministic-ish price between ~$10 and ~$500 based on symbol + minute."""
    now = now or datetime.utcnow()
    seed = int(hashlib.sha256(symbol.upper().encode()).hexdigest(), 16) % 1000
    base = 10 + (seed % 490)
    # gentle sinusoidal drift per-minute, also seeded by symbol
    t = now.timestamp() / 60.0
    drift = math.sin(t / (5 + seed % 30) + seed) * (base * 0.02)
    return round(base + drift, 2)


class PaperBroker(BrokerConnector):
    def __init__(self, db: Session, conn: models.BrokerConnection):
        self.db = db
        self.conn = conn

    def get_account(self) -> BrokerAccount:
        return BrokerAccount(cash_cents=self.conn.cash_cents, positions=dict(self.conn.positions_json or {}))

    def get_last_price(self, symbol: str) -> float:
        return _synthetic_price(symbol)

    def place_order(self, *, symbol: str, side: str, qty: float,
                    order_type: str = "market", limit_price: float | None = None,
                    idempotency_key: str) -> BrokerOrder:
        if qty <= 0:
            raise BrokerError("qty must be positive")
        symbol = symbol.upper()
        price = limit_price or self.get_last_price(symbol)
        cost_cents = int(round(price * qty * 100))
        positions = dict(self.conn.positions_json or {})

        if side == "buy":
            if cost_cents > self.conn.cash_cents:
                raise BrokerError("Insufficient paper cash")
            self.conn.cash_cents -= cost_cents
            pos = positions.get(symbol, {"qty": 0.0, "avg_price": 0.0})
            new_qty = pos["qty"] + qty
            new_avg = ((pos["qty"] * pos["avg_price"]) + (qty * price)) / new_qty if new_qty else 0.0
            positions[symbol] = {"qty": new_qty, "avg_price": round(new_avg, 4)}
        elif side == "sell":
            pos = positions.get(symbol, {"qty": 0.0, "avg_price": 0.0})
            if pos["qty"] < qty:
                raise BrokerError("Insufficient paper position")
            pos["qty"] -= qty
            if pos["qty"] <= 1e-9:
                positions.pop(symbol, None)
            else:
                positions[symbol] = pos
            self.conn.cash_cents += cost_cents
        else:
            raise BrokerError(f"Unknown side: {side}")

        self.conn.positions_json = positions
        self.db.add(self.conn)
        self.db.flush()

        return BrokerOrder(
            broker_order_id=f"paper-{idempotency_key[:12]}",
            status="filled",
            filled_qty=qty,
            avg_fill_price=price,
            raw={"engine": "paper", "price_used": price},
        )

    def cancel_order(self, broker_order_id: str) -> None:
        # Paper orders fill immediately; nothing to cancel.
        return None
