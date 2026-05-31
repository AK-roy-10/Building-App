"""Timeframe resampling. UP-only: e.g. 1m bars → 5m bars.

Never down-samples (would require finer data we don't have).
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Iterable

from .types import Bar, Timeframe


def _floor_to(ts: datetime, seconds: int) -> datetime:
    epoch = int(ts.replace(tzinfo=None).timestamp())
    floored = (epoch // seconds) * seconds
    return datetime.utcfromtimestamp(floored)


def resample_bars(bars: Iterable[Bar], target: Timeframe | str) -> list[Bar]:
    """Aggregate finer bars into coarser bars (OHLCV).

    Raises ValueError if `target` is finer than the input bars or if input bars
    have mixed timeframes.
    """
    tf = target if isinstance(target, Timeframe) else Timeframe.parse(target)
    bars_list = sorted(bars, key=lambda b: b.ts)
    if not bars_list:
        return []
    src_tf = bars_list[0].timeframe
    src_secs = Timeframe.parse(src_tf).seconds
    tgt_secs = tf.seconds
    if any(b.timeframe != src_tf for b in bars_list):
        raise ValueError("resample_bars: input bars have mixed timeframes")
    if tgt_secs < src_secs:
        raise ValueError(f"resample_bars: target {tf.value} is finer than source {src_tf}")
    if tgt_secs == src_secs:
        return list(bars_list)
    if tgt_secs % src_secs != 0 and src_secs not in (60, 300):
        # Calendar-month buckets aren't an exact multiple of any second-based
        # source; fall back to grouping by the floored target window.
        pass

    out: list[Bar] = []
    cur_start: datetime | None = None
    o = h = l = c = 0.0
    v = 0.0
    for b in bars_list:
        bucket_start = _floor_to(b.ts, tgt_secs)
        if cur_start is None:
            cur_start = bucket_start
            o, h, l, c, v = b.open, b.high, b.low, b.close, b.volume
            continue
        if bucket_start != cur_start:
            out.append(Bar(ts=cur_start, open=o, high=h, low=l, close=c,
                           volume=v, timeframe=tf.value))
            cur_start = bucket_start
            o, h, l, c, v = b.open, b.high, b.low, b.close, b.volume
        else:
            h = max(h, b.high)
            l = min(l, b.low)
            c = b.close
            v += b.volume
    if cur_start is not None:
        out.append(Bar(ts=cur_start, open=o, high=h, low=l, close=c,
                       volume=v, timeframe=tf.value))
    return out


def bar_count_for(start: datetime, end: datetime, tf: Timeframe | str) -> int:
    """How many bars of `tf` fit between start and end (inclusive)."""
    tf_ = tf if isinstance(tf, Timeframe) else Timeframe.parse(tf)
    return max(0, int((end - start).total_seconds() // tf_.seconds))
