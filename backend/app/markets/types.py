"""Core market value objects and enums."""
from __future__ import annotations
import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class AssetClass(str, enum.Enum):
    equity = "equity"
    crypto = "crypto"
    forex = "forex"
    futures = "futures"
    options = "options"
    commodity_cfd = "commodity_cfd"

    @classmethod
    def all(cls) -> list[str]:
        return [m.value for m in cls]


class OrderSide(str, enum.Enum):
    buy = "buy"
    sell = "sell"


class OrderType(str, enum.Enum):
    market = "market"
    limit = "limit"
    stop = "stop"
    stop_limit = "stop_limit"
    trailing_stop = "trailing_stop"


# ---------- Timeframe ----------
# Stored as canonical strings; the seconds map below drives resampling and
# sorting. We accept the common case-insensitive aliases via Timeframe.parse.
_TIMEFRAME_SECONDS: dict[str, int] = {
    "1s": 1, "5s": 5, "15s": 15,
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400,
    "1d": 86400, "1w": 604800, "1M": 2_592_000,  # 30-day "month" approximation
}


class Timeframe(str, enum.Enum):
    s1 = "1s"
    s5 = "5s"
    s15 = "15s"
    m1 = "1m"
    m5 = "5m"
    m15 = "15m"
    m30 = "30m"
    h1 = "1h"
    h4 = "4h"
    d1 = "1d"
    w1 = "1w"
    M1 = "1M"

    @property
    def seconds(self) -> int:
        return _TIMEFRAME_SECONDS[self.value]

    @classmethod
    def all(cls) -> list[str]:
        return [m.value for m in cls]

    @classmethod
    def parse(cls, value: str) -> "Timeframe":
        """Parse a user-supplied timeframe string. Case-insensitive for letters
        EXCEPT the month suffix which we keep as canonical `1M` to distinguish
        from minutes. Examples: '1d', '1D', '15M' (minutes), '1Mo' (month)."""
        if not value:
            raise ValueError("empty timeframe")
        v = value.strip()
        if v in _TIMEFRAME_SECONDS:
            return cls(v)
        # Allow common aliases
        low = v.lower()
        aliases = {
            "1min": "1m", "5min": "5m", "15min": "15m", "30min": "30m",
            "60m": "1h", "60min": "1h",
            "1hour": "1h", "4hour": "4h",
            "1day": "1d", "daily": "1d",
            "1week": "1w", "weekly": "1w",
            "1mo": "1M", "1mon": "1M", "monthly": "1M",
        }
        if low in aliases:
            return cls(aliases[low])
        # Lowercased canonical (excluding the 'M' month case)
        if low in _TIMEFRAME_SECONDS:
            return cls(low)
        raise ValueError(f"unknown timeframe: {value}")


@dataclass(frozen=True)
class Symbol:
    """Normalized symbol. Examples:
        Equity   : Symbol("equity", "AAPL", exchange="NASDAQ")
        Crypto   : Symbol("crypto", "BTC", quote="USD", exchange="coinbase")
        Forex    : Symbol("forex", "EUR", quote="USD")
        Futures  : Symbol("futures", "CL", expiry="2025-12", exchange="NYMEX")
        Options  : Symbol("options", "AAPL", expiry="2025-01-17", strike=200, right="C")
    """
    asset_class: str
    base: str
    quote: Optional[str] = None
    exchange: Optional[str] = None
    expiry: Optional[str] = None  # ISO date or YYYY-MM
    strike: Optional[float] = None
    right: Optional[str] = None  # 'C' | 'P' for options

    def canonical(self) -> str:
        """Canonical lossless string form used as cache key."""
        parts = [self.asset_class, self.base.upper()]
        if self.quote: parts.append(self.quote.upper())
        if self.exchange: parts.append(self.exchange.lower())
        if self.expiry: parts.append(self.expiry)
        if self.strike is not None: parts.append(f"{self.strike:g}")
        if self.right: parts.append(self.right.upper())
        return ":".join(parts)

    def display(self) -> str:
        """Human-readable display name."""
        if self.asset_class == AssetClass.crypto.value and self.quote:
            return f"{self.base.upper()}/{self.quote.upper()}"
        if self.asset_class == AssetClass.forex.value and self.quote:
            return f"{self.base.upper()}{self.quote.upper()}"
        if self.asset_class == AssetClass.options.value:
            return (f"{self.base.upper()} {self.expiry} "
                    f"{self.right or '?'}{self.strike or '?'}")
        if self.asset_class == AssetClass.futures.value and self.expiry:
            return f"{self.base.upper()} {self.expiry}"
        return self.base.upper()

    @classmethod
    def parse(cls, raw: str, default_asset_class: str = "equity") -> "Symbol":
        """Best-effort parser used when the UI/API submits a free-form string."""
        if not raw:
            raise ValueError("empty symbol")
        s = raw.strip().upper()
        # Crypto with slash: BTC/USD
        if "/" in s:
            base, quote = s.split("/", 1)
            return cls("crypto", base, quote)
        # 6-letter forex without separators: EURUSD
        if (default_asset_class == "forex" and len(s) == 6 and s.isalpha()):
            return cls("forex", s[:3], s[3:])
        return cls(default_asset_class, s)


@dataclass(frozen=True)
class Bar:
    """OHLCV bar."""
    ts: datetime          # bar start time, UTC
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    timeframe: str = "1d"


@dataclass(frozen=True)
class Quote:
    symbol: str
    ts: datetime
    last: float
    bid: Optional[float] = None
    ask: Optional[float] = None


@dataclass(frozen=True)
class NewsItem:
    ts: datetime
    headline: str
    summary: str = ""
    url: str = ""
    source: str = ""
    tickers: tuple[str, ...] = ()
    sentiment: Optional[float] = None  # -1..+1 if provider reports it


@dataclass(frozen=True)
class Fundamentals:
    """Equity-only. Free-form dict to avoid coupling to a particular vendor schema."""
    symbol: str
    data: dict = field(default_factory=dict)
