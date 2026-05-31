"""Auth: signup, login. Creates an Organization for the signup user (org owner)."""
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas, audit
from ..auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.TokenResponse, status_code=201)
def signup(body: schemas.SignupRequest, response: Response, db: Session = Depends(get_db)):
    if not body.accept_risk_disclaimer:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "You must accept the risk disclaimer to use this platform.")
    if db.query(models.User).filter_by(email=body.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    org = models.Organization(name=body.org_name, risk_ack_accepted=True)
    db.add(org)
    db.flush()
    user = models.User(
        email=body.email, password_hash=hash_password(body.password),
        org_id=org.id, role=models.RoleEnum.owner,
    )
    db.add(user)
    db.add(models.Subscription(org_id=org.id, plan_code="free", status="active"))
    audit.log(db, org.id, "user.signup", actor_user_id=user.id,
              target_type="user", target_id=user.id,
              payload={"email": body.email, "org_name": body.org_name})
    db.commit()
    token = create_access_token(user.id, {"org_id": org.id})
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    return schemas.TokenResponse(access_token=token)


@router.post("/login", response_model=schemas.TokenResponse)
def login(body: schemas.LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token = create_access_token(user.id, {"org_id": user.org_id})
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    audit.log(db, user.org_id, "user.login", actor_user_id=user.id,
              target_type="user", target_id=user.id, payload={"email": body.email})
    db.commit()
    return schemas.TokenResponse(access_token=token)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"ok": True}
