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
    broker: str  # 'paper' | 'alpaca' | 'ccxt' | ...
    label: str
    trade_scope: str = "paper"
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    asset_classes: List[str] = []
    extra: dict = {}  # broker-specific (e.g., {"exchange": "binance"} for ccxt)


class BrokerConnectionOut(BaseModel):
    id: str
    broker: str
    label: str
    trade_scope: str
    enabled: bool
    cash_cents: int
    positions: dict
    asset_classes: List[str] = []

    model_config = {"from_attributes": True}


class AgentCreate(BaseModel):
    name: str
    strategy_code: str
    config: dict
    automation: str = "suggest"
    model_code: str = "mock"
    llm_provider: str = ""  # "" lets the registry pick by model_code
    llm_params: dict = {}
    asset_class: str = "equity"
    timeframe: str = "1d"
    data_provider: str = "synthetic"
    broker_connection_id: Optional[str] = None
    max_position_notional_cents: int = 5_000_00
    max_orders_per_run: int = 3
    allowed_symbols: List[str] = []

    model_config = {"protected_namespaces": ()}  # silence pydantic's `model_` warning


class AgentOut(BaseModel):
    id: str
    name: str
    strategy_code: str
    config: dict
    automation: str
    model_code: str
    llm_provider: str = ""
    llm_params: dict = {}
    asset_class: str = "equity"
    timeframe: str = "1d"
    data_provider: str = "synthetic"
    broker_connection_id: Optional[str]
    status: str
    max_position_notional_cents: int
    max_orders_per_run: int
    allowed_symbols: List[str]

    model_config = {"protected_namespaces": ()}


class BacktestRequest(BaseModel):
    start: Optional[str] = None  # ISO date
    end: Optional[str] = None
    starting_cash_cents: int = 100_000_00
    symbol: Optional[str] = None  # overrides allowed_symbols[0]


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
