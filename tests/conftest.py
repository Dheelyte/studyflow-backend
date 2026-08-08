import os

# Settings are constructed at import time , make sure required fields exist even
# without a local .env (CI). pydantic-settings gives process env vars priority
# over .env, so these also pin test-critical values (like USE_MOCK_DATA) against
# whatever a developer's local .env says.
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-32-chars!!")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/unused")
os.environ.setdefault("GOOGLE_API_KEY", "test")
os.environ["USE_MOCK_DATA"] = "true"
os.environ.setdefault("GOOGLE_OAUTH2_CLIENT_ID", "test")
os.environ.setdefault("GOOGLE_OAUTH2_CLIENT_SECRET", "test")
os.environ.setdefault("SOCIAL_GITHUB_CLIENT_ID", "test")
os.environ.setdefault("SOCIAL_GITHUB_CLIENT_SECRET", "test")
os.environ.setdefault("APPLE_CLIENT_ID", "test")
os.environ.setdefault("APPLE_TEAM_ID", "test")
os.environ.setdefault("APPLE_KEY_ID", "test")
os.environ.setdefault("APPLE_PRIVATE_KEY", "test")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db.session import db_session, session_context
from app.dependencies.auth import get_auth_user
from app.exceptions.base import UnauthorizedError
from app.main import app
from app.models.base import Base
from app.models.user import User
from app.rate_limit import limiter

limiter.enabled = False


@pytest_asyncio.fixture
async def db_engine():
    # StaticPool: every session shares the single in-memory database.
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def test_user(session_factory):
    async with session_factory() as session:
        user = User(
            email="learner@example.com",
            password_hash="x",
            first_name="Test",
            last_name="Learner",
            plan="free",
        )
        session.add(user)
        await session.commit()
    return user


class AuthOverride:
    """Mutable holder so tests can swap (or clear) the authenticated user."""

    def __init__(self, user=None):
        self.user = user

    def __call__(self):
        if self.user is None:
            raise UnauthorizedError("Not authenticated")
        return self.user


@pytest.fixture
def auth(test_user):
    return AuthOverride(test_user)


@pytest_asyncio.fixture
async def client(session_factory, auth):
    async def test_db_session():
        async with session_factory() as session:
            token = session_context.set(session)
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                session_context.reset(token)

    app.dependency_overrides[db_session] = test_db_session
    app.dependency_overrides[get_auth_user] = auth

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def billing_settings(monkeypatch):
    """Enable billing with known test plan codes."""
    monkeypatch.setattr(settings, "BILLING_ENABLED", True)
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_secret")
    monkeypatch.setattr(settings, "PAYSTACK_PLAN_CODE_PRO_MONTHLY", "PLN_pro_m")
    monkeypatch.setattr(settings, "PAYSTACK_PLAN_CODE_PRO_ANNUAL", "PLN_pro_y")
    monkeypatch.setattr(settings, "PAYSTACK_PLAN_CODE_MAX_MONTHLY", "PLN_max_m")
    monkeypatch.setattr(settings, "PAYSTACK_PLAN_CODE_MAX_ANNUAL", "PLN_max_y")
    return settings
