"""Markets package: asset classes, timeframes, symbols, data providers, features."""
from .types import (
    AssetClass, Timeframe, OrderType, OrderSide,
    Symbol, Bar, Quote, NewsItem, Fundamentals,
)
from .data_provider import (
    MarketDataProvider, ProviderCapabilities,
    register_provider, get_data_provider, list_data_providers,
)
from .features import FeatureBuilder, compute_features
from .resample import resample_bars

# Import built-in providers so they self-register.
from .providers import synthetic as _synthetic  # noqa: F401
from .providers import yahoo as _yahoo  # noqa: F401
from .providers import ccxt_provider as _ccxt  # noqa: F401

__all__ = [
    "AssetClass", "Timeframe", "OrderType", "OrderSide",
    "Symbol", "Bar", "Quote", "NewsItem", "Fundamentals",
    "MarketDataProvider", "ProviderCapabilities",
    "register_provider", "get_data_provider", "list_data_providers",
    "FeatureBuilder", "compute_features",
    "resample_bars",
]
