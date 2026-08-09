"""Scheduled sweep: POST /billing/reconcile.

The lazy expiry check only fires when a user comes back. This endpoint settles
the ones who don't, so subscriber counts stay honest. It's called by a
scheduler, so it authenticates with a shared secret rather than a session.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.billing import Subscription
from app.models.user import User
from app.services.paystack import PaystackError

PATH = "/api/v1/billing/reconcile"
SECRET = "s3cr3t-sweep-token"


@pytest.fixture
def reconcile_secret(monkeypatch):
    monkeypatch.setattr(settings, "RECONCILE_SECRET", SECRET)
    return SECRET


def days_ago(n):
    return datetime.now(timezone.utc) - timedelta(days=n)


def days_ahead(n):
    return datetime.now(timezone.utc) + timedelta(days=n)


async def add_user(session_factory, email, plan, expires_at, sub_code=None):
    async with session_factory() as session:
        user = User(
            email=email, password_hash="h", first_name="A", last_name="B",
            plan=plan, plan_expires_at=expires_at,
        )
        session.add(user)
        await session.flush()
        if sub_code:
            session.add(
                Subscription(
                    user_id=user.id, tier=plan, status="active", interval="monthly",
                    paystack_plan_code="PLN_pro_m",
                    paystack_subscription_code=sub_code,
                    paystack_email_token="tok",
                    current_period_end=expires_at,
                )
            )
        await session.commit()
        return user.id


async def plan_of(session_factory, user_id):
    async with session_factory() as session:
        return (
            await session.execute(select(User.plan).where(User.id == user_id))
        ).scalar_one()


# --- authentication --------------------------------------------------------


async def test_rejects_missing_secret(client, reconcile_secret):
    assert (await client.post(PATH)).status_code == 401


async def test_rejects_wrong_secret(client, reconcile_secret):
    response = await client.post(PATH, headers={"x-reconcile-secret": "nope"})
    assert response.status_code == 401


async def test_fails_closed_when_no_secret_configured(client, monkeypatch):
    """An unset secret must disable the endpoint, not leave it open."""
    monkeypatch.setattr(settings, "RECONCILE_SECRET", "")
    response = await client.post(PATH, headers={"x-reconcile-secret": ""})
    assert response.status_code == 401


async def test_accepts_correct_secret(client, reconcile_secret, paystack_mock):
    response = await client.post(PATH, headers={"x-reconcile-secret": SECRET})
    assert response.status_code == 200
    assert response.json()["scanned"] == 0


# --- sweeping --------------------------------------------------------------


async def test_downgrades_dormant_lapsed_subscriber(
    client, reconcile_secret, paystack_mock, session_factory
):
    """The case the lazy check can never catch: lapsed and never came back."""
    user_id = await add_user(session_factory, "gone@x.com", "pro", days_ago(40), "SUB_gone")
    paystack_mock["subscription_state"]["SUB_gone"] = {"status": "complete"}

    response = await client.post(PATH, headers={"x-reconcile-secret": SECRET})
    body = response.json()
    assert body["scanned"] == 1
    assert body["downgraded"] == 1
    assert await plan_of(session_factory, user_id) == "free"


async def test_leaves_healthy_and_free_users_alone(
    client, reconcile_secret, paystack_mock, session_factory
):
    healthy = await add_user(session_factory, "ok@x.com", "pro", days_ahead(20), "SUB_ok")
    free = await add_user(session_factory, "free@x.com", "free", None)

    response = await client.post(PATH, headers={"x-reconcile-secret": SECRET})
    assert response.json()["scanned"] == 0, "neither row should even be selected"
    assert paystack_mock["fetch_subscription"] == []
    assert await plan_of(session_factory, healthy) == "pro"
    assert await plan_of(session_factory, free) == "free"


async def test_within_grace_is_not_swept(
    client, reconcile_secret, paystack_mock, session_factory
):
    user_id = await add_user(session_factory, "recent@x.com", "pro", days_ago(1), "SUB_r")

    response = await client.post(PATH, headers={"x-reconcile-secret": SECRET})
    assert response.json()["scanned"] == 0
    assert await plan_of(session_factory, user_id) == "pro"


async def test_still_active_subscription_is_healed_not_downgraded(
    client, reconcile_secret, paystack_mock, session_factory
):
    user_id = await add_user(session_factory, "missed@x.com", "pro", days_ago(40), "SUB_live")
    paystack_mock["subscription_state"]["SUB_live"] = {
        "status": "active",
        "next_payment_date": days_ahead(20).isoformat(),
    }

    body = (await client.post(PATH, headers={"x-reconcile-secret": SECRET})).json()
    assert body["downgraded"] == 0
    assert body["still_active"] == 1
    assert await plan_of(session_factory, user_id) == "pro"


async def test_one_bad_account_does_not_abort_the_batch(
    client, reconcile_secret, paystack_mock, session_factory
):
    """A Paystack failure on one user must not strand the rest of the sweep."""
    broken = await add_user(session_factory, "broken@x.com", "pro", days_ago(50), "SUB_bad")
    ok = await add_user(session_factory, "ok2@x.com", "pro", days_ago(40), "SUB_ok2")
    paystack_mock["subscription_state"]["SUB_bad"] = PaystackError("boom")
    paystack_mock["subscription_state"]["SUB_ok2"] = {"status": "complete"}

    body = (await client.post(PATH, headers={"x-reconcile-secret": SECRET})).json()
    assert body["scanned"] == 2
    assert body["downgraded"] == 1, "the healthy-to-process user is still handled"
    # PaystackError is swallowed by reconcile_plan (fail open), so the broken
    # account keeps its plan and is retried next run rather than counted as an error.
    assert await plan_of(session_factory, broken) == "pro"
    assert await plan_of(session_factory, ok) == "free"


async def test_batch_limit_is_respected(
    client, reconcile_secret, paystack_mock, session_factory
):
    for i in range(4):
        code = f"SUB_{i}"
        await add_user(session_factory, f"u{i}@x.com", "pro", days_ago(30 + i), code)
        paystack_mock["subscription_state"][code] = {"status": "complete"}

    body = (await client.post(f"{PATH}?limit=2", headers={"x-reconcile-secret": SECRET})).json()
    assert body["scanned"] == 2, "must not process the whole backlog in one run"

    # The remainder is picked up next run — nothing is stranded.
    body = (await client.post(PATH, headers={"x-reconcile-secret": SECRET})).json()
    assert body["scanned"] == 2


async def test_oldest_lapsed_are_swept_first(
    client, reconcile_secret, paystack_mock, session_factory
):
    """Ordering matters: without it a backlog could retry the same rows forever."""
    await add_user(session_factory, "newer@x.com", "pro", days_ago(10), "SUB_new")
    await add_user(session_factory, "older@x.com", "pro", days_ago(90), "SUB_old")
    for code in ("SUB_new", "SUB_old"):
        paystack_mock["subscription_state"][code] = {"status": "complete"}

    await client.post(f"{PATH}?limit=1", headers={"x-reconcile-secret": SECRET})
    assert paystack_mock["fetch_subscription"] == ["SUB_old"]
