"""Abstract broker connector. Read methods + order methods.

Each connector declares its `BrokerCapabilities` (supported asset classes,
order types, market-data timeframes, fractional/shorting/24-7, fee model).
The risk engine + UI use this metadata to gate what an agent may do.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable


class BrokerError(Exception):
    pass


@dataclass
class BrokerOrder:
    broker_order_id: str
    status: str  # new/accepted/partially_filled/filled/canceled/rejected
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    raw: dict = field(default_factory=dict)


@dataclass
class BrokerAccount:
    cash_cents: int                       # base currency (USD default)
    positions: dict                       # {symbol: {qty, avg_price}}
    multi_currency_cash: dict = field(default_factory=dict)  # {ccy: cents}


@dataclass
class FeeModel:
    """Cost per trade approximation. Pricing differs by broker — keep it simple."""
    per_order_cents: int = 0
    bps_of_notional: float = 0.0          # basis points (1 bps = 0.01%)
    min_fee_cents: int = 0


@dataclass
class BrokerCapabilities:
    code: str
    name: str
    asset_classes: list[str]              # AssetClass values
    order_types: list[str] = field(default_factory=lambda: ["market", "limit"])
    timeframes: list[str] = field(default_factory=list)  # for own data (if any)
    supports_fractional: bool = False
    supports_shorting: bool = False
    supports_24_7: bool = False
    supports_options: bool = False
    multi_currency: bool = False
    fee_model: FeeModel = field(default_factory=FeeModel)
    sandbox_url: Optional[str] = None
    requires_credentials: bool = True
    notes: str = ""
    enabled: bool = True                  # set False for adapters that are pure stubs

    def to_dict(self) -> dict:
        d = {**self.__dict__}
        d["fee_model"] = self.fee_model.__dict__
        return d


@runtime_checkable
class BrokerConnector(Protocol):
    """Implementations must be deterministic re: side effects (idempotency on place_order)."""

    capabilities: BrokerCapabilities

    def get_account(self) -> BrokerAccount: ...
    def get_last_price(self, symbol: str) -> float: ...
    def place_order(self, *, symbol: str, side: str, qty: float,
                    order_type: str = "market", limit_price: float | None = None,
                    idempotency_key: str) -> BrokerOrder: ...
    def cancel_order(self, broker_order_id: str) -> None: ...

    def verify(self) -> dict:
        """Return {ok: bool, detail: str, account?: {...}} for a quick health check."""
        ...

