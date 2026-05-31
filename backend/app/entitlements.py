"""Entitlement (plan-gating) service. Single source of truth for 'can org X do Y?'."""
from __future__ import annotations
from typing import Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

# Plan catalogue. Server-side enforced; UI may also hide unavailable features.
DEFAULT_PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "name": "Free",
        "price_cents": 0,
        "entitlements": {
            "max_agents": 1,
            "max_broker_connections": 1,
            "max_runs_per_day": 20,
            "allowed_strategies": ["momentum", "news_summary"],
            "allowed_models": ["mock"],
            "allowed_automation": ["suggest"],
            "allowed_trade_scopes": ["paper"],
            "data_realtime": False,
        },
    },
    "starter": {
        "name": "Starter",
        "price_cents": 1900,
        "entitlements": {
            "max_agents": 3,
            "max_broker_connections": 2,
            "max_runs_per_day": 200,
            "allowed_strategies": ["momentum", "mean_reversion", "news_summary"],
            "allowed_models": ["mock", "gpt-small"],
            "allowed_automation": ["suggest", "paper"],
            "allowed_trade_scopes": ["paper"],
            "data_realtime": True,
        },
    },
    "pro": {
        "name": "Pro",
        "price_cents": 9900,
        "entitlements": {
            "max_agents": 10,
            "max_broker_connections": 5,
            "max_runs_per_day": 2000,
            "allowed_strategies": ["momentum", "mean_reversion", "news_summary", "portfolio_risk"],
            "allowed_models": ["mock", "gpt-small", "gpt-large"],
            "allowed_automation": ["suggest", "paper", "live_manual"],
            "allowed_trade_scopes": ["paper", "live"],
            "data_realtime": True,
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "price_cents": 49900,
        "entitlements": {
            "max_agents": 1000,
            "max_broker_connections": 100,
            "max_runs_per_day": 100000,
            "allowed_strategies": ["momentum", "mean_reversion", "news_summary", "portfolio_risk"],
            "allowed_models": ["mock", "gpt-small", "gpt-large"],
            "allowed_automation": ["suggest", "paper", "live_manual", "live_auto"],
            "allowed_trade_scopes": ["paper", "live"],
            "data_realtime": True,
        },
    },
}


def get_org_entitlements(db: Session, org_id: str) -> dict:
    """Return the active entitlements dict for an org (defaults to Free)."""
    from . import models
    sub = (
        db.query(models.Subscription)
        .filter_by(org_id=org_id, status="active")
        .order_by(models.Subscription.created_at.desc())
        .first()
    )
    code = sub.plan_code if sub else "free"
    plan = db.query(models.Plan).filter_by(code=code).one_or_none()
    if not plan:
        return DEFAULT_PLANS["free"]["entitlements"]
    return plan.entitlements_json or {}


class EntitlementError(HTTPException):
    def __init__(self, message: str):
        super().__init__(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=message)


def check_quota(db: Session, org_id: str, key: str, current_count: int) -> None:
    ent = get_org_entitlements(db, org_id)
    limit = ent.get(key)
    if limit is not None and current_count >= int(limit):
        raise EntitlementError(f"Plan quota exceeded for {key} (limit {limit}). Upgrade to continue.")


def require_in_list(db: Session, org_id: str, key: str, value: str) -> None:
    ent = get_org_entitlements(db, org_id)
    allowed = ent.get(key) or []
    if value not in allowed:
        raise EntitlementError(f"'{value}' is not allowed by your plan ({key}). Allowed: {allowed}")
