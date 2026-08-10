import pytest
from sqlalchemy import select

from app.models.billing import Subscription
from app.models.user import User




async def test_checkout_disabled_without_flag(client, test_user):
    response = await client.post(
        "/api/v1/billing/checkout", json={"tier": "pro", "interval": "monthly"}
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "tier,interval,expected_code",
    [
        ("pro", "monthly", "PLN_pro_m"),
        ("pro", "annual", "PLN_pro_y"),
        ("max", "monthly", "PLN_max_m"),
        ("max", "annual", "PLN_max_y"),
    ],
)
async def test_checkout_uses_right_plan_code(
    client, billing_settings, paystack_mock, test_user, tier, interval, expected_code
):
    response = await client.post(
        "/api/v1/billing/checkout", json={"tier": tier, "interval": interval}
    )
    assert response.status_code == 200
    assert response.json()["authorization_url"].startswith("https://checkout.paystack.com")
    assert paystack_mock["initialize"][-1]["plan_code"] == expected_code
    assert paystack_mock["initialize"][-1]["metadata"] == {"user_id": str(test_user.id)}


async def test_checkout_sends_the_plans_amount(
    client, billing_settings, paystack_mock, test_user
):
    """Regression: Paystack rejects initialize with "Invalid Amount Sent" unless a
    non-zero amount is supplied, even though the plan code overrides it."""
    response = await client.post(
        "/api/v1/billing/checkout", json={"tier": "pro", "interval": "monthly"}
    )
    assert response.status_code == 200

    sent = paystack_mock["initialize"][-1]["amount_kobo"]
    assert isinstance(sent, int) and sent > 0
    # ₦4,500 == 450000 kobo, read from the plan rather than hardcoded here.
    assert sent == 450000
    assert paystack_mock["fetch_plan"] == ["PLN_pro_m"]


async def test_checkout_fails_clearly_when_plan_code_is_wrong(
    client, billing_settings, paystack_mock, test_user, monkeypatch
):
    """Guards the test-codes-in-live mistake: an unknown plan code must fail at
    checkout, not after the customer has been charged."""
    from app.config import settings

    monkeypatch.setattr(settings, "PAYSTACK_PLAN_CODE_PRO_MONTHLY", "PLN_from_test_mode")

    response = await client.post(
        "/api/v1/billing/checkout", json={"tier": "pro", "interval": "monthly"}
    )
    assert response.status_code == 400
    assert paystack_mock["initialize"] == []  # never reached Paystack checkout


async def test_checkout_rejects_unknown_tier(client, billing_settings, paystack_mock, test_user):
    response = await client.post(
        "/api/v1/billing/checkout", json={"tier": "platinum", "interval": "monthly"}
    )
    assert response.status_code == 400


async def test_verify_activates_tier(client, billing_settings, paystack_mock, test_user, session_factory):
    response = await client.get("/api/v1/billing/verify?reference=ref_abc")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "plan": "pro"}

    from app.models.user import User

    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.id == test_user.id))
        ).scalar_one()
        assert user.plan == "pro"


async def _add_pro_sub(session_factory, user_id):
    async with session_factory() as session:
        session.add(
            Subscription(
                user_id=user_id,
                tier="pro",
                status="active",
                interval="monthly",
                paystack_plan_code="PLN_pro_m",
                paystack_subscription_code="SUB_pro",
                paystack_email_token="tok_pro",
            )
        )
        await session.commit()


async def test_checkout_does_not_touch_current_subscription(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    """C2: winding down before payment let an abandoned checkout kill a paying
    customer. Checkout must leave the existing subscription alone."""
    await _add_pro_sub(session_factory, test_user.id)

    response = await client.post(
        "/api/v1/billing/checkout", json={"tier": "max", "interval": "monthly"}
    )
    assert response.status_code == 200
    assert paystack_mock["disable"] == [], "checkout must not disable anything"

    async with session_factory() as session:
        sub = (
            await session.execute(
                select(Subscription).where(Subscription.paystack_subscription_code == "SUB_pro")
            )
        ).scalar_one()
        assert sub.status == "active", "old plan stays live until the new one is paid"


async def test_old_subscription_disabled_once_new_tier_is_paid(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    """The tier switch completes on confirmed payment (charge.success), not at
    checkout."""
    await _add_pro_sub(session_factory, test_user.id)
    paystack_mock["subscription_state"]  # ensure fixture active

    event = {
        "event": "charge.success",
        "data": {
            "reference": "ref_upgrade",
            "amount": 1000000,
            "currency": "NGN",
            "status": "success",
            "metadata": {"user_id": str(test_user.id)},
            "customer": {"email": test_user.email, "customer_code": "CUS_1"},
            "plan": {"plan_code": "PLN_max_m"},
        },
    }
    import hashlib
    import hmac
    import json

    body = json.dumps(event).encode()
    sig = hmac.new(b"sk_test_secret", body, hashlib.sha512).hexdigest()
    response = await client.post(
        "/api/v1/billing/webhook/paystack",
        content=body,
        headers={"content-type": "application/json", "x-paystack-signature": sig},
    )
    assert response.status_code == 200
    assert paystack_mock["disable"] == [{"code": "SUB_pro", "token": "tok_pro"}]

    async with session_factory() as session:
        old = (
            await session.execute(
                select(Subscription).where(Subscription.paystack_subscription_code == "SUB_pro")
            )
        ).scalar_one()
        assert old.status == "non_renewing"
        user = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
        assert user.plan == "max"


async def test_cancel_uses_stored_token(client, billing_settings, paystack_mock, test_user, session_factory):
    async with session_factory() as session:
        session.add(
            Subscription(
                user_id=test_user.id,
                tier="pro",
                status="active",
                interval="monthly",
                paystack_plan_code="PLN_pro_m",
                paystack_subscription_code="SUB_pro",
                paystack_email_token="tok_pro",
            )
        )
        await session.commit()

    response = await client.post("/api/v1/billing/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "non_renewing"
    assert paystack_mock["disable"] == [{"code": "SUB_pro", "token": "tok_pro"}]


async def test_cancel_without_subscription_404(client, billing_settings, test_user):
    response = await client.post("/api/v1/billing/cancel")
    assert response.status_code == 404
