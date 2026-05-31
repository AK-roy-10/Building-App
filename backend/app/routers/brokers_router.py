"""Broker connections CRUD. Credentials are encrypted at rest."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_role
from .. import models, schemas, audit
from ..auth import encrypt_secret
from ..entitlements import check_quota, require_in_list

router = APIRouter(prefix="/api/broker-connections", tags=["brokers"])


@router.get("")
def list_connections(user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    rows = db.query(models.BrokerConnection).filter_by(org_id=user.org_id).all()
    return [{"id": r.id, "broker": r.broker, "label": r.label,
             "trade_scope": r.trade_scope, "enabled": r.enabled,
             "cash_cents": r.cash_cents, "positions": r.positions_json}
            for r in rows]


@router.post("", status_code=201)
def create_connection(body: schemas.BrokerConnectionCreate,
                      user: models.User = Depends(require_role("owner", "admin", "trader")),
                      db: Session = Depends(get_db)):
    if body.broker not in ("paper", "alpaca"):
        raise HTTPException(400, "Unsupported broker")
    require_in_list(db, user.org_id, "allowed_trade_scopes", body.trade_scope)
    current = db.query(models.BrokerConnection).filter_by(org_id=user.org_id).count()
    check_quota(db, user.org_id, "max_broker_connections", current)

    enc = ""
    if body.api_key or body.api_secret:
        enc = encrypt_secret(json.dumps({"api_key": body.api_key or "",
                                         "api_secret": body.api_secret or ""}))
    conn = models.BrokerConnection(
        org_id=user.org_id, broker=body.broker, label=body.label,
        trade_scope=body.trade_scope, encrypted_credentials=enc,
    )
    db.add(conn)
    audit.log(db, user.org_id, "broker.connect", actor_user_id=user.id,
              target_type="broker_connection", target_id=conn.id,
              payload={"broker": body.broker, "label": body.label, "trade_scope": body.trade_scope,
                       "api_key": "***" if body.api_key else None})
    db.commit()
    return {"id": conn.id}


@router.delete("/{conn_id}", status_code=204)
def delete_connection(conn_id: str,
                      user: models.User = Depends(require_role("owner", "admin")),
                      db: Session = Depends(get_db)):
    conn = db.query(models.BrokerConnection).filter_by(id=conn_id, org_id=user.org_id).one_or_none()
    if not conn:
        raise HTTPException(404, "Not found")
    db.delete(conn)
    audit.log(db, user.org_id, "broker.disconnect", actor_user_id=user.id,
              target_type="broker_connection", target_id=conn_id, payload={})
    db.commit()
