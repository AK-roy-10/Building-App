"""FastAPI app entrypoint."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from .database import init_db
from .routers.auth_router import router as auth_router
from .routers.plans_router import router as plans_router
from .routers.brokers_router import router as brokers_router
from .routers.agents_router import router as agents_router
from .routers.approvals_router import router as approvals_router
from .routers.audit_router import router as audit_router
from .routers.ui_router import router as ui_router

app = FastAPI(
    title="AI Agentic Trading SaaS — MVP",
    description=(
        "Multi-tenant SaaS for building & running AI trading/research agents. "
        "Not financial advice. The LLM never executes trades; all orders pass "
        "through a deterministic risk engine and (for live trading) explicit "
        "user approval."
    ),
    version="0.1.0",
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"ok": True}


app.include_router(auth_router)
app.include_router(plans_router)
app.include_router(brokers_router)
app.include_router(agents_router)
app.include_router(approvals_router)
app.include_router(audit_router)
app.include_router(ui_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.exception_handler(404)
async def not_found(_, exc):
    return JSONResponse({"detail": "Not found"}, status_code=404)
