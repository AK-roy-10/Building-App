"""Market data, asset class, timeframe, data provider, and backtest endpoints."""
from __future__ import annotations
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_role
from .. import models, schemas
from ..markets.types import AssetClass, Timeframe, Symbol
from ..markets.data_provider import list_data_providers, get_data_provider
from ..markets.features import compute_features
from ..markets.backtester import run_backtest
from ..agents.strategies import get_strategy
from ..entitlements import check_quota, require_in_list, get_org_entitlements

router = APIRouter(prefix="/api", tags=["markets"])


@router.get("/asset-classes")
def asset_classes(user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    ent = get_org_entitlements(db, user.org_id)
    allowed = set(ent.get("allowed_asset_classes") or [])
    wildcard = "*" in allowed
    return [{"code": ac, "name": ac.replace("_", " ").title(),
             "available": (wildcard or ac in allowed)}
            for ac in AssetClass.all()]


@router.get("/timeframes")
def timeframes():
    return [{"code": tf, "seconds": Timeframe.parse(tf).seconds} for tf in Timeframe.all()]


@router.get("/data-providers")
def data_providers(user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    ent = get_org_entitlements(db, user.org_id)
    allowed = set(ent.get("allowed_data_providers") or [])
    wildcard = "*" in allowed
    return [{**p, "available": (wildcard or p["code"] in allowed)}
            for p in list_data_providers()]


@router.get("/market-data/{provider}/{symbol}/{timeframe}")
def get_bars_endpoint(provider: str, symbol: str, timeframe: str,
                      limit: int = 200,
                      user: models.User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    require_in_list(db, user.org_id, "allowed_data_providers", provider)
    try:
        prov = get_data_provider(provider)
        tf = Timeframe.parse(timeframe)
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))
    end = datetime.utcnow()
    start = end - timedelta(seconds=tf.seconds * max(limit, 1))
    bars = prov.get_bars(Symbol.parse(symbol), tf, start, end)
    feats = compute_features(bars)
    return {
        "symbol": symbol, "timeframe": timeframe, "provider": provider,
        "bars": [b.__dict__ if not hasattr(b, "_asdict") else dict(b._asdict())
                 for b in bars[-limit:]],
        "features": feats,
    }


@router.post("/agents/{agent_id}/backtest")
def backtest_agent(agent_id: str, body: schemas.BacktestRequest,
                   user: models.User = Depends(require_role("owner", "admin", "trader")),
                   db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter_by(id=agent_id, org_id=user.org_id).one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    # Per-day quota
    since = datetime.utcnow() - timedelta(days=1)
    today = 0  # backtest counter — not tracked yet via AuditEvent
    check_quota(db, user.org_id, "max_backtests_per_day", today)

    try:
        prov = get_data_provider(getattr(agent, "data_provider", None) or "synthetic")
        tf = Timeframe.parse(getattr(agent, "timeframe", None) or "1d")
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))

    end = datetime.fromisoformat(body.end) if body.end else datetime.utcnow()
    start = (datetime.fromisoformat(body.start)
             if body.start else end - timedelta(seconds=tf.seconds * 300))
    symbols = ([body.symbol] if body.symbol
               else [s for s in (agent.allowed_symbols_csv or "").split(",") if s.strip()])
    if not symbols:
        raise HTTPException(400, "No symbol available — set agent.allowed_symbols or pass body.symbol")
    sym = Symbol.parse(symbols[0])
    bars = prov.get_bars(sym, tf, start, end)
    if not bars:
        raise HTTPException(400, "No bars returned by provider for the requested window")

    strat = get_strategy(agent.strategy_code)

    def decide(window):
        # Simple universal decider: feed window-mean price into the strategy's
        # `decide(prices, config)` if available; otherwise threshold on momentum.
        prices = [b.close for b in window]
        if hasattr(strat, "decide"):
            try:
                return strat.decide(prices, agent.config_json or {})
            except Exception:
                pass
        if len(prices) < 3:
            return None
        mom = (prices[-1] - prices[-3]) / max(prices[-3], 1e-9)
        if mom > 0.002:
            return ("buy", 1.0)
        if mom < -0.002:
            return ("sell", 1.0)
        return None

    result = run_backtest(bars, decide, starting_cash=body.starting_cash_cents / 100.0)
    return {
        "agent_id": agent.id,
        "symbol": sym.display(),
        "timeframe": tf.value,
        "n_bars": len(bars),
        "result": result.__dict__,
    }
