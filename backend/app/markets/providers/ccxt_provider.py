"""ccxt-based crypto data provider (lazy import).

Wraps ~100 crypto exchanges through ccxt. Falls back to synthetic if ccxt is
not installed or the API call fails.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from ..data_provider import MarketDataProvider, ProviderCapabilities, register_provider
from ..types import AssetClass, Bar, Fundamentals, NewsItem, Quote, Symbol, Timeframe


_CCXT_TF = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w", "1M": "1M",
}


def _try_import_ccxt():
    try:
        import ccxt  # type: ignore
        return ccxt
    except Exception:
        return None


def _ccxt_symbol(s: Symbol) -> str:
    return f"{s.base.upper()}/{(s.quote or 'USDT').upper()}"


class CcxtProvider:
    capabilities = ProviderCapabilities(
        code="ccxt",
        name="ccxt (crypto, multi-exchange)",
        asset_classes=[AssetClass.crypto.value],
        timeframes=list(_CCXT_TF.keys()),
        supports_quotes=True,
        supports_bars=True,
        supports_news=False,
        supports_fundamentals=False,
        supports_streaming=False,
        requires_credentials=False,
        cost_tier="free",
        notes="Default exchange: binance. Configure via env or per-connection in future.",
    )

    def __init__(self, exchange: str = "binance"):
        self.exchange_name = exchange
        self._ex = None

    def _ex_or_none(self):
        if self._ex is not None:
            return self._ex
        ccxt = _try_import_ccxt()
        if ccxt is None:
            return None
        try:
            self._ex = getattr(ccxt, self.exchange_name)({"enableRateLimit": True})
            return self._ex
        except Exception:
            return None

    def _fallback(self):
        from .synthetic import SyntheticProvider
        return SyntheticProvider()

    def get_bars(self, symbol: Symbol, timeframe: Timeframe, start: datetime,
                 end: datetime) -> list[Bar]:
        ex = self._ex_or_none()
        tf = timeframe if isinstance(timeframe, Timeframe) else Timeframe.parse(timeframe)
        if ex is None or tf.value not in _CCXT_TF or symbol.asset_class != AssetClass.crypto.value:
            return self._fallback().get_bars(symbol, tf, start, end)
        try:
            since_ms = int(start.timestamp() * 1000)
            raw = ex.fetch_ohlcv(_ccxt_symbol(symbol), timeframe=_CCXT_TF[tf.value],
                                 since=since_ms, limit=1000)
            out: list[Bar] = []
            end_ms = int(end.timestamp() * 1000)
            for ts_ms, o, h, l, c, v in raw:
                if ts_ms > end_ms:
                    break
                out.append(Bar(ts=datetime.utcfromtimestamp(ts_ms / 1000),
                               open=float(o), high=float(h), low=float(l),
                               close=float(c), volume=float(v),
                               timeframe=tf.value))
            return out
        except Exception:
            return self._fallback().get_bars(symbol, tf, start, end)

    def get_quote(self, symbol: Symbol) -> Quote:
        ex = self._ex_or_none()
        if ex is None or symbol.asset_class != AssetClass.crypto.value:
            return self._fallback().get_quote(symbol)
        try:
            t = ex.fetch_ticker(_ccxt_symbol(symbol))
            return Quote(symbol=symbol.canonical(), ts=datetime.utcnow(),
                         last=float(t.get("last") or 0.0),
                         bid=float(t.get("bid") or 0.0) or None,
                         ask=float(t.get("ask") or 0.0) or None)
        except Exception:
            return self._fallback().get_quote(symbol)

    def get_news(self, symbol_or_topic: str, since: datetime, limit: int = 25):
        return []

    def get_fundamentals(self, symbol: Symbol) -> Optional[Fundamentals]:
        return None


register_provider(CcxtProvider())
