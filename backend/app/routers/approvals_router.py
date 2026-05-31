"""Approval inbox + decision endpoint. Manual gate for live trades."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_role
from .. import models, schemas, audit
from ..agents.runtime import _execute_approved

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("")
def list_pending(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(models.Proposal)
            .filter_by(org_id=user.org_id, status=models.ProposalStatus.requires_approval)
            .order_by(models.Proposal.created_at.desc()).all())
    return [{"id": p.id, "agent_id": p.agent_id, "symbol": p.symbol, "side": p.side,
             "qty": p.qty, "order_type": p.order_type, "limit_price": p.limit_price,
             "reason": p.reason, "risk_verdict": p.risk_verdict_json,
             "created_at": p.created_at} for p in rows]


@router.post("/{proposal_id}")
def decide(proposal_id: str, body: schemas.ApprovalDecision,
           user: models.User = Depends(require_role("owner", "admin", "trader")),
           db: Session = Depends(get_db)):
    p = db.query(models.Proposal).filter_by(id=proposal_id, org_id=user.org_id).one_or_none()
    if not p:
        raise HTTPException(404, "Not found")
    if p.status != models.ProposalStatus.requires_approval:
        raise HTTPException(400, f"Proposal not pending (status={p.status.value})")

    p.decided_by_user_id = user.id
    p.decided_at = datetime.utcnow()

    if not body.approve:
        p.status = models.ProposalStatus.rejected_by_user
        audit.log(db, user.org_id, "proposal.rejected_by_user", actor_user_id=user.id,
                  target_type="proposal", target_id=p.id, payload={"note": body.note})
        db.commit()
        return {"status": p.status.value}

    p.status = models.ProposalStatus.approved
    audit.log(db, user.org_id, "proposal.approved_by_user", actor_user_id=user.id,
              target_type="proposal", target_id=p.id, payload={"note": body.note})

    agent = db.query(models.Agent).filter_by(id=p.agent_id).one()
    conn = db.query(models.BrokerConnection).filter_by(id=agent.broker_connection_id).one_or_none()
    if conn is None:
        raise HTTPException(400, "Agent has no broker; cannot execute")

    db.commit()
    _execute_approved(db, agent, conn, p)
    return {"status": p.status.value}
