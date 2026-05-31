"""MarketDataProvider protocol + provider registry.

Providers self-register on import via `register_provider`. The registry is
used by API endpoints to list options and by the agent runtime to fetch data.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional, Protocol, runtime_checkable

from .types import AssetClass, Bar, Fundamentals, NewsItem, Quote, Symbol, Timeframe


@dataclass
class ProviderCapabilities:
    code: str
    name: str
    asset_classes: list[str]                    # AssetClass values
    timeframes: list[str]                       # Timeframe values
    supports_quotes: bool = True
    supports_bars: bool = True
    supports_news: bool = False
    supports_fundamentals: bool = False
    supports_streaming: bool = False
    requires_credentials: bool = False
    cost_tier: str = "free"                     # free | freemium | paid
    notes: str = ""

    def to_dict(self) -> dict:
        d = {**self.__dict__}
        return d


@runtime_checkable
class MarketDataProvider(Protocol):
    capabilities: ProviderCapabilities

    def get_bars(self, symbol: Symbol, timeframe: Timeframe, start: datetime,
                 end: datetime) -> list[Bar]: ...

    def get_quote(self, symbol: Symbol) -> Quote: ...

    def get_news(self, symbol_or_topic: str, since: datetime,
                 limit: int = 25) -> list[NewsItem]: ...

    def get_fundamentals(self, symbol: Symbol) -> Optional[Fundamentals]: ...


# ---------- Registry ----------
_REGISTRY: dict[str, MarketDataProvider] = {}


def register_provider(provider: MarketDataProvider) -> None:
    code = provider.capabilities.code
    _REGISTRY[code] = provider


def get_data_provider(code: str) -> MarketDataProvider:
    if code not in _REGISTRY:
        raise KeyError(f"Unknown data provider: {code}. Available: {list(_REGISTRY)}")
    return _REGISTRY[code]


def list_data_providers() -> list[dict]:
    return [p.capabilities.to_dict() for p in _REGISTRY.values()]


def best_provider_for(asset_class: str, timeframe: str,
                      *, free_only: bool = True) -> Optional[MarketDataProvider]:
    """Pick a provider that supports the given asset class + timeframe.

    Prefers free providers when `free_only=True`. Returns None if nothing fits.
    """
    candidates = []
    for p in _REGISTRY.values():
        caps = p.capabilities
        if asset_class not in caps.asset_classes:
            continue
        if timeframe not in caps.timeframes:
            continue
        if free_only and caps.cost_tier != "free":
            continue
        candidates.append(p)
    if not candidates:
        return None
    # Prefer providers that don't require credentials.
    candidates.sort(key=lambda p: (p.capabilities.requires_credentials, p.capabilities.code))
    return candidates[0]


# Default no-op implementations to make Protocol structural matching easier for
# providers that only support a subset of methods.
class _NoNewsMixin:
    def get_news(self, symbol_or_topic: str, since: datetime,
                 limit: int = 25) -> list[NewsItem]:
        return []


class _NoFundamentalsMixin:
    def get_fundamentals(self, symbol: Symbol) -> Optional[Fundamentals]:
        return None
