"""Recurring billing: Paystack auto-charges the saved card each interval.

Covers what happens across cycles, not just the first payment — access must
persist and the stored renewal date must roll forward, otherwise the profile
shows a renewal date in the past forever.
"""
import hashlib
import hmac
import json

from sqlalchemy import select

from app.models.billing import Subscription
from app.models.user import User

WEBHOOK = "/api/v1/billing/webhook/paystack"


async def send(client, event):
    body = json.dumps(event).encode()
    return await client.post(
        WEBHOOK,
        content=body,
        headers={
            "content-type": "application/json",
            "x-paystack-signature": hmac.new(
                b"sk_test_secret", body, hashlib.sha512
            ).hexdigest(),
        },
    )


def charge(user, reference):
    return {
        "event": "charge.success",
        "data": {
            "reference": reference,
            "amount": 450000,
            "currency": "NGN",
            "status": "success",
            "metadata": {"user_id": str(user.id)},
            "customer": {"email": user.email, "customer_code": "CUS_1"},
            "plan": {"plan_code": "PLN_pro_m"},
        },
    }


def invoice(next_payment_date, status="success"):
    return {
        "event": "invoice.update",
        "data": {
            "status": status,
            "paid": status == "success",
            "subscription": {
                "subscription_code": "SUB_1",
                "next_payment_date": next_payment_date,
            },
        },
    }


async def read(session_factory, user_id):
    async with session_factory() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        sub = (
            await session.execute(
                select(Subscription).where(Subscription.paystack_subscription_code == "SUB_1")
            )
        ).scalar_one_or_none()
        return user, sub


async def subscribe(client, user):
    """First payment: charge, then Paystack creates the subscription."""
    await send(client, charge(user, "ref_cycle_1"))
    await send(
        client,
        {
            "event": "subscription.create",
            "data": {
                "subscription_code": "SUB_1",
                "email_token": "tok_1",
                "next_payment_date": "2026-09-08T00:00:00.000Z",
                "customer": {"email": user.email, "customer_code": "CUS_1"},
                "plan": {"plan_code": "PLN_pro_m"},
            },
        },
    )


async def test_renewal_keeps_access_and_advances_the_date(
    client, billing_settings, test_user, session_factory
):
    await subscribe(client, test_user)
    user, sub = await read(session_factory, test_user.id)
    assert user.plan == "pro"
    assert sub.current_period_end.month == 9

    # A month later Paystack auto-debits the saved card and re-invoices.
    await send(client, charge(test_user, "ref_cycle_2"))
    await send(client, invoice("2026-10-08T00:00:00.000Z"))

    user, sub = await read(session_factory, test_user.id)
    assert user.plan == "pro", "renewal must not interrupt access"
    assert sub.current_period_end.month == 10, "renewal date must roll forward"
    assert sub.status == "active"


async def test_failed_renewal_keeps_access_then_recovers(
    client, billing_settings, test_user, session_factory
):
    """Paystack retries a failed renewal — don't cut access off mid-retry."""
    await subscribe(client, test_user)

    await send(
        client,
        {
            "event": "invoice.payment_failed",
            "data": {"subscription": {"subscription_code": "SUB_1"}},
        },
    )
    user, sub = await read(session_factory, test_user.id)
    assert user.plan == "pro", "a failed charge must not instantly revoke Pro"
    assert sub.status == "past_due"

    # Retry succeeds
    await send(client, invoice("2026-10-08T00:00:00.000Z"))
    user, sub = await read(session_factory, test_user.id)
    assert sub.status == "active"
    assert user.plan == "pro"


async def test_cancelled_subscription_is_not_revived_by_an_invoice(
    client, billing_settings, test_user, session_factory
):
    """A user who cancelled is non_renewing; a stray invoice event must not
    flip them back to active and keep billing them forever."""
    await subscribe(client, test_user)
    await send(
        client,
        {"event": "subscription.not_renew", "data": {"subscription_code": "SUB_1"}},
    )

    await send(client, invoice("2026-10-08T00:00:00.000Z"))
    user, sub = await read(session_factory, test_user.id)
    assert sub.status == "non_renewing", "cancellation must survive later invoices"
    assert user.plan == "pro", "they keep Pro until the period actually ends"


async def test_expiry_downgrades_only_at_period_end(
    client, billing_settings, test_user, session_factory
):
    """subscription.disable is the single source of truth for expiry."""
    await subscribe(client, test_user)
    await send(
        client,
        {"event": "subscription.not_renew", "data": {"subscription_code": "SUB_1"}},
    )
    user, _ = await read(session_factory, test_user.id)
    assert user.plan == "pro", "still paid up until the period closes"

    await send(
        client, {"event": "subscription.disable", "data": {"subscription_code": "SUB_1"}}
    )
    user, sub = await read(session_factory, test_user.id)
    assert user.plan == "free"
    assert sub.status == "cancelled"
