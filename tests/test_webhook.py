import hashlib
import hmac
import json

from sqlalchemy import select

from app.models.billing import PaymentTransaction, Subscription
from app.models.user import User

WEBHOOK_PATH = "/api/v1/billing/webhook/paystack"


def sign(body: bytes, secret: str = "sk_test_secret") -> str:
    return hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()


def charge_success_event(user, reference="ref_001", plan_code="PLN_pro_m"):
    return {
        "event": "charge.success",
        "data": {
            "reference": reference,
            "amount": 450000,
            "currency": "NGN",
            "status": "success",
            "paid_at": "2026-08-01T10:00:00.000Z",
            "metadata": {"user_id": str(user.id)},
            "customer": {"email": user.email, "customer_code": "CUS_1"},
            "plan": {"plan_code": plan_code},
        },
    }


async def post_event(client, event, secret="sk_test_secret"):
    body = json.dumps(event).encode()
    return await client.post(
        WEBHOOK_PATH,
        content=body,
        headers={
            "content-type": "application/json",
            "x-paystack-signature": sign(body, secret),
        },
    )


async def get_user(session_factory, user_id):
    async with session_factory() as session:
        return (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one()


async def test_webhook_rejects_bad_signature(client, billing_settings, test_user):
    body = json.dumps(charge_success_event(test_user)).encode()
    response = await client.post(
        WEBHOOK_PATH,
        content=body,
        headers={"content-type": "application/json", "x-paystack-signature": "tampered"},
    )
    assert response.status_code == 401


async def test_webhook_missing_signature(client, billing_settings, test_user):
    response = await client.post(
        WEBHOOK_PATH,
        content=json.dumps(charge_success_event(test_user)),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 401


async def test_charge_success_activates_pro(client, billing_settings, test_user, session_factory):
    response = await post_event(client, charge_success_event(test_user))
    assert response.status_code == 200

    user = await get_user(session_factory, test_user.id)
    assert user.plan == "pro"

    async with session_factory() as session:
        txn = (
            await session.execute(
                select(PaymentTransaction).where(PaymentTransaction.reference == "ref_001")
            )
        ).scalar_one()
        assert txn.amount_kobo == 450000


async def test_charge_success_max_plan_code(client, billing_settings, test_user, session_factory):
    await post_event(client, charge_success_event(test_user, plan_code="PLN_max_y"))
    user = await get_user(session_factory, test_user.id)
    assert user.plan == "max"


async def test_charge_success_idempotent_on_duplicate_reference(
    client, billing_settings, test_user, session_factory
):
    await post_event(client, charge_success_event(test_user))
    await post_event(client, charge_success_event(test_user))

    async with session_factory() as session:
        txns = (
            await session.execute(
                select(PaymentTransaction).where(PaymentTransaction.reference == "ref_001")
            )
        ).scalars().all()
        assert len(txns) == 1


async def test_unknown_plan_code_ignored(client, billing_settings, test_user, session_factory):
    await post_event(client, charge_success_event(test_user, plan_code="PLN_other"))
    user = await get_user(session_factory, test_user.id)
    assert user.plan == "free"


async def test_unknown_event_returns_200(client, billing_settings, test_user):
    response = await post_event(client, {"event": "transfer.success", "data": {}})
    assert response.status_code == 200


async def test_subscription_create_then_disable(client, billing_settings, test_user, session_factory):
    await post_event(client, charge_success_event(test_user))

    create_event = {
        "event": "subscription.create",
        "data": {
            "subscription_code": "SUB_1",
            "email_token": "tok_1",
            "next_payment_date": "2026-09-01T00:00:00.000Z",
            "customer": {"email": test_user.email, "customer_code": "CUS_1"},
            "plan": {"plan_code": "PLN_pro_m"},
        },
    }
    await post_event(client, create_event)

    async with session_factory() as session:
        sub = (
            await session.execute(
                select(Subscription).where(Subscription.paystack_subscription_code == "SUB_1")
            )
        ).scalar_one()
        assert sub.status == "active"
        assert sub.paystack_email_token == "tok_1"
        assert sub.current_period_end is not None

    disable_event = {
        "event": "subscription.disable",
        "data": {"subscription_code": "SUB_1"},
    }
    await post_event(client, disable_event)

    user = await get_user(session_factory, test_user.id)
    assert user.plan == "free"
    async with session_factory() as session:
        sub = (
            await session.execute(
                select(Subscription).where(Subscription.paystack_subscription_code == "SUB_1")
            )
        ).scalar_one()
        assert sub.status == "cancelled"


async def test_disable_keeps_paid_tier_during_switch(
    client, billing_settings, test_user, session_factory
):
    """Pro→Max switch: disabling the old Pro sub must not downgrade a user whose
    Max subscription is live."""
    await post_event(client, charge_success_event(test_user, reference="r1", plan_code="PLN_pro_m"))
    await post_event(
        client,
        {
            "event": "subscription.create",
            "data": {
                "subscription_code": "SUB_pro",
                "email_token": "tok_pro",
                "customer": {"email": test_user.email},
                "plan": {"plan_code": "PLN_pro_m"},
            },
        },
    )
    # New Max subscription arrives
    await post_event(client, charge_success_event(test_user, reference="r2", plan_code="PLN_max_m"))
    await post_event(
        client,
        {
            "event": "subscription.create",
            "data": {
                "subscription_code": "SUB_max",
                "email_token": "tok_max",
                "customer": {"email": test_user.email},
                "plan": {"plan_code": "PLN_max_m"},
            },
        },
    )
    # Old Pro subscription finally dies at period end
    await post_event(client, {"event": "subscription.disable", "data": {"subscription_code": "SUB_pro"}})

    user = await get_user(session_factory, test_user.id)
    assert user.plan == "max"


async def test_resolves_user_by_email_fallback(client, billing_settings, test_user, session_factory):
    event = charge_success_event(test_user)
    event["data"]["metadata"] = {}
    await post_event(client, event)
    user = await get_user(session_factory, test_user.id)
    assert user.plan == "pro"
