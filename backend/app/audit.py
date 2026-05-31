"""Append-only audit logging."""
from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from . import models


def log(
    db: Session,
    org_id: str,
    event_type: str,
    *,
    actor_user_id: Optional[str] = None,
    actor_type: str = "user",
    target_type: str = "",
    target_id: str = "",
    payload: Optional[dict] = None,
) -> models.AuditEvent:
    # Redact obvious secret fields if a caller forgets.
    safe_payload = _redact(payload or {})
    ev = models.AuditEvent(
        org_id=org_id,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        payload_json=safe_payload,
    )
    db.add(ev)
    db.flush()
    return ev


_SECRET_KEYS = {"password", "api_key", "api_secret", "secret", "token", "encrypted_credentials"}


def _redact(payload: dict) -> dict:
    out = {}
    for k, v in payload.items():
        if k.lower() in _SECRET_KEYS:
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = _redact(v)
        else:
            out[k] = v
    return out
