"""Audit log query endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from .. import models

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def list_events(limit: int = 100,
                user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    rows = (db.query(models.AuditEvent)
            .filter_by(org_id=user.org_id)
            .order_by(models.AuditEvent.created_at.desc())
            .limit(min(limit, 500)).all())
    return [{"id": r.id, "event_type": r.event_type, "actor_type": r.actor_type,
             "actor_user_id": r.actor_user_id, "target_type": r.target_type,
             "target_id": r.target_id, "payload": r.payload_json,
             "created_at": r.created_at} for r in rows]
