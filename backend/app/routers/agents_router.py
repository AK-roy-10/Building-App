"""Agents CRUD + on-demand run."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from ..database import get_db, SessionLocal
from ..deps import get_current_user, require_role
from .. import models, schemas, audit
from ..entitlements import check_quota, require_in_list
from ..agents.strategies import STRATEGIES, get_strategy
from ..agents.runtime import run_agent

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/strategies")
def list_strategies():
    return [{"code": s.code, "name": s.name, "description": s.description,
             "config_schema": s.config_schema} for s in STRATEGIES.values()]


@router.get("")
def list_agents(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(models.Agent).filter_by(org_id=user.org_id).all()
    return [_serialize(a) for a in rows]


def _serialize(a: models.Agent) -> dict:
    return {
        "id": a.id, "name": a.name, "strategy_code": a.strategy_code,
        "config": a.config_json, "automation": a.automation.value,
        "model_code": a.model_code, "broker_connection_id": a.broker_connection_id,
        "status": a.status.value,
        "max_position_notional_cents": a.max_position_notional_cents,
        "max_orders_per_run": a.max_orders_per_run,
        "allowed_symbols": [s for s in (a.allowed_symbols_csv or "").split(",") if s.strip()],
    }


@router.post("", status_code=201)
def create_agent(body: schemas.AgentCreate,
                 user: models.User = Depends(require_role("owner", "admin", "trader")),
                 db: Session = Depends(get_db)):
    require_in_list(db, user.org_id, "allowed_strategies", body.strategy_code)
    require_in_list(db, user.org_id, "allowed_models", body.model_code)
    require_in_list(db, user.org_id, "allowed_automation", body.automation)
    current = db.query(models.Agent).filter_by(org_id=user.org_id).count()
    check_quota(db, user.org_id, "max_agents", current)

    try:
        strat = get_strategy(body.strategy_code)
    except KeyError:
        raise HTTPException(400, "Unknown strategy")
    errs = strat.validate(body.config)
    if errs:
        raise HTTPException(422, {"config_errors": errs})

    # Live automation requires a broker with trade_scope=live
    if body.automation in ("live_manual", "live_auto"):
        if not body.broker_connection_id:
            raise HTTPException(400, "Live automation requires a broker_connection_id")
        conn = db.query(models.BrokerConnection).filter_by(
            id=body.broker_connection_id, org_id=user.org_id).one_or_none()
        if not conn or conn.trade_scope != "live":
            raise HTTPException(400, "Selected broker is not live-enabled")
        org = db.query(models.Organization).filter_by(id=user.org_id).one()
        if not org.risk_ack_accepted:
            raise HTTPException(400, "Org must accept risk disclaimer before live trading")

    agent = models.Agent(
        org_id=user.org_id, name=body.name, strategy_code=body.strategy_code,
        config_json=body.config, automation=models.AutomationLevel(body.automation),
        model_code=body.model_code, broker_connection_id=body.broker_connection_id,
        max_position_notional_cents=body.max_position_notional_cents,
        max_orders_per_run=body.max_orders_per_run,
        allowed_symbols_csv=",".join(s.upper() for s in body.allowed_symbols),
        status=models.AgentStatus.active,
    )
    db.add(agent)
    audit.log(db, user.org_id, "agent.create", actor_user_id=user.id,
              target_type="agent", target_id=agent.id,
              payload={"name": body.name, "strategy": body.strategy_code,
                       "automation": body.automation})
    db.commit()
    return _serialize(agent)


@router.post("/{agent_id}/run")
def trigger_run(agent_id: str, bg: BackgroundTasks,
                user: models.User = Depends(require_role("owner", "admin", "trader")),
                db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter_by(id=agent_id, org_id=user.org_id).one_or_none()
    if not agent:
        raise HTTPException(404, "Not found")
    if agent.status != models.AgentStatus.active:
        raise HTTPException(400, f"Agent not active ({agent.status.value})")

    # Per-day quota
    since = datetime.utcnow() - timedelta(days=1)
    runs_today = db.query(models.AgentRun).filter(
        models.AgentRun.org_id == user.org_id,
        models.AgentRun.started_at >= since).count()
    check_quota(db, user.org_id, "max_runs_per_day", runs_today)

    def _bg():
        # New session for background task.
        with SessionLocal() as bdb:
            a = bdb.query(models.Agent).filter_by(id=agent_id).one()
            run_agent(bdb, a)

    bg.add_task(_bg)
    audit.log(db, user.org_id, "agent.run.queued", actor_user_id=user.id,
              target_type="agent", target_id=agent.id, payload={})
    db.commit()
    return {"queued": True}


@router.get("/{agent_id}/runs")
def agent_runs(agent_id: str, user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    runs = (db.query(models.AgentRun)
            .filter_by(agent_id=agent_id, org_id=user.org_id)
            .order_by(models.AgentRun.started_at.desc()).limit(50).all())
    return [{"id": r.id, "started_at": r.started_at, "finished_at": r.finished_at,
             "status": r.status, "summary": r.summary, "llm_rationale": r.llm_rationale}
            for r in runs]


@router.post("/{agent_id}/pause")
def pause_agent(agent_id: str, user: models.User = Depends(require_role("owner", "admin", "trader")),
                db: Session = Depends(get_db)):
    a = db.query(models.Agent).filter_by(id=agent_id, org_id=user.org_id).one_or_none()
    if not a: raise HTTPException(404, "Not found")
    a.status = models.AgentStatus.paused
    audit.log(db, user.org_id, "agent.pause", actor_user_id=user.id,
              target_type="agent", target_id=a.id, payload={})
    db.commit()
    return {"ok": True}
