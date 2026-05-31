"""Yahoo Finance provider (lazy import of yfinance).

If yfinance is not installed or a call fails, the provider degrades gracefully
to the synthetic provider so the platform keeps working offline.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from ..data_provider import MarketDataProvider, ProviderCapabilities, register_provider
from ..types import AssetClass, Bar, Fundamentals, NewsItem, Quote, Symbol, Timeframe


_YF_INTERVAL = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "60m", "1d": "1d", "1w": "1wk", "1M": "1mo",
}


def _yf_symbol(s: Symbol) -> str:
    """Map our Symbol → yahoo ticker."""
    if s.asset_class == AssetClass.crypto.value:
        # BTC-USD style
        return f"{s.base.upper()}-{(s.quote or 'USD').upper()}"
    if s.asset_class == AssetClass.forex.value:
        # EURUSD=X
        return f"{s.base.upper()}{(s.quote or 'USD').upper()}=X"
    if s.asset_class == AssetClass.futures.value:
        # Use base; assumes user passes e.g. "CL=F" via base.
        if "=" in s.base:
            return s.base.upper()
        return f"{s.base.upper()}=F"
    return s.base.upper()


def _try_import_yf():
    try:
        import yfinance as yf  # type: ignore
        return yf
    except Exception:
        return None


class YahooProvider:
    capabilities = ProviderCapabilities(
        code="yahoo",
        name="Yahoo Finance (free)",
        asset_classes=[AssetClass.equity.value, AssetClass.crypto.value,
                       AssetClass.forex.value, AssetClass.futures.value],
        timeframes=list(_YF_INTERVAL.keys()),
        supports_quotes=True,
        supports_bars=True,
        supports_news=False,
        supports_fundamentals=True,
        supports_streaming=False,
        requires_credentials=False,
        cost_tier="free",
        notes="Free, delayed equity data (~15min). For dev only; not for production trading.",
    )

    def _fallback(self):
        # Lazy import to avoid circulars at module load.
        from .synthetic import SyntheticProvider
        return SyntheticProvider()

    def get_bars(self, symbol: Symbol, timeframe: Timeframe, start: datetime,
                 end: datetime) -> list[Bar]:
        yf = _try_import_yf()
        tf = timeframe if isinstance(timeframe, Timeframe) else Timeframe.parse(timeframe)
        if yf is None or tf.value not in _YF_INTERVAL:
            return self._fallback().get_bars(symbol, tf, start, end)
        try:
            t = yf.Ticker(_yf_symbol(symbol))
            df = t.history(start=start, end=end, interval=_YF_INTERVAL[tf.value],
                           auto_adjust=False, actions=False)
            bars: list[Bar] = []
            for ts, row in df.iterrows():
                bars.append(Bar(
                    ts=ts.to_pydatetime().replace(tzinfo=None),
                    open=float(row["Open"]), high=float(row["High"]),
                    low=float(row["Low"]), close=float(row["Close"]),
                    volume=float(row.get("Volume", 0) or 0),
                    timeframe=tf.value,
                ))
            return bars
        except Exception:
            return self._fallback().get_bars(symbol, tf, start, end)

    def get_quote(self, symbol: Symbol) -> Quote:
        yf = _try_import_yf()
        if yf is None:
            return self._fallback().get_quote(symbol)
        try:
            t = yf.Ticker(_yf_symbol(symbol))
            info = t.fast_info if hasattr(t, "fast_info") else {}
            last = float(info.get("last_price") or info.get("regularMarketPrice") or 0) or 0.0
            if last == 0.0:
                hist = t.history(period="1d", interval="1d")
                if len(hist):
                    last = float(hist["Close"].iloc[-1])
            return Quote(symbol=symbol.canonical(), ts=datetime.utcnow(), last=last)
        except Exception:
            return self._fallback().get_quote(symbol)

    def get_news(self, symbol_or_topic: str, since: datetime,
                 limit: int = 25) -> list[NewsItem]:
        return []

    def get_fundamentals(self, symbol: Symbol) -> Optional[Fundamentals]:
        if symbol.asset_class != AssetClass.equity.value:
            return None
        yf = _try_import_yf()
        if yf is None:
            return self._fallback().get_fundamentals(symbol)
        try:
            t = yf.Ticker(_yf_symbol(symbol))
            info = t.info if hasattr(t, "info") else {}
            return Fundamentals(symbol=symbol.canonical(), data={
                "pe": info.get("trailingPE"),
                "eps_ttm": info.get("trailingEps"),
                "market_cap": info.get("marketCap"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
            })
        except Exception:
            return self._fallback().get_fundamentals(symbol)


register_provider(YahooProvider())
