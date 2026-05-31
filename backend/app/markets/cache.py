"""Simple SQLAlchemy-backed cache for OHLCV bars.

Key: (provider_code, symbol_canonical, timeframe, ts). Insertions are
idempotent (UPSERT via merge-by-key). Reads use a single SQL query and return
a list[Bar] sorted by ts.
"""
from __future__ import annotations
from datetime import datetime
from typing import Iterable

from sqlalchemy import String, Integer, Float, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, Session

from ..database import Base
from .types import Bar, Symbol, Timeframe


class MarketBar(Base):
    __tablename__ = "market_bars"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    symbol: Mapped[str] = mapped_column(String(120), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    __table_args__ = (
        UniqueConstraint("provider", "symbol", "timeframe", "ts", name="uq_market_bars"),
        Index("ix_market_bars_lookup", "provider", "symbol", "timeframe", "ts"),
    )


def cache_bars(db: Session, provider_code: str, symbol: Symbol,
               timeframe: Timeframe | str, bars: Iterable[Bar]) -> int:
    tf = timeframe.value if isinstance(timeframe, Timeframe) else timeframe
    sym = symbol.canonical()
    inserted = 0
    for b in bars:
        existing = (db.query(MarketBar)
                    .filter_by(provider=provider_code, symbol=sym,
                               timeframe=tf, ts=b.ts).one_or_none())
        if existing:
            existing.open = b.open; existing.high = b.high
            existing.low = b.low;   existing.close = b.close
            existing.volume = b.volume
        else:
            db.add(MarketBar(provider=provider_code, symbol=sym, timeframe=tf,
                             ts=b.ts, open=b.open, high=b.high, low=b.low,
                             close=b.close, volume=b.volume))
            inserted += 1
    db.commit()
    return inserted


def load_cached_bars(db: Session, provider_code: str, symbol: Symbol,
                     timeframe: Timeframe | str,
                     start: datetime, end: datetime) -> list[Bar]:
    tf = timeframe.value if isinstance(timeframe, Timeframe) else timeframe
    rows = (db.query(MarketBar)
            .filter(MarketBar.provider == provider_code,
                    MarketBar.symbol == symbol.canonical(),
                    MarketBar.timeframe == tf,
                    MarketBar.ts >= start, MarketBar.ts <= end)
            .order_by(MarketBar.ts.asc()).all())
    return [Bar(ts=r.ts, open=r.open, high=r.high, low=r.low,
                close=r.close, volume=r.volume, timeframe=r.timeframe)
            for r in rows]
