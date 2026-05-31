"""Built-in strategies. Each is a pure function:
    inputs:   config dict + market data callable
    output:   list of ProposalDraft + signal context for the LLM
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Callable
from jsonschema import Draft202012Validator


@dataclass
class ProposalDraft:
    symbol: str
    side: str
    qty: float
    order_type: str = "market"
    limit_price: float | None = None
    reason: str = ""


@dataclass
class StrategyResult:
    proposals: list[ProposalDraft] = field(default_factory=list)
    context: dict = field(default_factory=dict)  # passed to the LLM for narrative
    notes: list[str] = field(default_factory=list)


@dataclass
class Strategy:
    code: str
    name: str
    description: str
    config_schema: dict   # JSON Schema for config
    run: Callable[[dict, Callable[[str], float]], StrategyResult]

    def validate(self, config: dict) -> list[str]:
        v = Draft202012Validator(self.config_schema)
        return [e.message for e in v.iter_errors(config)]


# ---------- Strategy implementations ----------

def _momentum(config: dict, price_of: Callable[[str], float]) -> StrategyResult:
    symbol = config["symbol"].upper()
    qty = float(config.get("qty", 1))
    threshold = float(config.get("threshold_pct", 1.0)) / 100.0
    last = price_of(symbol)
    # Synthesize "prior" price from a tiny pseudo-history; in a real impl, query the data source.
    rng = random.Random(symbol)
    prior = last * (1 - rng.uniform(-0.03, 0.03))
    change = (last - prior) / prior if prior else 0
    ctx = {"symbol": symbol, "last_price": last, "prior_price": round(prior, 2),
           "pct_change": change, "threshold_pct": threshold, "signal": "neutral"}
    if change >= threshold:
        ctx["signal"] = "buy"
        return StrategyResult(
            proposals=[ProposalDraft(symbol=symbol, side="buy", qty=qty,
                                     reason=f"Momentum up {change:+.2%} >= {threshold:.2%}")],
            context=ctx)
    if change <= -threshold:
        ctx["signal"] = "sell"
        return StrategyResult(
            proposals=[ProposalDraft(symbol=symbol, side="sell", qty=qty,
                                     reason=f"Momentum down {change:+.2%} <= -{threshold:.2%}")],
            context=ctx)
    return StrategyResult(context=ctx, notes=["No momentum threshold crossed"])


def _mean_reversion(config: dict, price_of: Callable[[str], float]) -> StrategyResult:
    symbol = config["symbol"].upper()
    qty = float(config.get("qty", 1))
    z_threshold = float(config.get("z_threshold", 1.5))
    last = price_of(symbol)
    rng = random.Random(symbol + "mr")
    series = [last * (1 + rng.uniform(-0.02, 0.02)) for _ in range(20)]
    mean = sum(series) / len(series)
    var = sum((x - mean) ** 2 for x in series) / len(series)
    sd = math.sqrt(var) or 1.0
    z = (last - mean) / sd
    ctx = {"symbol": symbol, "last_price": last, "mean": round(mean, 2),
           "z_score": round(z, 2), "pct_change": (last - mean) / mean if mean else 0,
           "signal": "neutral"}
    if z >= z_threshold:
        ctx["signal"] = "sell"
        return StrategyResult(
            proposals=[ProposalDraft(symbol=symbol, side="sell", qty=qty,
                                     reason=f"Mean reversion: z={z:.2f} >= {z_threshold}")],
            context=ctx)
    if z <= -z_threshold:
        ctx["signal"] = "buy"
        return StrategyResult(
            proposals=[ProposalDraft(symbol=symbol, side="buy", qty=qty,
                                     reason=f"Mean reversion: z={z:.2f} <= -{z_threshold}")],
            context=ctx)
    return StrategyResult(context=ctx, notes=["Within mean-reversion band"])


def _news_summary(config: dict, price_of: Callable[[str], float]) -> StrategyResult:
    # Read-only research agent. Never produces proposals.
    symbols = [s.upper() for s in config.get("symbols", [])]
    prices = {s: price_of(s) for s in symbols}
    return StrategyResult(
        context={"symbols": symbols, "prices": prices, "signal": "neutral",
                 "symbol": symbols[0] if symbols else "PORTFOLIO",
                 "last_price": prices.get(symbols[0], 0) if symbols else 0,
                 "pct_change": 0.0},
        notes=["Research agent: produces only an analytical note, no proposals."],
    )


def _portfolio_risk(config: dict, price_of: Callable[[str], float]) -> StrategyResult:
    # Risk-monitor agent; produces no orders, just narrative.
    return StrategyResult(
        context={"symbol": "PORTFOLIO", "last_price": 0.0, "pct_change": 0.0, "signal": "neutral",
                 "note": "Computes portfolio exposure/var (stub)."},
        notes=["Portfolio risk report generated."],
    )


STRATEGIES: dict[str, Strategy] = {
    "momentum": Strategy(
        code="momentum",
        name="Momentum",
        description="Buy/sell on simple % change threshold.",
        config_schema={
            "type": "object",
            "required": ["symbol"],
            "properties": {
                "symbol": {"type": "string", "minLength": 1, "maxLength": 10},
                "qty": {"type": "number", "exclusiveMinimum": 0, "maximum": 1_000_000},
                "threshold_pct": {"type": "number", "exclusiveMinimum": 0, "maximum": 50},
            },
            "additionalProperties": False,
        },
        run=_momentum,
    ),
    "mean_reversion": Strategy(
        code="mean_reversion",
        name="Mean reversion",
        description="Trade against z-score extremes vs short window mean.",
        config_schema={
            "type": "object",
            "required": ["symbol"],
            "properties": {
                "symbol": {"type": "string", "minLength": 1, "maxLength": 10},
                "qty": {"type": "number", "exclusiveMinimum": 0, "maximum": 1_000_000},
                "z_threshold": {"type": "number", "minimum": 0.5, "maximum": 5.0},
            },
            "additionalProperties": False,
        },
        run=_mean_reversion,
    ),
    "news_summary": Strategy(
        code="news_summary",
        name="News & research summary",
        description="Analytical-only agent. Produces narrative, no trades.",
        config_schema={
            "type": "object",
            "required": ["symbols"],
            "properties": {
                "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 25},
                "hours_lookback": {"type": "integer", "minimum": 1, "maximum": 168},
            },
            "additionalProperties": False,
        },
        run=_news_summary,
    ),
    "portfolio_risk": Strategy(
        code="portfolio_risk",
        name="Portfolio risk monitor",
        description="Daily portfolio risk report; no trades.",
        config_schema={
            "type": "object",
            "properties": {
                "var_confidence": {"type": "number", "minimum": 0.5, "maximum": 0.999},
            },
            "additionalProperties": False,
        },
        run=_portfolio_risk,
    ),
}


def get_strategy(code: str) -> Strategy:
    if code not in STRATEGIES:
        raise KeyError(f"Unknown strategy: {code}")
    return STRATEGIES[code]
