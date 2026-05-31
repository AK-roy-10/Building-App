"""Entitlements / plan gating tests."""
import pytest
from app.entitlements import (
    DEFAULT_PLANS, get_org_entitlements, check_quota, require_in_list, EntitlementError,
)
from app import database
from app import models


def _make_org(plan_code="free"):
    with database.SessionLocal() as db:
        org = models.Organization(name="Test", risk_ack_accepted=True)
        db.add(org); db.flush()
        db.add(models.Subscription(org_id=org.id, plan_code=plan_code, status="active"))
        db.commit()
        return org.id


def test_default_free_entitlements():
    org_id = _make_org("free")
    with database.SessionLocal() as db:
        ent = get_org_entitlements(db, org_id)
    assert ent["max_agents"] == DEFAULT_PLANS["free"]["entitlements"]["max_agents"]
    assert "suggest" in ent["allowed_automation"]
    assert "live_manual" not in ent["allowed_automation"]


def test_quota_exceeded():
    org_id = _make_org("free")
    with database.SessionLocal() as db:
        with pytest.raises(EntitlementError):
            check_quota(db, org_id, "max_agents", 999)


def test_require_in_list_rejects_unallowed_automation_on_free():
    org_id = _make_org("free")
    with database.SessionLocal() as db:
        with pytest.raises(EntitlementError):
            require_in_list(db, org_id, "allowed_automation", "live_manual")


def test_pro_allows_live_manual():
    org_id = _make_org("pro")
    with database.SessionLocal() as db:
        require_in_list(db, org_id, "allowed_automation", "live_manual")
