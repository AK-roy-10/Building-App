"""Pydantic schemas for the JSON API."""
from __future__ import annotations
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    org_name: str = Field(min_length=2)
    accept_risk_disclaimer: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: EmailStr
    org_id: str
    role: str

    model_config = {"from_attributes": True}


class PlanOut(BaseModel):
    code: str
    name: str
    price_cents: int
    entitlements: dict

    model_config = {"from_attributes": True}


class SubscribeRequest(BaseModel):
    plan_code: str


class BrokerConnectionCreate(BaseModel):
    broker: str  # 'paper' | 'alpaca'
    label: str
    trade_scope: str = "paper"
    api_key: Optional[str] = None
    api_secret: Optional[str] = None


class BrokerConnectionOut(BaseModel):
    id: str
    broker: str
    label: str
    trade_scope: str
    enabled: bool
    cash_cents: int
    positions: dict

    model_config = {"from_attributes": True}


class AgentCreate(BaseModel):
    name: str
    strategy_code: str
    config: dict
    automation: str = "suggest"
    model_code: str = "mock"
    broker_connection_id: Optional[str] = None
    max_position_notional_cents: int = 5_000_00
    max_orders_per_run: int = 3
    allowed_symbols: List[str] = []


class AgentOut(BaseModel):
    id: str
    name: str
    strategy_code: str
    config: dict
    automation: str
    model_code: str
    broker_connection_id: Optional[str]
    status: str
    max_position_notional_cents: int
    max_orders_per_run: int
    allowed_symbols: List[str]


class ProposalOut(BaseModel):
    id: str
    symbol: str
    side: str
    qty: float
    order_type: str
    limit_price: Optional[float]
    status: str
    reason: str
    risk_verdict: dict

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: str
    agent_id: str
    started_at: Any
    finished_at: Any
    status: str
    summary: str
    llm_rationale: str

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    approve: bool
    note: str = ""
