"""Abstract broker connector. Read methods + order methods. Read-only by default."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol


class BrokerError(Exception):
    pass


@dataclass
class BrokerOrder:
    broker_order_id: str
    status: str  # new/filled/cancelled/rejected
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    raw: dict = field(default_factory=dict)


@dataclass
class BrokerAccount:
    cash_cents: int
    positions: dict


class BrokerConnector(Protocol):
    """Implementations must be deterministic re: side effects (idempotency on place_order)."""

    def get_account(self) -> BrokerAccount: ...
    def get_last_price(self, symbol: str) -> float: ...
    def place_order(self, *, symbol: str, side: str, qty: float,
                    order_type: str = "market", limit_price: float | None = None,
                    idempotency_key: str) -> BrokerOrder: ...
    def cancel_order(self, broker_order_id: str) -> None: ...
