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
from sqlalchemy import select

from app.db.session import db_session, get_session, session_context
from app.dependencies.auth import get_auth_user
from app.exceptions.base import UnauthorizedError
from app.main import app
from app.models.base import Base
from app.models.user import User
from app.rate_limit import limiter
from app.services.paystack import PaystackClient, PaystackError

limiter.enabled = False


@pytest.fixture(autouse=True)
def _no_real_paystack(monkeypatch):
    """Hard stop against any test making a live Paystack HTTP call.

    Every Paystack method funnels through `_request`; stubbing it means an
    unmocked call raises instead of hitting the network. `paystack_mock` still
    overrides the higher-level methods, which no longer touch `_request`, so
    the two don't collide. Fail-open paths (e.g. the M1 price check) see this as
    a normal outage and behave exactly as they would in production.
    """
    async def _blocked(self, *args, **kwargs):
        raise PaystackError("Paystack network call not mocked in this test")

    monkeypatch.setattr(PaystackClient, "_request", _blocked)


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

    async def __call__(self):
        if self.user is None:
            raise UnauthorizedError("Not authenticated")
        # Reload from the request's session, because real auth queries the user
        # on every request. Returning the fixture's detached instance would hand
        # services a stale row that ignores anything committed since, and any
        # writes they make would never reach the database.
        session = get_session()
        result = await session.execute(select(User).where(User.id == self.user.id))
        return result.scalar_one()


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


@pytest.fixture
def paystack_mock(monkeypatch):
    """Record Paystack API calls instead of hitting the network."""
    calls = {
        "initialize": [],
        "disable": [],
        "verify": [],
        "fetch_plan": [],
        "fetch_subscription": [],
    }
    # Tests override this to say what Paystack currently reports for a
    # subscription: a dict to return, or a PaystackError instance to raise.
    subscription_state = {}

    # Amounts as Paystack reports them: kobo, matching the configured plans.
    PLAN_AMOUNTS = {
        "PLN_pro_m": 450000,
        "PLN_pro_y": 4500000,
        "PLN_max_m": 1000000,
        "PLN_max_y": 10000000,
    }

    async def fetch_plan(self, plan_code):
        calls["fetch_plan"].append(plan_code)
        if plan_code not in PLAN_AMOUNTS:
            raise PaystackError("Plan not found")
        return {"plan_code": plan_code, "amount": PLAN_AMOUNTS[plan_code], "currency": "NGN"}

    async def initialize_transaction(
        self, email, plan_code, amount_kobo, callback_url, metadata=None
    ):
        # Paystack rejects the call outright when amount is missing or zero.
        if not amount_kobo:
            raise PaystackError("Invalid Amount Sent")
        calls["initialize"].append({
            "email": email,
            "plan_code": plan_code,
            "amount_kobo": amount_kobo,
            "metadata": metadata,
        })
        return {"authorization_url": "https://checkout.paystack.com/x", "reference": "ref_new"}

    async def disable_subscription(self, subscription_code, email_token):
        calls["disable"].append({"code": subscription_code, "token": email_token})
        return {}

    async def fetch_subscription(self, subscription_code):
        calls["fetch_subscription"].append(subscription_code)
        state = subscription_state.get(subscription_code, {"status": "complete"})
        if isinstance(state, PaystackError):
            raise state
        return state

    async def verify_transaction(self, reference):
        calls["verify"].append(reference)
        return {
            "status": "success",
            "reference": reference,
            "amount": 450000,
            "currency": "NGN",
            "paid_at": "2026-08-01T10:00:00.000Z",
            # Email matches the default test_user so the verify ownership check
            # passes; tests for the *mismatch* case use a different caller.
            "customer": {"customer_code": "CUS_1", "email": "learner@example.com"},
            # transaction/verify returns `plan` as a bare plan-code STRING, not
            # an object like the webhooks do. Mocking the object shape here is
            # exactly what let an AttributeError reach production.
            "plan": "PLN_pro_m",
        }

    monkeypatch.setattr(PaystackClient, "fetch_plan", fetch_plan)
    monkeypatch.setattr(PaystackClient, "initialize_transaction", initialize_transaction)
    monkeypatch.setattr(PaystackClient, "disable_subscription", disable_subscription)
    monkeypatch.setattr(PaystackClient, "verify_transaction", verify_transaction)
    monkeypatch.setattr(PaystackClient, "fetch_subscription", fetch_subscription)
    calls["subscription_state"] = subscription_state
    return calls
