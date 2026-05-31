"""LLM providers + finance model catalog endpoints."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from .. import models
from ..llms.base import list_providers
from ..llms.models import list_models
from ..entitlements import get_org_entitlements

router = APIRouter(prefix="/api/llm", tags=["llms"])


@router.get("/providers")
def providers(user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    ent = get_org_entitlements(db, user.org_id)
    allowed = set(ent.get("allowed_llm_providers") or [])
    wildcard = "*" in allowed
    out = []
    for p in list_providers():
        d = p.__dict__ if hasattr(p, "__dict__") else dict(p)
        d["available"] = wildcard or d.get("code") in allowed
        out.append(d)
    return out


@router.get("/models")
def models_endpoint(tag: Optional[str] = None,
                    provider: Optional[str] = None,
                    task: Optional[str] = None,
                    user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    ent = get_org_entitlements(db, user.org_id)
    allowed_models = set(ent.get("allowed_models") or [])
    allowed_tags = set(ent.get("allowed_llm_tags") or [])
    allowed_providers = set(ent.get("allowed_llm_providers") or [])
    cost_cap = float(ent.get("max_llm_cost_per_1k_in") or 0.0)
    out = []
    for m in list_models(tag=tag, provider=provider, task=task):
        d = m.to_dict()
        d["available"] = (
            ("*" in allowed_models or m.id in allowed_models)
            and ("*" in allowed_providers or m.provider in allowed_providers)
            and (not m.tags or "*" in allowed_tags
                 or any(t in allowed_tags for t in m.tags))
            and (cost_cap == 0.0 or m.cost_per_1k_in <= cost_cap or m.cost_per_1k_in == 0)
        )
        out.append(d)
    return out
