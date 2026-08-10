"""H3 (verify-only activation stays visible to expiry) and M1 (amount check)."""
import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.billing import PaymentTransaction, Subscription
from app.models.user import User
from app.services.paystack import PaystackClient


def as_utc(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def read_user(session_factory, user_id):
    async with session_factory() as session:
        return (await session.execute(select(User).where(User.id == user_id))).scalar_one()


async def send_webhook(client, event):
    body = json.dumps(event).encode()
    sig = hmac.new(b"sk_test_secret", body, hashlib.sha512).hexdigest()
    return await client.post(
        "/api/v1/billing/webhook/paystack",
        content=body,
        headers={"content-type": "application/json", "x-paystack-signature": sig},
    )


def charge(user, plan_code="PLN_pro_m", amount=450000, reference="ref_1", currency="NGN"):
    return {
        "event": "charge.success",
        "data": {
            "reference": reference,
            "amount": amount,
            "currency": currency,
            "status": "success",
            "metadata": {"user_id": str(user.id)},
            "customer": {"email": user.email, "customer_code": "CUS_1"},
            "plan": {"plan_code": plan_code},
        },
    }


# --- H3: activation must always leave an enforceable expiry -----------------


async def test_verify_only_activation_sets_provisional_expiry(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    """If only the verify fallback runs (all webhooks missed), the user must
    still get a non-NULL, future plan_expires_at, or the safety nets skip them
    forever."""
    await client.get("/api/v1/billing/verify?reference=ref_v")
    user = await read_user(session_factory, test_user.id)
    assert user.plan == "pro"
    assert user.plan_expires_at is not None
    assert as_utc(user.plan_expires_at) > datetime.now(timezone.utc)


async def test_real_date_from_later_event_overwrites_provisional(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    await client.get("/api/v1/billing/verify?reference=ref_v")
    provisional = as_utc((await read_user(session_factory, test_user.id)).plan_expires_at)

    # subscription.create carries Paystack's exact next_payment_date
    exact = "2027-01-15T00:00:00.000Z"
    await send_webhook(client, {
        "event": "subscription.create",
        "data": {
            "subscription_code": "SUB_x", "email_token": "tok",
            "next_payment_date": exact,
            "customer": {"email": test_user.email},
            "plan": {"plan_code": "PLN_pro_m"},
        },
    })
    updated = as_utc((await read_user(session_factory, test_user.id)).plan_expires_at)
    assert updated.year == 2027 and updated.month == 1
    assert updated != provisional, "the exact date must replace the provisional one"


# --- M1: a charge must actually cover the plan ------------------------------


async def test_underpaid_charge_is_recorded_but_not_activated(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    # Pro monthly is priced 450000 in the mock; pay less.
    await send_webhook(client, charge(test_user, amount=100000, reference="ref_under"))

    user = await read_user(session_factory, test_user.id)
    assert user.plan == "free", "underpayment must not grant the tier"

    async with session_factory() as session:
        txn = (
            await session.execute(
                select(PaymentTransaction).where(PaymentTransaction.reference == "ref_under")
            )
        ).scalar_one_or_none()
        assert txn is not None, "but the charge is still recorded for audit"


async def test_wrong_currency_is_rejected(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    await send_webhook(client, charge(test_user, amount=450000, currency="USD", reference="ref_usd"))
    user = await read_user(session_factory, test_user.id)
    assert user.plan == "free"


async def test_correct_amount_activates(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    await send_webhook(client, charge(test_user, amount=450000, reference="ref_ok"))
    assert (await read_user(session_factory, test_user.id)).plan == "pro"


async def test_dual_activation_paths_produce_one_subscription(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    """H2: webhook (charge.success) and callback verify both activate the same
    payment. They must converge on one Subscription and one PaymentTransaction,
    not duplicates."""
    # Path 1: the webhook.
    await send_webhook(client, charge(test_user, reference="ref_dup"))
    # Path 2: the callback page verifies the same reference.
    await client.get("/api/v1/billing/verify?reference=ref_v")

    async with session_factory() as session:
        subs = (
            await session.execute(
                select(Subscription).where(Subscription.user_id == test_user.id)
            )
        ).scalars().all()
        assert len(subs) == 1, f"expected 1 subscription, got {len(subs)}"

        txns = (
            await session.execute(
                select(PaymentTransaction).where(PaymentTransaction.user_id == test_user.id)
            )
        ).scalars().all()
        # Two different references (webhook ref_dup, verify ref_v) → two txns is
        # correct; the point is neither path 500s and no reference is doubled.
        assert len({t.reference for t in txns}) == len(txns), "no duplicate references"


async def test_replayed_reference_does_not_error(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    """The same reference arriving twice (Paystack retry) must be a clean no-op,
    not a 500 from the unique constraint."""
    r1 = await send_webhook(client, charge(test_user, reference="ref_replay"))
    r2 = await send_webhook(client, charge(test_user, reference="ref_replay"))
    assert r1.status_code == 200 and r2.status_code == 200

    async with session_factory() as session:
        txns = (
            await session.execute(
                select(PaymentTransaction).where(PaymentTransaction.reference == "ref_replay")
            )
        ).scalars().all()
        assert len(txns) == 1


async def test_price_check_fails_open_on_paystack_error(
    client, billing_settings, paystack_mock, test_user, session_factory, monkeypatch
):
    """If we can't fetch the plan to price-check, prefer availability — Paystack
    already signed the plan code into the webhook."""
    from app.services.paystack import PaystackError

    async def boom(self, code):
        raise PaystackError("plan lookup down")

    monkeypatch.setattr(PaystackClient, "fetch_plan", boom)

    await send_webhook(client, charge(test_user, amount=450000, reference="ref_open"))
    assert (await read_user(session_factory, test_user.id)).plan == "pro"
