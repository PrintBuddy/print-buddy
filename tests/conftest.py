import uuid as _uuid_mod

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import sqltypes
from sqlmodel import Session, SQLModel, create_engine

# Importing the app transitively imports every route/service/model module,
# registering all tables with SQLModel.metadata. This must happen at conftest
# import time (before any fixture runs `create_all`), not lazily inside a
# fixture body — otherwise `create_all` runs against an empty metadata for
# any test file that doesn't already import the models itself.
from src.main import app
from src.core.limiter import limiter
from src.core.security import Security
from src.db.main import get_session
from src.db.models.user import User


# Application code passes ids around as plain strings (e.g. `token.credentials`
# straight from a decoded JWT) and relies on Postgres's native UUID type
# coercing them automatically. SQLAlchemy's generic Uuid type — used here
# because SQLite has no native UUID type — requires real uuid.UUID objects
# and raises on a plain string. Patch it once, test-side only, so the SQLite
# test DB tolerates the same strings Postgres already does in production.
_original_bind_processor = sqltypes.Uuid.bind_processor


def _string_tolerant_bind_processor(self, dialect):
    processor = _original_bind_processor(self, dialect)
    if processor is None:
        return None

    def process(value):
        if isinstance(value, str):
            value = _uuid_mod.UUID(value)
        return processor(value)

    return process


sqltypes.Uuid.bind_processor = _string_tolerant_bind_processor


@pytest.fixture
def engine():
    # check_same_thread=False + StaticPool: FastAPI runs sync route handlers
    # in a worker thread, so `client` fixture requests touch this DB from a
    # different thread than the one that ran create_all(). A plain
    # "sqlite://" in-memory DB is per-connection — without StaticPool
    # forcing every checkout to share the one connection, the worker thread
    # can get a fresh, table-less in-memory DB instead of this one.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(session, engine, monkeypatch):
    """
    A FastAPI TestClient wired to the SQLite test DB. Overrides the
    get_session dependency for regular routes, and repoints db.main's
    module-level `engine` since AdminTokenBearer opens its own
    `Session(engine)` directly rather than going through a dependency.
    """
    # AdminTokenBearer does `from ...db.main import engine` and uses that
    # name directly — patching db.main's own attribute doesn't reach an
    # already-bound `from ... import engine` reference elsewhere, so the
    # token module's copy of the name needs patching too.
    monkeypatch.setattr("src.db.main.engine", engine)
    monkeypatch.setattr("src.api.dependencies.token.engine", engine)
    app.dependency_overrides[get_session] = lambda: session
    # The rate limiter's in-memory storage is a module-level singleton
    # shared across the whole test run; reset it so one test's requests
    # don't count against another test's rate limit.
    limiter._storage.reset()
    # Deliberately NOT used as a context manager: that would run the app's
    # lifespan (starting the APScheduler singleton) on every test, and the
    # scheduler doesn't tear down cleanly across repeated test runs. Route
    # tests don't need the scheduler running.
    # TrustedHostMiddleware rejects the httpx TestClient's default
    # "testserver" Host header — 127.0.0.1 is in the app's allowed_hosts.
    test_client = TestClient(app, base_url="http://127.0.0.1")
    yield test_client
    app.dependency_overrides.clear()


def make_token(user_id) -> str:
    return Security.create_token({"uid": str(user_id)})


def make_user(session, **overrides):
    """Create and persist a User row with sane defaults, overridable per-test."""
    import uuid as _uuid

    defaults = dict(
        username=f"user_{_uuid.uuid4().hex[:8]}",
        name="Test",
        surname="User",
        pwd=Security.hash_password("secretpassword"),
        email=f"{_uuid.uuid4().hex[:8]}@example.com",
        balance=0.0,
        credit_limit=0.0,
    )
    defaults.update(overrides)
    user = User(**defaults)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
