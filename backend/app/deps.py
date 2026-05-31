"""Shared FastAPI dependencies."""
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from . import models
from .auth import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _token_from_request(request: Request, bearer: Optional[str]) -> Optional[str]:
    if bearer:
        return bearer
    # also accept session cookie for the HTML UI
    return request.cookies.get("access_token")


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    raw = _token_from_request(request, token)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_access_token(raw)
    if not payload or "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = db.query(models.User).filter_by(id=payload["sub"]).one_or_none()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def try_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    raw = _token_from_request(request, token)
    if not raw:
        return None
    payload = decode_access_token(raw)
    if not payload:
        return None
    return db.query(models.User).filter_by(id=payload.get("sub")).one_or_none()


def require_role(*roles: str):
    def _check(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role.value not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {roles}")
        return user
    return _check


def get_org(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> models.Organization:
    org = db.query(models.Organization).filter_by(id=user.org_id).one_or_none()
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Org missing")
    return org
