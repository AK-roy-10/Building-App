# AgentDesk — Multi-Tenant AI Agentic Trading SaaS (MVP)

A runnable MVP scaffold for a multi-tenant SaaS where users build, configure, and run AI-powered trading and research agents. Implements the phased architecture from `docs/architecture` (Phases 0–4 in one cohesive service so it is cheap to host today, and structured to split later).

> ⚠️ **Not financial advice.** This software is for education and research. Markets carry risk of loss. The LLM does **not** execute trades; it only summarizes and explains. Every trade flows through a **deterministic risk engine** and (for live trading) **explicit user approval**.

---

## What's inside

- **Multi-tenant**: every domain table carries `org_id`. JWT auth + role-based access (owner/admin/trader/viewer).
- **Plans & entitlements**: Free / Starter / Pro / Enterprise. Server-side enforced for every gated action (max agents, allowed strategies, allowed models, allowed automation level, allowed trade scopes, runs/day, …).
- **Broker connectors**: pluggable `BrokerConnector` interface. Built-in **Paper broker** (works offline, synthetic prices); **Alpaca** stub for paper/live. Credentials encrypted at rest (Fernet; swap to KMS in prod).
- **Agent builder**: pick a strategy, fill numeric parameters, choose automation level, broker, model. JSON-schema validated.
- **LLM (read-only)**: abstraction with mock + optional OpenAI. The LLM is given analytical context only — it has no tools that touch the broker.
- **Deterministic risk engine** (`app/risk_engine.py`): hard and soft checks (notional caps, cash/positions, daily-loss limit, kill-switch, allowlist, automation gating, live-scope requirement). Heavily unit-tested.
- **Agent runtime**: data → signal → LLM rationale → proposal → risk verdict → (approval if needed) → broker order → audit.
- **Approval inbox**: live-manual proposals queue here. One-click approve/reject.
- **Kill switch & daily-loss circuit breaker** at the org level.
- **Append-only audit log** of users, agents, and system actions.
- **Minimal server-rendered UI** (Jinja + HTMX) — no SPA needed to demo.
- **Tests** for the risk engine, entitlements, agent runtime, and HTTP smoke.

## Architecture summary

```
 Browser ── HTMX ──┐
                   ▼
              FastAPI app ───► Postgres / SQLite (multi-tenant via org_id)
                   │
                   ├── Background tasks (in-process for MVP; swap for Redis+RQ later)
                   │       └─ AgentRuntime
                   │             ├─ Strategy (deterministic) ──► ProposalDraft
                   │             ├─ LLM (read-only)         ──► rationale
                   │             ├─ RiskEngine (deterministic) ──► verdict
                   │             ├─ ApprovalGate (if live_manual) ──► user
                   │             └─ OrderRouter ──► BrokerConnector (Paper / Alpaca)
                   │
                   └─► AuditLog (append-only, redacted)
```

The boundary between **LLM (analyst)** and **risk engine + order router (executor)** is the most important safety property. The LLM is *never* given a place_order tool.

## Running

### Option A: Python (fastest)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # optional; defaults work for dev
uvicorn app.main:app --reload
```

Open <http://localhost:8000>. Sign up at `/signup`. The default DB is SQLite at `./trading.db`.

### Option B: Docker Compose (with Postgres)

```bash
cp .env.example .env
docker compose up --build
```

### Tests

```bash
cd backend
pytest
```

## Key endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/signup` | creates org + owner user + free subscription |
| POST | `/api/auth/login` | issues JWT (also set as cookie) |
| GET  | `/api/me` | current user / org / plan |
| GET/POST | `/api/plans`, `/api/subscriptions` | plan catalogue & change plan |
| POST | `/api/org/kill-switch?value=true` | engage kill switch |
| GET/POST/DELETE | `/api/broker-connections` | broker connections |
| GET  | `/api/agents/strategies` | strategy catalogue + JSON schemas |
| GET/POST | `/api/agents` | list/create agents (gated by plan) |
| POST | `/api/agents/{id}/run` | trigger an ad-hoc run (background task) |
| GET  | `/api/agents/{id}/runs` | recent runs |
| GET/POST | `/api/approvals`, `/api/approvals/{id}` | approval inbox |
| GET  | `/api/audit` | audit events |

## Plans (default)

| Plan | Agents | Connections | Automation levels | Trade scopes |
|---|---|---|---|---|
| free | 1 | 1 | suggest | paper |
| starter | 3 | 2 | suggest, paper | paper |
| pro | 10 | 5 | suggest, paper, live_manual | paper, live |
| enterprise | 1000 | 100 | suggest, paper, live_manual, live_auto | paper, live |

Edit `app/entitlements.py` to customize.

## Safety properties enforced by the code

1. **Suggest-only agents cannot place orders** (hard-rejected by the risk engine).
2. **Kill switch off** is verified on every proposal.
3. **Daily loss limit** is checked per proposal.
4. **Live automation requires `trade_scope=live`** on the broker connection.
5. **`live_manual` always routes to the approval inbox**, never auto-executes.
6. **`live_auto` proposals that consume >25 % of cash escalate to the approval inbox.**
7. **Per-order notional cap** is enforced regardless of plan.
8. **Symbol allowlist** enforced when set.
9. **Idempotency keys** on every broker order.
10. **Audit log entry** for every meaningful action; secret fields redacted.

## What is intentionally simplified (production TODOs)

- Replace in-process background tasks with **Redis + RQ/Celery** workers + a real scheduler.
- Replace local Fernet key with **AWS/GCP KMS** envelope encryption.
- Add **Stripe Checkout** + webhooks (the subscription endpoint is currently a stub).
- Add a **Next.js** frontend if you want a richer SPA experience; the JSON API is the same.
- Add a **vector DB** (pgvector → Pinecone) for research/news RAG.
- Add **TimescaleDB/ClickHouse** for tick history.
- Real broker reconciliation worker (poll fills, reconcile vs internal order state).
- SSO/SAML, SCIM, finer RBAC.
- Compliance: regional gating, SOC2 evidence collection, immutable export of audit log to object storage.

## File map

```
backend/
  app/
    main.py                # FastAPI app
    config.py              # env-loaded settings
    database.py            # SQLAlchemy session + seed
    models.py              # multi-tenant ORM
    schemas.py             # pydantic schemas
    auth.py                # JWT, password hashing, Fernet
    deps.py                # FastAPI dependencies (current_user, role gates)
    entitlements.py        # plan-gating (single source of truth)
    audit.py               # append-only logger w/ redaction
    risk_engine.py         # deterministic, NO LLM
    llm.py                 # mock + OpenAI; read-only analysis
    brokers/
      base.py              # interface
      paper.py             # built-in paper broker
      alpaca.py            # real REST stub
      registry.py          # factory
    agents/
      strategies.py        # momentum, mean_reversion, news_summary, portfolio_risk
      runtime.py           # full agent pipeline
    routers/               # auth, plans, brokers, agents, approvals, audit, ui
    templates/             # Jinja + HTMX UI
    static/app.css
  tests/
    test_risk_engine.py
    test_entitlements.py
    test_agent_runtime.py
    test_api_smoke.py
docker-compose.yml
.env.example
```

## License

See `LICENSE`.
