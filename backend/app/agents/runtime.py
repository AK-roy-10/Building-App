"""Agent run orchestration. Pipeline:

  load agent + broker → run strategy → call LLM for rationale (read-only) →
  for each ProposalDraft: persist Proposal → risk-engine verdict →
    rejected      : mark + audit
    requires-approval: mark + audit; UI inbox shows it
    approved      : route to order executor → persist Order → mark proposal executed

The LLM never executes trades. Only deterministic code can call the broker.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session

from .. import models, audit
from ..llm import get_llm
from ..risk_engine import Proposal, AccountState, RiskPolicy, evaluate
from ..brokers import get_broker, BrokerError
from .strategies import get_strategy


def _account_state(broker, org: models.Organization) -> AccountState:
    acct = broker.get_account()
    return AccountState(
        cash_cents=acct.cash_cents,
        positions=acct.positions,
        realised_pnl_today_cents=org.realised_pnl_today_cents,
    )


def _policy_for(agent: models.Agent, conn: models.BrokerConnection | None,
                org: models.Organization, price_hint: float) -> RiskPolicy:
    return RiskPolicy(
        automation=agent.automation.value,
        trade_scope=conn.trade_scope if conn else "paper",
        max_position_notional_cents=agent.max_position_notional_cents,
        max_orders_per_run=agent.max_orders_per_run,
        allowed_symbols=[s for s in (agent.allowed_symbols_csv or "").split(",") if s.strip()],
        org_daily_loss_limit_cents=org.daily_loss_limit_cents,
        org_kill_switch=org.kill_switch,
        risk_ack_accepted=org.risk_ack_accepted,
        price_hint=price_hint,
    )


def _execute_approved(db: Session, agent: models.Agent, conn: models.BrokerConnection,
                      proposal: models.Proposal) -> models.Order:
    broker = get_broker(db, conn)
    try:
        bo = broker.place_order(
            symbol=proposal.symbol, side=proposal.side, qty=proposal.qty,
            order_type=proposal.order_type, limit_price=proposal.limit_price,
            idempotency_key=proposal.id,
        )
    except BrokerError as e:
        proposal.status = models.ProposalStatus.failed
        audit.log(db, agent.org_id, "order.failed", actor_type="system",
                  target_type="proposal", target_id=proposal.id, payload={"error": str(e)})
        db.commit()
        raise
    order = models.Order(
        org_id=agent.org_id, proposal_id=proposal.id, broker_connection_id=conn.id,
        broker_order_id=bo.broker_order_id, symbol=proposal.symbol, side=proposal.side,
        qty=proposal.qty, filled_qty=bo.filled_qty, avg_fill_price=bo.avg_fill_price,
        status=bo.status, idempotency_key=proposal.id,
    )
    db.add(order)
    proposal.status = models.ProposalStatus.executed
    proposal.decided_at = datetime.utcnow()
    audit.log(db, agent.org_id, "order.placed", actor_type="agent",
              target_type="order", target_id=order.id,
              payload={"symbol": order.symbol, "side": order.side, "qty": order.qty,
                       "status": order.status, "broker": conn.broker})
    db.commit()
    return order


def run_agent(db: Session, agent: models.Agent) -> models.AgentRun:
    org = db.query(models.Organization).filter_by(id=agent.org_id).one()
    run = models.AgentRun(org_id=agent.org_id, agent_id=agent.id, status="running")
    db.add(run)
    db.flush()

    audit.log(db, agent.org_id, "agent.run.start", actor_type="system",
              target_type="agent", target_id=agent.id, payload={"run_id": run.id})

    # Resolve broker (may be None for pure research agents)
    conn = None
    if agent.broker_connection_id:
        conn = db.query(models.BrokerConnection).filter_by(id=agent.broker_connection_id).one_or_none()

    # 1. Run the deterministic strategy
    strategy = get_strategy(agent.strategy_code)
    errors = strategy.validate(agent.config_json or {})
    if errors:
        run.status = "failed"
        run.summary = f"Invalid config: {errors}"
        run.finished_at = datetime.utcnow()
        db.commit()
        return run

    if conn is not None:
        broker = get_broker(db, conn)
        price_of = broker.get_last_price
    else:
        # No broker → synthetic prices from the paper broker price generator.
        from ..brokers.paper import _synthetic_price
        price_of = _synthetic_price

    result = strategy.run(agent.config_json or {}, price_of)
    run.data_snapshot_json = {"context": result.context, "notes": result.notes}

    # 2. LLM rationale (read-only)
    llm = get_llm()
    llm_res = llm.analyze(
        model=agent.model_code,
        context=result.context,
        prompt=("Summarize the analytical context briefly and classify it as "
                "bullish, bearish, or neutral. Do not give financial advice."),
    )
    run.llm_rationale = llm_res.rationale
    audit.log(db, agent.org_id, "agent.llm.call", actor_type="agent",
              target_type="run", target_id=run.id,
              payload={"model": llm_res.model, "classification": llm_res.classification,
                       "tokens_in": llm_res.tokens_in, "tokens_out": llm_res.tokens_out})

    # 3. Risk-evaluate each proposal
    executed = 0
    rejected = 0
    pending = 0
    for i, draft in enumerate(result.proposals):
        price_hint = price_of(draft.symbol)
        policy = _policy_for(agent, conn, org, price_hint)
        proposal_obj = Proposal(symbol=draft.symbol, side=draft.side, qty=draft.qty,
                                order_type=draft.order_type, limit_price=draft.limit_price)
        account = _account_state(get_broker(db, conn), org) if conn else AccountState(0, {}, 0)
        verdict = evaluate(proposal_obj, account, policy, orders_already_this_run=i)

        proposal_row = models.Proposal(
            org_id=agent.org_id, run_id=run.id, agent_id=agent.id,
            symbol=draft.symbol, side=draft.side, qty=draft.qty,
            order_type=draft.order_type, limit_price=draft.limit_price,
            reason=draft.reason,
            risk_verdict_json=verdict.to_dict(),
        )

        if verdict.verdict == "rejected":
            proposal_row.status = models.ProposalStatus.rejected_by_risk
            rejected += 1
        elif verdict.verdict == "requires_user_approval":
            proposal_row.status = models.ProposalStatus.requires_approval
            pending += 1
        else:
            proposal_row.status = models.ProposalStatus.approved

        db.add(proposal_row)
        db.flush()
        audit.log(db, agent.org_id, f"proposal.{proposal_row.status.value}",
                  actor_type="agent", target_type="proposal", target_id=proposal_row.id,
                  payload={"symbol": draft.symbol, "side": draft.side, "qty": draft.qty,
                           "verdict": verdict.verdict, "reasons": verdict.reasons})

        if proposal_row.status == models.ProposalStatus.approved and conn is not None:
            try:
                _execute_approved(db, agent, conn, proposal_row)
                executed += 1
            except BrokerError:
                rejected += 1

    run.status = "ok"
    run.summary = (f"Strategy={agent.strategy_code}; proposals={len(result.proposals)}, "
                   f"executed={executed}, pending_approval={pending}, rejected={rejected}. "
                   f"LLM={llm_res.classification}.")
    run.finished_at = datetime.utcnow()
    audit.log(db, agent.org_id, "agent.run.finish", actor_type="system",
              target_type="run", target_id=run.id,
              payload={"executed": executed, "pending": pending, "rejected": rejected})
    db.commit()
    return run
