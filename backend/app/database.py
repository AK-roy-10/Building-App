"""SQLAlchemy engine, session, Base."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator

from .config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables and seed default plans."""
    # Import models so they register with Base.metadata
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _seed_plans()


def _seed_plans() -> None:
    from . import models
    from .entitlements import DEFAULT_PLANS
    with SessionLocal() as db:
        for code, spec in DEFAULT_PLANS.items():
            existing = db.query(models.Plan).filter_by(code=code).one_or_none()
            if existing:
                existing.name = spec["name"]
                existing.price_cents = spec["price_cents"]
                existing.entitlements_json = spec["entitlements"]
            else:
                db.add(models.Plan(
                    code=code,
                    name=spec["name"],
                    price_cents=spec["price_cents"],
                    entitlements_json=spec["entitlements"],
                ))
        db.commit()
