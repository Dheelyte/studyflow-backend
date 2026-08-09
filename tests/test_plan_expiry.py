"""Lazy safety net for a missed `subscription.disable` webhook.

`user.plan` is the only gate on paid features and that webhook is normally the
only thing that clears it, so a lost delivery leaves a user on Pro forever.
When a lapsed subscriber uses something their subscription pays for, we confirm
with Paystack and downgrade — while never revoking access on an API hiccup.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.billing import Subscription
from app.models.user import User
from app.services.paystack import PaystackError

# Hits the plan-aware dependency without needing a course or topic to exist.
GATED = "/api/v1/billing/status"


def days_ago(n):
    return datetime.now(timezone.utc) - timedelta(days=n)


def days_ahead(n):
    return datetime.now(timezone.utc) + timedelta(days=n)


def as_utc(dt):
    """SQLite drops tzinfo on round-trip; Postgres keeps it. Normalise so the
    assertions work on both (reconcile_plan does the same for real)."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def make_subscriber(session_factory, user_id, expires_at, code="SUB_live"):
    async with session_factory() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        user.plan = "pro"
        user.plan_expires_at = expires_at
        session.add(
            Subscription(
                user_id=user_id,
                tier="pro",
                status="active",
                interval="monthly",
                paystack_plan_code="PLN_pro_m",
                paystack_subscription_code=code,
                paystack_email_token="tok",
                current_period_end=expires_at,
            )
        )
        await session.commit()


async def read(session_factory, user_id):
    async with session_factory() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        sub = (
            await session.execute(select(Subscription).where(Subscription.user_id == user_id))
        ).scalars().first()
        return user, sub


# --- the hot path must cost nothing ---------------------------------------


async def test_free_user_never_calls_paystack(client, billing_settings, paystack_mock, test_user):
    response = await client.get(GATED)
    assert response.status_code == 200
    assert paystack_mock["fetch_subscription"] == []


async def test_healthy_subscriber_never_calls_paystack(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    await make_subscriber(session_factory, test_user.id, days_ahead(20))

    response = await client.get(GATED)
    assert response.status_code == 200
    assert paystack_mock["fetch_subscription"] == [], "no call while the plan is current"

    user, _ = await read(session_factory, test_user.id)
    assert user.plan == "pro"


async def test_within_grace_is_left_alone(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    """Expired yesterday: Paystack may still be retrying the renewal."""
    await make_subscriber(session_factory, test_user.id, days_ago(1))

    await client.get(GATED)
    assert paystack_mock["fetch_subscription"] == []

    user, _ = await read(session_factory, test_user.id)
    assert user.plan == "pro"


# --- past the grace window -------------------------------------------------


async def test_expired_subscription_downgrades(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    await make_subscriber(session_factory, test_user.id, days_ago(10))
    paystack_mock["subscription_state"]["SUB_live"] = {"status": "complete"}

    await client.get(GATED)
    assert paystack_mock["fetch_subscription"] == ["SUB_live"]

    user, sub = await read(session_factory, test_user.id)
    assert user.plan == "free"
    assert user.plan_expires_at is None
    assert sub.status == "cancelled"


async def test_still_active_at_paystack_self_heals(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    """The disable webhook was never missed — the renewal one was. Keep the
    tier, refresh the date, and stop re-checking on every request."""
    await make_subscriber(session_factory, test_user.id, days_ago(10))
    renewed = days_ahead(20)
    paystack_mock["subscription_state"]["SUB_live"] = {
        "status": "active",
        "next_payment_date": renewed.isoformat(),
    }

    await client.get(GATED)
    user, sub = await read(session_factory, test_user.id)
    assert user.plan == "pro", "must not downgrade a live subscription"
    assert user.plan_expires_at is not None
    assert as_utc(user.plan_expires_at) > datetime.now(timezone.utc)
    assert as_utc(sub.current_period_end) > datetime.now(timezone.utc)

    # Second request sees a current plan, so it must not call Paystack again.
    await client.get(GATED)
    assert paystack_mock["fetch_subscription"] == ["SUB_live"], "should not re-check once healed"


async def test_paystack_failure_fails_open(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    """An outage must never revoke a paying customer's access."""
    await make_subscriber(session_factory, test_user.id, days_ago(10))
    paystack_mock["subscription_state"]["SUB_live"] = PaystackError("service unavailable")

    response = await client.get(GATED)
    assert response.status_code == 200

    user, sub = await read(session_factory, test_user.id)
    assert user.plan == "pro", "keep access when we cannot confirm otherwise"
    assert sub.status == "active"


async def test_paid_plan_with_no_subscription_row_downgrades(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    """Nothing backs the paid tier, so there is nothing to confirm."""
    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.id == test_user.id))
        ).scalar_one()
        user.plan = "pro"
        user.plan_expires_at = days_ago(10)
        await session.commit()

    await client.get(GATED)
    assert paystack_mock["fetch_subscription"] == []

    user, _ = await read(session_factory, test_user.id)
    assert user.plan == "free"


async def test_null_expiry_is_never_treated_as_expired(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    """A user upgraded but not yet given a period end (charge.success lands
    before subscription.create) must not be downgraded in that window."""
    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.id == test_user.id))
        ).scalar_one()
        user.plan = "pro"
        user.plan_expires_at = None
        await session.commit()

    await client.get(GATED)
    assert paystack_mock["fetch_subscription"] == []

    user, _ = await read(session_factory, test_user.id)
    assert user.plan == "pro"


async def test_grace_period_is_configurable(
    client, billing_settings, paystack_mock, test_user, session_factory, monkeypatch
):
    monkeypatch.setattr(settings, "PLAN_EXPIRY_GRACE_DAYS", 30)
    await make_subscriber(session_factory, test_user.id, days_ago(10))

    await client.get(GATED)
    assert paystack_mock["fetch_subscription"] == [], "10 days lapsed is inside a 30-day grace"

    user, _ = await read(session_factory, test_user.id)
    assert user.plan == "pro"
