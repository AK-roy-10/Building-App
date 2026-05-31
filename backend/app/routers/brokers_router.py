"""Broker connections CRUD + verify. Credentials are encrypted at rest."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_role
from .. import models, schemas, audit
from ..auth import encrypt_secret
from ..entitlements import check_quota, require_in_list
from ..brokers import known_broker_codes, list_broker_catalog, get_broker, BrokerError

router = APIRouter(prefix="/api/broker-connections", tags=["brokers"])


@router.get("/catalog")
def broker_catalog():
    """Public catalog of broker capabilities — for the agent-create UI."""
    return list_broker_catalog()


@router.get("")
def list_connections(user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    rows = db.query(models.BrokerConnection).filter_by(org_id=user.org_id).all()
    return [{"id": r.id, "broker": r.broker, "label": r.label,
             "trade_scope": r.trade_scope, "enabled": r.enabled,
             "cash_cents": r.cash_cents, "positions": r.positions_json,
             "asset_classes": r.asset_classes_json or []}
            for r in rows]


@router.post("", status_code=201)
def create_connection(body: schemas.BrokerConnectionCreate,
                      user: models.User = Depends(require_role("owner", "admin", "trader")),
                      db: Session = Depends(get_db)):
    if body.broker not in known_broker_codes():
        raise HTTPException(400, f"Unsupported broker '{body.broker}'")
    require_in_list(db, user.org_id, "allowed_brokers", body.broker)
    require_in_list(db, user.org_id, "allowed_trade_scopes", body.trade_scope)
    for ac in body.asset_classes:
        require_in_list(db, user.org_id, "allowed_asset_classes", ac)
    current = db.query(models.BrokerConnection).filter_by(org_id=user.org_id).count()
    check_quota(db, user.org_id, "max_broker_connections", current)

    enc = ""
    cred_payload = {}
    if body.api_key or body.api_secret:
        cred_payload.update({"api_key": body.api_key or "",
                             "api_secret": body.api_secret or ""})
    if body.extra:
        cred_payload.update(body.extra)
    if cred_payload:
        enc = encrypt_secret(json.dumps(cred_payload))
    conn = models.BrokerConnection(
        org_id=user.org_id, broker=body.broker, label=body.label,
        trade_scope=body.trade_scope, encrypted_credentials=enc,
        asset_classes_json=body.asset_classes or [],
    )
    db.add(conn)
    audit.log(db, user.org_id, "broker.connect", actor_user_id=user.id,
              target_type="broker_connection", target_id=conn.id,
              payload={"broker": body.broker, "label": body.label, "trade_scope": body.trade_scope,
                       "api_key": "***" if body.api_key else None,
                       "asset_classes": body.asset_classes})
    db.commit()
    return {"id": conn.id}


@router.post("/{conn_id}/verify")
def verify_connection(conn_id: str,
                      user: models.User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    conn = db.query(models.BrokerConnection).filter_by(id=conn_id, org_id=user.org_id).one_or_none()
    if not conn:
        raise HTTPException(404, "Not found")
    try:
        broker = get_broker(db, conn)
        result = broker.verify()
    except BrokerError as e:
        result = {"ok": False, "detail": str(e)}
    except Exception as e:  # defensive — never leak stack traces to the client
        result = {"ok": False, "detail": f"verify failed: {type(e).__name__}"}
    return result


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
