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
    """Create tables, run lightweight column migrations, seed default plans."""
    # Import models so they register with Base.metadata
    from . import models  # noqa: F401
    from .markets import cache as _market_cache  # noqa: F401  (registers MarketBar table)
    Base.metadata.create_all(bind=engine)
    _auto_migrate_columns()
    _seed_plans()


def _auto_migrate_columns() -> None:
    """SQLite-friendly auto-migration: ALTER TABLE ADD COLUMN for any column
    declared on a model but missing from the existing table. This keeps
    pre-existing dev databases working when we add fields without users
    needing to wipe `trading.db`.
    """
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing:
                continue
            col_type = col.type.compile(dialect=engine.dialect)
            default_sql = ""
            if col.default is not None and getattr(col.default, "is_scalar", False):
                v = col.default.arg
                if isinstance(v, str):
                    default_sql = f" DEFAULT '{v}'"
                elif isinstance(v, bool):
                    default_sql = f" DEFAULT {1 if v else 0}"
                elif isinstance(v, (int, float)):
                    default_sql = f" DEFAULT {v}"
            stmt = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}{default_sql}'
            try:
                with engine.begin() as conn:
                    conn.execute(text(stmt))
            except Exception:
                # Best-effort migration; don't crash app startup on dev DBs.
                pass


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
