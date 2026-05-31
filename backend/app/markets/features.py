"""Technical features over a Bar series. Pure Python, no pandas-ta dependency.

Each function takes a list[Bar] (oldest first) and returns either a list of
floats (same length as input, leading entries may be NaN-equivalent) or a
single scalar. Use FeatureBuilder.compute(...) for a convenient dict bundle.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Iterable

from .types import Bar

NAN = float("nan")


def _closes(bars: Iterable[Bar]) -> list[float]:
    return [b.close for b in bars]


def returns(bars: list[Bar]) -> list[float]:
    cs = _closes(bars)
    out = [NAN]
    for i in range(1, len(cs)):
        prev = cs[i - 1]
        out.append((cs[i] - prev) / prev if prev else NAN)
    return out


def realized_vol(bars: list[Bar], window: int = 20) -> float:
    """Sample std of log returns over the trailing `window` bars."""
    cs = _closes(bars)
    if len(cs) < window + 1:
        return NAN
    logs = []
    for i in range(len(cs) - window, len(cs)):
        prev = cs[i - 1]
        if prev <= 0 or cs[i] <= 0:
            return NAN
        logs.append(math.log(cs[i] / prev))
    mean = sum(logs) / len(logs)
    var = sum((x - mean) ** 2 for x in logs) / (len(logs) - 1) if len(logs) > 1 else 0.0
    return math.sqrt(var)


def sma(bars: list[Bar], window: int) -> list[float]:
    cs = _closes(bars)
    out: list[float] = []
    acc = 0.0
    for i, c in enumerate(cs):
        acc += c
        if i >= window:
            acc -= cs[i - window]
        out.append(acc / window if i >= window - 1 else NAN)
    return out


def ema(bars: list[Bar], window: int) -> list[float]:
    cs = _closes(bars)
    if not cs:
        return []
    k = 2.0 / (window + 1)
    out: list[float] = []
    prev = cs[0]
    out.append(prev)
    for i in range(1, len(cs)):
        prev = cs[i] * k + prev * (1 - k)
        out.append(prev)
    # Mark the warm-up region as NAN like SMA for consistency
    for i in range(min(window - 1, len(out))):
        out[i] = NAN
    return out


def rsi(bars: list[Bar], window: int = 14) -> list[float]:
    cs = _closes(bars)
    if len(cs) <= window:
        return [NAN] * len(cs)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(cs)):
        d = cs[i] - cs[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[1:window + 1]) / window
    avg_loss = sum(losses[1:window + 1]) / window
    out = [NAN] * (window)
    out.append(100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    for i in range(window + 1, len(cs)):
        avg_gain = (avg_gain * (window - 1) + gains[i]) / window
        avg_loss = (avg_loss * (window - 1) + losses[i]) / window
        if avg_loss == 0:
            out.append(100.0)
        else:
            rs = avg_gain / avg_loss
            out.append(100 - 100 / (1 + rs))
    return out


def macd(bars: list[Bar], fast: int = 12, slow: int = 26, signal: int = 9
         ) -> tuple[list[float], list[float], list[float]]:
    e_fast = ema(bars, fast)
    e_slow = ema(bars, slow)
    line = [NAN if math.isnan(f) or math.isnan(s) else f - s for f, s in zip(e_fast, e_slow)]
    # signal is EMA of macd line, treating NaN warm-up as starting value
    sig: list[float] = []
    k = 2.0 / (signal + 1)
    prev = None
    for v in line:
        if math.isnan(v):
            sig.append(NAN)
            continue
        if prev is None:
            prev = v
            sig.append(NAN)  # warm-up
        else:
            prev = v * k + prev * (1 - k)
            sig.append(prev)
    hist = [NAN if math.isnan(l) or math.isnan(s) else l - s for l, s in zip(line, sig)]
    return line, sig, hist


def bollinger(bars: list[Bar], window: int = 20, num_std: float = 2.0
              ) -> tuple[list[float], list[float], list[float]]:
    cs = _closes(bars)
    mid = sma(bars, window)
    upper: list[float] = []
    lower: list[float] = []
    for i in range(len(cs)):
        if i < window - 1:
            upper.append(NAN); lower.append(NAN); continue
        win = cs[i - window + 1:i + 1]
        mean = sum(win) / window
        var = sum((x - mean) ** 2 for x in win) / window
        sd = math.sqrt(var)
        upper.append(mean + num_std * sd)
        lower.append(mean - num_std * sd)
    return upper, mid, lower


def atr(bars: list[Bar], window: int = 14) -> list[float]:
    if len(bars) < 2:
        return [NAN] * len(bars)
    trs = [NAN]
    for i in range(1, len(bars)):
        h, l, pc = bars[i].high, bars[i].low, bars[i - 1].close
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    out = [NAN] * len(bars)
    if len(bars) <= window:
        return out
    first = sum(trs[1:window + 1]) / window
    out[window] = first
    prev = first
    for i in range(window + 1, len(bars)):
        prev = (prev * (window - 1) + trs[i]) / window
        out[i] = prev
    return out


def vwap(bars: list[Bar]) -> list[float]:
    out: list[float] = []
    cum_pv = 0.0
    cum_v = 0.0
    for b in bars:
        tp = (b.high + b.low + b.close) / 3.0
        cum_pv += tp * b.volume
        cum_v += b.volume
        out.append(cum_pv / cum_v if cum_v else NAN)
    return out


# ---------- Bundle ----------
@dataclass
class FeatureBuilder:
    rsi_window: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_window: int = 20
    bb_num_std: float = 2.0
    atr_window: int = 14
    sma_short: int = 10
    sma_long: int = 50
    vol_window: int = 20

    def compute(self, bars: list[Bar]) -> dict:
        return compute_features(bars, self)


def compute_features(bars: list[Bar], cfg: FeatureBuilder | None = None) -> dict:
    """Return a dict of indicators + summary. Safe on short series (NaN-padded)."""
    cfg = cfg or FeatureBuilder()
    if not bars:
        return {"n": 0}
    closes = _closes(bars)
    last = closes[-1]
    ret_series = returns(bars)
    rsi_series = rsi(bars, cfg.rsi_window)
    macd_line, macd_sig, macd_hist = macd(bars, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
    bb_up, bb_mid, bb_low = bollinger(bars, cfg.bb_window, cfg.bb_num_std)
    atr_series = atr(bars, cfg.atr_window)
    sma_s = sma(bars, cfg.sma_short)
    sma_l = sma(bars, cfg.sma_long)
    vwap_series = vwap(bars)
    rv = realized_vol(bars, cfg.vol_window)
    summary = {
        "n": len(bars),
        "last_close": last,
        "first_close": closes[0],
        "pct_change_total": (last - closes[0]) / closes[0] if closes[0] else NAN,
        "last_return": ret_series[-1],
        "rsi": rsi_series[-1],
        "macd": macd_line[-1],
        "macd_signal": macd_sig[-1],
        "macd_hist": macd_hist[-1],
        "bollinger_upper": bb_up[-1],
        "bollinger_mid": bb_mid[-1],
        "bollinger_lower": bb_low[-1],
        "atr": atr_series[-1],
        "sma_short": sma_s[-1],
        "sma_long": sma_l[-1],
        "vwap": vwap_series[-1],
        "realized_vol": rv,
    }
    # Simple regime label
    if not math.isnan(summary["sma_short"]) and not math.isnan(summary["sma_long"]):
        if summary["sma_short"] > summary["sma_long"]:
            summary["regime"] = "uptrend"
        elif summary["sma_short"] < summary["sma_long"]:
            summary["regime"] = "downtrend"
        else:
            summary["regime"] = "flat"
    else:
        summary["regime"] = "unknown"
    return summary
