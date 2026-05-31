"""Plans + subscriptions (subscription stubbed; integrate Stripe in production)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_role
from .. import models, schemas, audit
from ..entitlements import DEFAULT_PLANS

router = APIRouter(prefix="/api", tags=["plans"])


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    rows = db.query(models.Plan).all()
    return [{"code": p.code, "name": p.name, "price_cents": p.price_cents,
             "entitlements": p.entitlements_json} for p in rows] or [
        {"code": k, **v} for k, v in DEFAULT_PLANS.items()
    ]


@router.post("/subscriptions")
def subscribe(body: schemas.SubscribeRequest,
              user: models.User = Depends(require_role("owner", "admin")),
              db: Session = Depends(get_db)):
    plan = db.query(models.Plan).filter_by(code=body.plan_code).one_or_none()
    if not plan:
        raise HTTPException(404, "Unknown plan")
    # In production, here you'd create a Stripe Checkout session and return the URL.
    # For MVP we mark current sub canceled and create a new active one.
    current = db.query(models.Subscription).filter_by(org_id=user.org_id, status="active").all()
    for c in current:
        c.status = "canceled"
    sub = models.Subscription(org_id=user.org_id, plan_code=plan.code, status="active")
    db.add(sub)
    audit.log(db, user.org_id, "subscription.changed", actor_user_id=user.id,
              target_type="subscription", target_id=sub.id,
              payload={"plan_code": plan.code})
    db.commit()
    return {"ok": True, "plan_code": plan.code}


@router.get("/me")
def me(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.query(models.Subscription).filter_by(org_id=user.org_id, status="active").first()
    org = db.query(models.Organization).filter_by(id=user.org_id).one()
    return {
        "user": {"id": user.id, "email": user.email, "role": user.role.value},
        "org": {"id": org.id, "name": org.name, "kill_switch": org.kill_switch,
                "risk_ack_accepted": org.risk_ack_accepted,
                "daily_loss_limit_cents": org.daily_loss_limit_cents},
        "plan": sub.plan_code if sub else "free",
    }


@router.post("/org/kill-switch")
def kill_switch(value: bool, user: models.User = Depends(require_role("owner", "admin")),
                db: Session = Depends(get_db)):
    org = db.query(models.Organization).filter_by(id=user.org_id).one()
    org.kill_switch = bool(value)
    audit.log(db, user.org_id, "org.kill_switch", actor_user_id=user.id,
              target_type="org", target_id=org.id, payload={"value": value})
    db.commit()
    return {"ok": True, "kill_switch": org.kill_switch}
