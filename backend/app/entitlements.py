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
            "max_backtests_per_day": 5,
            "allowed_strategies": ["momentum", "news_summary"],
            "allowed_models": ["mock"],
            "allowed_llm_providers": ["mock"],
            "allowed_llm_tags": ["free", "offline"],
            "allowed_automation": ["suggest"],
            "allowed_trade_scopes": ["paper"],
            "allowed_asset_classes": ["equity"],
            "allowed_data_providers": ["synthetic"],
            "allowed_brokers": ["paper"],
            "max_llm_cost_per_1k_in": 0.0,
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
            "max_backtests_per_day": 50,
            "allowed_strategies": ["momentum", "mean_reversion", "news_summary",
                                   "breakout", "vwap_revert"],
            "allowed_models": ["mock", "gpt-small", "gpt-4o-mini",
                               "fingpt-llama3-8b", "llama3:8b", "mistral-finance-7b"],
            "allowed_llm_providers": ["mock", "openai", "ollama"],
            "allowed_llm_tags": ["free", "offline", "cheap", "finance", "open"],
            "allowed_automation": ["suggest", "paper"],
            "allowed_trade_scopes": ["paper"],
            "allowed_asset_classes": ["equity", "crypto"],
            "allowed_data_providers": ["synthetic", "yahoo", "ccxt"],
            "allowed_brokers": ["paper", "alpaca", "ccxt", "binance", "coinbase", "kraken"],
            "max_llm_cost_per_1k_in": 0.001,
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
            "max_backtests_per_day": 500,
            "allowed_strategies": ["momentum", "mean_reversion", "news_summary",
                                   "portfolio_risk", "breakout", "vwap_revert",
                                   "carry_fx", "seasonality_commodity"],
            "allowed_models": ["mock", "gpt-small", "gpt-large", "gpt-4o-mini", "gpt-4o",
                               "claude-3-haiku", "claude-3-5-sonnet", "gemini-1.5-pro",
                               "fingpt-llama3-8b", "instruct-fingpt", "finma-7b",
                               "fintral-7b", "finance-chat-13b", "mistral-finance-7b",
                               "llama3:8b", "mixtral-8x7b-instruct"],
            "allowed_llm_providers": ["mock", "openai", "anthropic", "gemini",
                                      "ollama", "hugging_face"],
            "allowed_llm_tags": ["free", "offline", "cheap", "finance", "open",
                                 "general", "long-context", "self-hosted"],
            "allowed_automation": ["suggest", "paper", "live_manual"],
            "allowed_trade_scopes": ["paper", "live", "sandbox"],
            "allowed_asset_classes": ["equity", "crypto", "forex", "commodity_cfd"],
            "allowed_data_providers": ["synthetic", "yahoo", "ccxt"],
            "allowed_brokers": ["paper", "alpaca", "ccxt", "binance", "coinbase",
                                "kraken", "oanda", "tradier"],
            "max_llm_cost_per_1k_in": 0.01,
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
            "max_backtests_per_day": 100000,
            "allowed_strategies": ["momentum", "mean_reversion", "news_summary",
                                   "portfolio_risk", "breakout", "vwap_revert",
                                   "carry_fx", "seasonality_commodity"],
            # "*" sentinel == any allowed model id in the catalog
            "allowed_models": ["*"],
            "allowed_llm_providers": ["*"],
            "allowed_llm_tags": ["*"],
            "allowed_automation": ["suggest", "paper", "live_manual", "live_auto"],
            "allowed_trade_scopes": ["paper", "live", "sandbox"],
            "allowed_asset_classes": ["equity", "crypto", "forex", "futures",
                                      "options", "commodity_cfd"],
            "allowed_data_providers": ["*"],
            "allowed_brokers": ["*"],
            "max_llm_cost_per_1k_in": 1.0,
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
    """Allow either an exact match or a `"*"` wildcard entry in the entitlement list."""
    ent = get_org_entitlements(db, org_id)
    allowed = ent.get(key) or []
    if "*" in allowed:
        return
    if value not in allowed:
        raise EntitlementError(f"'{value}' is not allowed by your plan ({key}). Allowed: {allowed}")
