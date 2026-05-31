"""ORM models. Every domain table carries `org_id` for multi-tenancy."""
from __future__ import annotations
import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON, Enum as SAEnum, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------- Tenancy ----------
class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # operational flags
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_loss_limit_cents: Mapped[int] = mapped_column(Integer, default=10_000_00)
    realised_pnl_today_cents: Mapped[int] = mapped_column(Integer, default=0)
    risk_ack_accepted: Mapped[bool] = mapped_column(Boolean, default=False)


class RoleEnum(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    trader = "trader"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(SAEnum(RoleEnum), default=RoleEnum.owner)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    org: Mapped[Organization] = relationship()


# ---------- Plans & subscriptions ----------
class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    entitlements_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), index=True, nullable=False)
    plan_code: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------- Broker connections ----------
class BrokerConnection(Base):
    __tablename__ = "broker_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), index=True, nullable=False)
    broker: Mapped[str] = mapped_column(String(40), nullable=False)  # 'paper' | 'alpaca' | ...
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    encrypted_credentials: Mapped[str] = mapped_column(Text, default="")  # base64 Fernet
    trade_scope: Mapped[str] = mapped_column(String(40), default="paper")  # 'sandbox' | 'paper' | 'live'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Per-connection asset-class allowlist (subset of the broker's capabilities).
    # Empty list / null means "all that the broker supports".
    asset_classes_json: Mapped[list] = mapped_column(JSON, default=list)
    # Paper broker state (for the built-in paper broker)
    cash_cents: Mapped[int] = mapped_column(Integer, default=100_000_00)  # $100k starter
    positions_json: Mapped[dict] = mapped_column(JSON, default=dict)  # {symbol: {qty, avg_price}}


# ---------- Agents ----------
class AutomationLevel(str, enum.Enum):
    suggest = "suggest"             # never trade, only suggestions
    paper = "paper"                 # trade in paper broker, no approval needed
    live_manual = "live_manual"     # live trades, but every proposal needs approval
    live_auto = "live_auto"         # auto execute only if within hard limits


class AgentStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    archived = "archived"


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    strategy_code: Mapped[str] = mapped_column(String(40), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    automation: Mapped[AutomationLevel] = mapped_column(SAEnum(AutomationLevel), default=AutomationLevel.suggest)
    model_code: Mapped[str] = mapped_column(String(80), default="mock")
    # New: provider + extra params for the new LLM registry. `model_code` above
    # remains the catalog id; `llm_provider` is the dispatcher hint.
    llm_provider: Mapped[str] = mapped_column(String(40), default="")
    llm_params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # New: asset class + timeframe drive the data provider + risk checks.
    asset_class: Mapped[str] = mapped_column(String(20), default="equity")
    timeframe: Mapped[str] = mapped_column(String(8), default="1d")
    data_provider: Mapped[str] = mapped_column(String(40), default="synthetic")
    broker_connection_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("broker_connections.id"), nullable=True)
    status: Mapped[AgentStatus] = mapped_column(SAEnum(AgentStatus), default=AgentStatus.draft)
    # Per-agent risk policy
    max_position_notional_cents: Mapped[int] = mapped_column(Integer, default=5_000_00)
    max_orders_per_run: Mapped[int] = mapped_column(Integer, default=3)
    allowed_symbols_csv: Mapped[str] = mapped_column(Text, default="")  # empty = inherit org default
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------- Runs / Proposals / Approvals / Orders ----------
class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id"), index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="running")
    summary: Mapped[str] = mapped_column(Text, default="")
    llm_rationale: Mapped[str] = mapped_column(Text, default="")
    data_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ProposalStatus(str, enum.Enum):
    pending = "pending"           # awaiting risk verdict
    rejected_by_risk = "rejected_by_risk"
    requires_approval = "requires_approval"
    approved = "approved"
    rejected_by_user = "rejected_by_user"
    executed = "executed"
    failed = "failed"
    expired = "expired"


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id"), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # buy / sell
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), default="market")
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ProposalStatus] = mapped_column(SAEnum(ProposalStatus), default=ProposalStatus.pending)
    risk_verdict_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    proposal_id: Mapped[str] = mapped_column(String(36), ForeignKey("proposals.id"), nullable=False)
    broker_connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("broker_connections.id"), nullable=False)
    broker_order_id: Mapped[str] = mapped_column(String(80), default="")
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    filled_qty: Mapped[float] = mapped_column(Float, default=0.0)
    avg_fill_price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), default="new")  # new/filled/cancelled/rejected
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------- Audit log (append-only) ----------
class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="user")  # user | agent | system
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), default="")
    target_id: Mapped[str] = mapped_column(String(80), default="")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Index("ix_audit_org_created", AuditEvent.org_id, AuditEvent.created_at)
