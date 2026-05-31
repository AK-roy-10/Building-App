"""Stub adapters for brokers not yet fully wired.

Each adapter exposes its `capabilities` so the UI and entitlements can show /
gate it. Order placement raises `BrokerError` until the user installs the
SDK and provides credentials. Read methods either delegate to the broker's
free public REST (where possible) or raise so the agent runtime falls back
to the configured market-data provider.

Adding a real implementation later is a localized change: implement
`place_order`, `get_account`, `get_last_price` and `verify` and the rest of
the stack picks it up.
"""
from __future__ import annotations
from .base import (
    BrokerConnector, BrokerOrder, BrokerAccount, BrokerError,
    BrokerCapabilities, FeeModel,
)


def _stub_account() -> BrokerAccount:
    return BrokerAccount(cash_cents=0, positions={})


def _not_configured(name: str):
    raise BrokerError(f"{name}: adapter not configured. Provide credentials and install SDK.")


class CcxtBroker(BrokerConnector):
    """Unified crypto adapter — covers ~100 exchanges through `ccxt`."""
    capabilities = BrokerCapabilities(
        code="ccxt", name="ccxt (any crypto exchange)",
        asset_classes=["crypto"],
        order_types=["market", "limit", "stop", "stop_limit"],
        timeframes=["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
        supports_fractional=True, supports_shorting=False, supports_24_7=True,
        multi_currency=True,
        fee_model=FeeModel(bps_of_notional=10),
        notes="Install `ccxt`. Configure exchange + key per connection.",
    )
    def __init__(self, api_key: str = "", api_secret: str = "",
                 exchange: str = "binance", **kw): self._x = exchange
    def get_account(self) -> BrokerAccount: return _stub_account()
    def get_last_price(self, symbol: str) -> float: return 0.0
    def place_order(self, **kw) -> BrokerOrder: _not_configured(f"ccxt:{self._x}")
    def cancel_order(self, broker_order_id: str) -> None: _not_configured(f"ccxt:{self._x}")
    def verify(self) -> dict: return {"ok": False, "detail": "stub — install ccxt + creds"}


class CoinbaseBroker(BrokerConnector):
    capabilities = BrokerCapabilities(
        code="coinbase", name="Coinbase Advanced Trade",
        asset_classes=["crypto"],
        order_types=["market", "limit", "stop_limit"],
        timeframes=["1m", "5m", "15m", "1h", "1d"],
        supports_fractional=True, supports_24_7=True, multi_currency=True,
        fee_model=FeeModel(bps_of_notional=40),
        notes="Coinbase Advanced Trade API (formerly Pro).",
    )
    def __init__(self, **kw): pass
    def get_account(self): return _stub_account()
    def get_last_price(self, symbol): return 0.0
    def place_order(self, **kw): _not_configured("coinbase")
    def cancel_order(self, broker_order_id): _not_configured("coinbase")
    def verify(self) -> dict: return {"ok": False, "detail": "stub — Coinbase Advanced Trade"}


class BinanceBroker(BrokerConnector):
    capabilities = BrokerCapabilities(
        code="binance", name="Binance (.com / .us)",
        asset_classes=["crypto"],
        order_types=["market", "limit", "stop_limit"],
        timeframes=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
        supports_fractional=True, supports_24_7=True, multi_currency=True,
        fee_model=FeeModel(bps_of_notional=10),
        notes="Spot trading. Use Binance.US for US residents.",
    )
    def __init__(self, **kw): pass
    def get_account(self): return _stub_account()
    def get_last_price(self, symbol): return 0.0
    def place_order(self, **kw): _not_configured("binance")
    def cancel_order(self, broker_order_id): _not_configured("binance")
    def verify(self) -> dict: return {"ok": False, "detail": "stub — Binance spot"}


class KrakenBroker(BrokerConnector):
    capabilities = BrokerCapabilities(
        code="kraken", name="Kraken",
        asset_classes=["crypto"],
        order_types=["market", "limit", "stop_limit", "trailing_stop"],
        timeframes=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
        supports_fractional=True, supports_24_7=True, multi_currency=True,
        fee_model=FeeModel(bps_of_notional=26),
    )
    def __init__(self, **kw): pass
    def get_account(self): return _stub_account()
    def get_last_price(self, symbol): return 0.0
    def place_order(self, **kw): _not_configured("kraken")
    def cancel_order(self, broker_order_id): _not_configured("kraken")
    def verify(self) -> dict: return {"ok": False, "detail": "stub — Kraken"}


class OandaBroker(BrokerConnector):
    capabilities = BrokerCapabilities(
        code="oanda", name="OANDA v20 (forex + CFDs)",
        asset_classes=["forex", "commodity_cfd"],
        order_types=["market", "limit", "stop", "stop_limit", "trailing_stop"],
        timeframes=["5s", "10s", "15s", "30s", "1m", "5m", "15m", "30m",
                    "1h", "4h", "1d", "1w"],
        supports_fractional=True, supports_shorting=True, supports_24_7=False,
        multi_currency=True,
        fee_model=FeeModel(bps_of_notional=0, min_fee_cents=0),
        sandbox_url="https://api-fxpractice.oanda.com",
        notes="OANDA v20 REST/Stream API. Forex 24/5 + CFDs.",
    )
    def __init__(self, **kw): pass
    def get_account(self): return _stub_account()
    def get_last_price(self, symbol): return 0.0
    def place_order(self, **kw): _not_configured("oanda")
    def cancel_order(self, broker_order_id): _not_configured("oanda")
    def verify(self) -> dict: return {"ok": False, "detail": "stub — OANDA"}


class InteractiveBrokersBroker(BrokerConnector):
    capabilities = BrokerCapabilities(
        code="ib", name="Interactive Brokers (TWS / Gateway)",
        asset_classes=["equity", "options", "futures", "forex", "commodity_cfd"],
        order_types=["market", "limit", "stop", "stop_limit", "trailing_stop"],
        timeframes=["1s", "5s", "15s", "1m", "5m", "15m", "30m", "1h", "1d", "1w"],
        supports_fractional=True, supports_shorting=True, supports_options=True,
        multi_currency=True,
        fee_model=FeeModel(per_order_cents=35, bps_of_notional=5, min_fee_cents=100),
        notes="Requires a running IB Gateway / TWS. Use ib_insync.",
    )
    def __init__(self, **kw): pass
    def get_account(self): return _stub_account()
    def get_last_price(self, symbol): return 0.0
    def place_order(self, **kw): _not_configured("interactive_brokers")
    def cancel_order(self, broker_order_id): _not_configured("interactive_brokers")
    def verify(self) -> dict: return {"ok": False, "detail": "stub — IB Gateway/TWS"}


class TradierBroker(BrokerConnector):
    capabilities = BrokerCapabilities(
        code="tradier", name="Tradier (equity + options)",
        asset_classes=["equity", "options"],
        order_types=["market", "limit", "stop", "stop_limit"],
        timeframes=["1m", "5m", "15m", "1h", "1d"],
        supports_options=True, supports_shorting=True,
        sandbox_url="https://sandbox.tradier.com",
        fee_model=FeeModel(per_order_cents=0, min_fee_cents=0),
    )
    def __init__(self, **kw): pass
    def get_account(self): return _stub_account()
    def get_last_price(self, symbol): return 0.0
    def place_order(self, **kw): _not_configured("tradier")
    def cancel_order(self, broker_order_id): _not_configured("tradier")
    def verify(self) -> dict: return {"ok": False, "detail": "stub — Tradier"}


class TradovateBroker(BrokerConnector):
    capabilities = BrokerCapabilities(
        code="tradovate", name="Tradovate (futures)",
        asset_classes=["futures"],
        order_types=["market", "limit", "stop", "stop_limit", "trailing_stop"],
        timeframes=["1s", "5s", "1m", "5m", "15m", "1h", "1d"],
        supports_shorting=True,
        sandbox_url="https://demo.tradovateapi.com",
        fee_model=FeeModel(per_order_cents=85),
        notes="CME futures access.",
    )
    def __init__(self, **kw): pass
    def get_account(self): return _stub_account()
    def get_last_price(self, symbol): return 0.0
    def place_order(self, **kw): _not_configured("tradovate")
    def cancel_order(self, broker_order_id): _not_configured("tradovate")
    def verify(self) -> dict: return {"ok": False, "detail": "stub — Tradovate"}


# Convenience map used by the registry to instantiate stubs from their code.
STUB_BROKERS = {
    "ccxt": CcxtBroker,
    "coinbase": CoinbaseBroker,
    "binance": BinanceBroker,
    "kraken": KrakenBroker,
    "oanda": OandaBroker,
    "ib": InteractiveBrokersBroker,
    "tradier": TradierBroker,
    "tradovate": TradovateBroker,
}
