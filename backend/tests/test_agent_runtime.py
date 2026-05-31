"""End-to-end agent run on the paper broker."""
from app import database
from app import models
from app.agents.runtime import run_agent


def _bootstrap_org_with_paper_agent():
    with database.SessionLocal() as db:
        org = models.Organization(name="X", risk_ack_accepted=True)
        db.add(org); db.flush()
        db.add(models.Subscription(org_id=org.id, plan_code="starter", status="active"))
        conn = models.BrokerConnection(org_id=org.id, broker="paper", label="P",
                                       trade_scope="paper", cash_cents=100_000_00)
        db.add(conn); db.flush()
        agent = models.Agent(
            org_id=org.id, name="MomBot", strategy_code="momentum",
            config_json={"symbol": "AAPL", "qty": 1, "threshold_pct": 0.001},  # always trips
            automation=models.AutomationLevel.paper,
            broker_connection_id=conn.id,
            status=models.AgentStatus.active,
            max_position_notional_cents=10_000_00,
        )
        db.add(agent)
        db.commit()
        return org.id, agent.id


def test_paper_agent_runs_and_produces_proposal_and_order():
    org_id, agent_id = _bootstrap_org_with_paper_agent()
    with database.SessionLocal() as db:
        agent = db.query(models.Agent).filter_by(id=agent_id).one()
        run = run_agent(db, agent)
        assert run.status == "ok"
        assert run.llm_rationale  # mock LLM produced text
        props = db.query(models.Proposal).filter_by(run_id=run.id).all()
        assert len(props) >= 1
        # At threshold 0.001%, almost certainly we get either buy or sell. Either way:
        # under paper automation it should auto-execute → status=executed
        statuses = {p.status.value for p in props}
        assert "executed" in statuses or "rejected_by_risk" in statuses
        if "executed" in statuses:
            orders = db.query(models.Order).filter(
                models.Order.proposal_id.in_([p.id for p in props if p.status.value == "executed"])
            ).all()
            assert len(orders) >= 1
            assert orders[0].status == "filled"


def test_suggest_mode_never_creates_orders():
    with database.SessionLocal() as db:
        org = models.Organization(name="S", risk_ack_accepted=True)
        db.add(org); db.flush()
        db.add(models.Subscription(org_id=org.id, plan_code="free", status="active"))
        conn = models.BrokerConnection(org_id=org.id, broker="paper", label="P",
                                       trade_scope="paper", cash_cents=100_000_00)
        db.add(conn); db.flush()
        agent = models.Agent(
            org_id=org.id, name="A", strategy_code="momentum",
            config_json={"symbol": "AAPL", "qty": 1, "threshold_pct": 0.001},
            automation=models.AutomationLevel.suggest,
            broker_connection_id=conn.id,
            status=models.AgentStatus.active,
        )
        db.add(agent); db.commit()
        run = run_agent(db, agent)
        props = db.query(models.Proposal).filter_by(run_id=run.id).all()
        for p in props:
            assert p.status == models.ProposalStatus.rejected_by_risk
        orders = db.query(models.Order).filter_by(org_id=org.id).all()
        assert orders == []
