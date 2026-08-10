"""C1: /billing/verify activates the caller, so a transaction must be theirs.

A reference leaks through the Paystack redirect URL (history, logs,
screenshots), so without an ownership check any authenticated user could redeem
another user's payment onto their own account.
"""
import pytest
from sqlalchemy import select

from app.models.user import User
from app.services.paystack import PaystackClient


@pytest.fixture
def verify_returns(monkeypatch):
    """Let each test dictate the exact transaction/verify payload."""
    holder = {}

    async def verify_transaction(self, reference):
        return holder["payload"]

    monkeypatch.setattr(PaystackClient, "verify_transaction", verify_transaction)
    monkeypatch.setattr(
        PaystackClient, "fetch_plan",
        lambda self, code: _priced(code),
    )
    return holder


async def _priced(code):
    return {"amount": 450000, "currency": "NGN"}


async def other_user(session_factory):
    async with session_factory() as session:
        u = User(email="attacker@x.com", password_hash="h", first_name="E", last_name="F", plan="free")
        session.add(u)
        await session.commit()
        return u


async def plan_of(session_factory, user_id):
    async with session_factory() as session:
        return (await session.execute(select(User.plan).where(User.id == user_id))).scalar_one()


async def test_foreign_reference_is_rejected(
    client, billing_settings, verify_returns, test_user, session_factory
):
    """test_user (the caller) tries a reference whose metadata + email belong to
    someone else."""
    attacker = await other_user(session_factory)
    verify_returns["payload"] = {
        "status": "success",
        "reference": "ref_victim",
        "amount": 450000,
        "currency": "NGN",
        "metadata": {"user_id": str(attacker.id)},
        "customer": {"email": "attacker@x.com"},
        "plan": "PLN_pro_m",
    }

    # test_user is the authenticated caller (conftest default)
    response = await client.get("/api/v1/billing/verify?reference=ref_victim")
    assert response.status_code == 404, "must not confirm the reference exists"
    assert await plan_of(session_factory, test_user.id) == "free", "no tier granted"


async def test_owner_by_metadata_succeeds(
    client, billing_settings, verify_returns, test_user, session_factory
):
    verify_returns["payload"] = {
        "status": "success",
        "reference": "ref_mine",
        "amount": 450000,
        "currency": "NGN",
        "metadata": {"user_id": str(test_user.id)},
        "customer": {"email": "someone-else@x.com"},  # metadata wins
        "plan": "PLN_pro_m",
    }
    response = await client.get("/api/v1/billing/verify?reference=ref_mine")
    assert response.status_code == 200
    assert response.json()["plan"] == "pro"
    assert await plan_of(session_factory, test_user.id) == "pro"


async def test_owner_by_email_fallback_succeeds(
    client, billing_settings, verify_returns, test_user, session_factory
):
    """No metadata (older transaction) but the customer email matches."""
    verify_returns["payload"] = {
        "status": "success",
        "reference": "ref_email",
        "amount": 450000,
        "currency": "NGN",
        "metadata": {},
        "customer": {"email": "LEARNER@example.com"},  # case-insensitive
        "plan": "PLN_pro_m",
    }
    response = await client.get("/api/v1/billing/verify?reference=ref_email")
    assert response.status_code == 200
    assert await plan_of(session_factory, test_user.id) == "pro"


@pytest.mark.parametrize("bad", ["../plan/PLN_x", "abc def", "a/b", "x" * 200])
async def test_malformed_reference_rejected_at_router(client, billing_settings, bad):
    """C3, first line: path-injection shapes never reach the Paystack client."""
    response = await client.get("/api/v1/billing/verify", params={"reference": bad})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "method,attack,base_slashes",
    [
        # base_slashes = the fixed slashes in the endpoint path; the attack's own
        # "/" must be encoded, so the total slash count stays at the base.
        ("verify_transaction", "../subscription/SUB_x", 3),  # /transaction/verify/…
        ("fetch_subscription", "../plan/PLN_secret", 2),     # /subscription/…
        ("fetch_plan", "../transaction", 2),                 # /plan/…
    ],
)
async def test_client_quotes_path_values(monkeypatch, method, attack, base_slashes):
    """C3, second line: values from webhook payloads and the DB reach these
    methods without a router guard, so the client itself must encode them. The
    attack's "/" must be percent-encoded so it can't add a path segment — a
    literal ".." with no unescaped slash can't traverse."""
    from app.services.paystack import PaystackClient

    captured = {}

    async def fake_request(self, http_method, path, **kwargs):
        captured["path"] = path
        return {}

    monkeypatch.setattr(PaystackClient, "_request", fake_request)
    await getattr(PaystackClient(), method)(attack)

    path = captured["path"]
    assert path.count("/") == base_slashes, f"injected path segment(s): {path}"
    assert "%2F" in path, f"attack slash not encoded: {path}"
