"""Synthetic offline data provider.

Deterministic OHLCV generator seeded by symbol. Useful for tests, demos and
as a fallback when no real data provider is configured. Supports every
asset class and timeframe.
"""
from __future__ import annotations
import hashlib
import math
import random
from datetime import datetime, timedelta
from typing import Optional

from ..data_provider import MarketDataProvider, ProviderCapabilities, register_provider
from ..types import (
    AssetClass, Bar, Fundamentals, NewsItem, Quote, Symbol, Timeframe,
)


def _seed(symbol: Symbol) -> int:
    return int(hashlib.sha256(symbol.canonical().encode()).hexdigest(), 16) % (2 ** 31)


def _base_price(symbol: Symbol) -> float:
    s = _seed(symbol)
    # Different bases per asset class so synthetic prices are plausible.
    if symbol.asset_class == AssetClass.crypto.value:
        return 100 + (s % 60_000)
    if symbol.asset_class == AssetClass.forex.value:
        return 0.5 + (s % 200) / 100.0
    if symbol.asset_class == AssetClass.futures.value:
        return 30 + (s % 100)
    if symbol.asset_class == AssetClass.options.value:
        return 1 + (s % 50) / 10.0
    if symbol.asset_class == AssetClass.commodity_cfd.value:
        return 20 + (s % 200)
    return 10 + (s % 490)  # equity


class SyntheticProvider:
    capabilities = ProviderCapabilities(
        code="synthetic",
        name="Synthetic (offline)",
        asset_classes=AssetClass.all(),
        timeframes=Timeframe.all(),
        supports_quotes=True,
        supports_bars=True,
        supports_news=True,
        supports_fundamentals=True,
        supports_streaming=False,
        requires_credentials=False,
        cost_tier="free",
        notes="Deterministic synthetic data for offline development & tests.",
    )

    def get_bars(self, symbol: Symbol, timeframe: Timeframe, start: datetime,
                 end: datetime) -> list[Bar]:
        tf = timeframe if isinstance(timeframe, Timeframe) else Timeframe.parse(timeframe)
        if end <= start:
            return []
        secs = tf.seconds
        base = _base_price(symbol)
        seed = _seed(symbol)
        rng = random.Random(seed)
        n = min(5000, int((end - start).total_seconds() // secs) + 1)
        bars: list[Bar] = []
        # Walk a deterministic OHLC path.
        price = base
        for i in range(n):
            ts = start + timedelta(seconds=secs * i)
            # gentle sinusoidal drift + jittered noise; vol higher for crypto
            vol_amp = 0.04 if symbol.asset_class == AssetClass.crypto.value else 0.015
            drift = math.sin((ts.timestamp() / max(secs, 60)) / 25 + seed % 17) * base * 0.005
            shock = rng.uniform(-vol_amp, vol_amp) * price
            new_price = max(0.01, price + drift + shock)
            o = price
            c = new_price
            h = max(o, c) * (1 + abs(rng.uniform(0, vol_amp / 4)))
            l = min(o, c) * (1 - abs(rng.uniform(0, vol_amp / 4)))
            v = rng.uniform(100, 10_000) if symbol.asset_class != AssetClass.options.value else rng.uniform(1, 200)
            bars.append(Bar(ts=ts, open=round(o, 6), high=round(h, 6),
                            low=round(l, 6), close=round(c, 6),
                            volume=round(v, 2), timeframe=tf.value))
            price = c
        return bars

    def get_quote(self, symbol: Symbol) -> Quote:
        # Use the last "1m" bar from "now-1min..now" as a stable quote.
        now = datetime.utcnow().replace(microsecond=0)
        bars = self.get_bars(symbol, Timeframe.m1, now - timedelta(minutes=2), now)
        last = bars[-1].close if bars else _base_price(symbol)
        spread = max(0.01, last * 0.0005)
        return Quote(symbol=symbol.canonical(), ts=now, last=last,
                     bid=round(last - spread, 6), ask=round(last + spread, 6))

    def get_news(self, symbol_or_topic: str, since: datetime,
                 limit: int = 25) -> list[NewsItem]:
        rng = random.Random(hashlib.sha256(symbol_or_topic.encode()).hexdigest())
        items: list[NewsItem] = []
        topics = ["earnings beat", "analyst upgrade", "supply chain note",
                  "macro update", "regulatory update", "sector rotation"]
        for i in range(min(limit, 5)):
            items.append(NewsItem(
                ts=since + timedelta(hours=i + 1),
                headline=f"{symbol_or_topic.upper()}: {rng.choice(topics)}",
                summary="Synthetic placeholder news item for offline development.",
                url="",
                source="synthetic",
                tickers=(symbol_or_topic.upper(),),
                sentiment=round(rng.uniform(-0.5, 0.5), 2),
            ))
        return items

    def get_fundamentals(self, symbol: Symbol) -> Optional[Fundamentals]:
        if symbol.asset_class != AssetClass.equity.value:
            return None
        s = _seed(symbol)
        return Fundamentals(symbol=symbol.canonical(), data={
            "pe": round(8 + (s % 40), 2),
            "eps_ttm": round(0.5 + (s % 80) / 10.0, 2),
            "market_cap": (s % 1_000_000) * 1_000_000,
            "sector": ["Tech", "Energy", "Finance", "Health", "Consumer"][s % 5],
        })


register_provider(SyntheticProvider())
