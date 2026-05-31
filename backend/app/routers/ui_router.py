"""Minimal server-rendered UI using Jinja + HTMX. Same backend, no SPA needed."""
import json
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import try_current_user
from .. import models
from ..entitlements import get_org_entitlements, DEFAULT_PLANS
from ..agents.strategies import STRATEGIES

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory="app/templates")


def _ctx(request: Request, user, db, **extra):
    base = {"request": request, "user": user}
    if user:
        org = db.query(models.Organization).filter_by(id=user.org_id).one()
        sub = db.query(models.Subscription).filter_by(org_id=user.org_id, status="active").first()
        base.update({
            "org": org,
            "plan_code": sub.plan_code if sub else "free",
            "entitlements": get_org_entitlements(db, user.org_id),
        })
    base.update(extra)
    return base


@router.get("/", response_class=HTMLResponse)
def home(request: Request, user=Depends(try_current_user), db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse("/login")
    return RedirectResponse("/dashboard")


@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request, user=Depends(try_current_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse("signup.html", _ctx(request, user, db))


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user=Depends(try_current_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse("login.html", _ctx(request, user, db))


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user=Depends(try_current_user), db: Session = Depends(get_db)):
    if not user: return RedirectResponse("/login")
    agents = db.query(models.Agent).filter_by(org_id=user.org_id).all()
    conns = db.query(models.BrokerConnection).filter_by(org_id=user.org_id).all()
    pending = db.query(models.Proposal).filter_by(
        org_id=user.org_id, status=models.ProposalStatus.requires_approval).count()
    return templates.TemplateResponse("dashboard.html", _ctx(
        request, user, db, agents=agents, connections=conns, pending_approvals=pending))


@router.get("/plans", response_class=HTMLResponse)
def plans_page(request: Request, user=Depends(try_current_user), db: Session = Depends(get_db)):
    if not user: return RedirectResponse("/login")
    plans = db.query(models.Plan).all() or []
    return templates.TemplateResponse("plans.html", _ctx(request, user, db, plans=plans))


@router.get("/brokers", response_class=HTMLResponse)
def brokers_page(request: Request, user=Depends(try_current_user), db: Session = Depends(get_db)):
    if not user: return RedirectResponse("/login")
    conns = db.query(models.BrokerConnection).filter_by(org_id=user.org_id).all()
    return templates.TemplateResponse("brokers.html", _ctx(request, user, db, connections=conns))


@router.get("/agents", response_class=HTMLResponse)
def agents_page(request: Request, user=Depends(try_current_user), db: Session = Depends(get_db)):
    if not user: return RedirectResponse("/login")
    agents = db.query(models.Agent).filter_by(org_id=user.org_id).all()
    return templates.TemplateResponse("agents.html", _ctx(request, user, db, agents=agents))


@router.get("/agents/new", response_class=HTMLResponse)
def new_agent_page(request: Request, user=Depends(try_current_user), db: Session = Depends(get_db)):
    if not user: return RedirectResponse("/login")
    conns = db.query(models.BrokerConnection).filter_by(org_id=user.org_id).all()
    return templates.TemplateResponse("agent_new.html", _ctx(
        request, user, db, connections=conns,
        strategies=[{"code": s.code, "name": s.name, "description": s.description,
                     "schema": json.dumps(s.config_schema, indent=2)}
                    for s in STRATEGIES.values()]))


@router.get("/agents/{agent_id}", response_class=HTMLResponse)
def agent_detail(agent_id: str, request: Request,
                 user=Depends(try_current_user), db: Session = Depends(get_db)):
    if not user: return RedirectResponse("/login")
    a = db.query(models.Agent).filter_by(id=agent_id, org_id=user.org_id).one_or_none()
    if not a: raise HTTPException(404)
    runs = (db.query(models.AgentRun).filter_by(agent_id=agent_id)
            .order_by(models.AgentRun.started_at.desc()).limit(20).all())
    proposals = (db.query(models.Proposal).filter_by(agent_id=agent_id)
                 .order_by(models.Proposal.created_at.desc()).limit(20).all())
    return templates.TemplateResponse("agent_detail.html", _ctx(
        request, user, db, agent=a, runs=runs, proposals=proposals))


@router.get("/approvals", response_class=HTMLResponse)
def approvals_page(request: Request, user=Depends(try_current_user), db: Session = Depends(get_db)):
    if not user: return RedirectResponse("/login")
    rows = (db.query(models.Proposal)
            .filter_by(org_id=user.org_id, status=models.ProposalStatus.requires_approval)
            .order_by(models.Proposal.created_at.desc()).all())
    return templates.TemplateResponse("approvals.html", _ctx(request, user, db, proposals=rows))


@router.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request, user=Depends(try_current_user), db: Session = Depends(get_db)):
    if not user: return RedirectResponse("/login")
    events = (db.query(models.AuditEvent).filter_by(org_id=user.org_id)
              .order_by(models.AuditEvent.created_at.desc()).limit(200).all())
    return templates.TemplateResponse("audit.html", _ctx(request, user, db, events=events))
