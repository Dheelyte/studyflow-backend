import pytest
from sqlalchemy import select

from app.models.billing import Subscription
from app.services.paystack import PaystackClient, PaystackError


@pytest.fixture
def paystack_mock(monkeypatch):
    """Record Paystack API calls instead of hitting the network."""
    calls = {"initialize": [], "disable": [], "verify": [], "fetch_plan": []}

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

    async def verify_transaction(self, reference):
        calls["verify"].append(reference)
        return {
            "status": "success",
            "reference": reference,
            "amount": 450000,
            "currency": "NGN",
            "paid_at": "2026-08-01T10:00:00.000Z",
            "customer": {"customer_code": "CUS_1"},
            "plan": {"plan_code": "PLN_pro_m"},
        }

    monkeypatch.setattr(PaystackClient, "fetch_plan", fetch_plan)
    monkeypatch.setattr(PaystackClient, "initialize_transaction", initialize_transaction)
    monkeypatch.setattr(PaystackClient, "disable_subscription", disable_subscription)
    monkeypatch.setattr(PaystackClient, "verify_transaction", verify_transaction)
    return calls


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


async def test_upgrade_disables_old_subscription_first(
    client, billing_settings, paystack_mock, test_user, session_factory
):
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

    response = await client.post(
        "/api/v1/billing/checkout", json={"tier": "max", "interval": "monthly"}
    )
    assert response.status_code == 200
    assert paystack_mock["disable"] == [{"code": "SUB_pro", "token": "tok_pro"}]

    async with session_factory() as session:
        sub = (
            await session.execute(
                select(Subscription).where(Subscription.paystack_subscription_code == "SUB_pro")
            )
        ).scalar_one()
        assert sub.status == "non_renewing"


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
