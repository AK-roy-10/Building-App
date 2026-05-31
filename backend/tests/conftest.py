"""Shared test fixtures: per-test fresh SQLite, app TestClient."""
import sys, pathlib, os
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("APP_SECRET", "test-secret-test-secret-test-secret-test")
os.environ.setdefault("JWT_SECRET", "test-jwt")


@pytest.fixture(autouse=True)
def _per_test_db(tmp_path):
    """Rebind engine + SessionLocal to a fresh SQLite file per test."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app import database

    db_file = tmp_path / "t.db"
    new_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False},
                               future=True)
    new_session = sessionmaker(bind=new_engine, autoflush=False, autocommit=False,
                               expire_on_commit=False, future=True)
    database.engine = new_engine
    database.SessionLocal = new_session

    from app import models  # noqa: F401
    database.Base.metadata.create_all(bind=new_engine)
    database._seed_plans()
    yield
    new_engine.dispose()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
