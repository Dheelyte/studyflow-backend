"""Paystack sends the plan in several different shapes.

A real subscription payment crashed `verify` with
`AttributeError: 'str' object has no attribute 'get'` because the code assumed
the webhook's object shape everywhere, while transaction/verify returns a bare
plan-code string. These pin every shape we've actually observed.
"""
import pytest

from app.services.billing import _extract_plan_code


@pytest.mark.parametrize(
    "payload,expected,shape",
    [
        ({"plan": "PLN_abc123"}, "PLN_abc123", "transaction/verify: bare string"),
        ({"plan": {"plan_code": "PLN_abc123"}}, "PLN_abc123", "charge.success: nested object"),
        ({"plan_code": "PLN_abc123"}, "PLN_abc123", "top-level plan_code"),
        ({"plan": "", "plan_code": "PLN_abc123"}, "PLN_abc123", "empty plan, falls back"),
        ({"plan": {}, "plan_code": "PLN_abc123"}, "PLN_abc123", "empty object, falls back"),
        ({"plan": "  PLN_abc123  "}, "PLN_abc123", "whitespace trimmed"),
    ],
)
def test_extracts_plan_code_from_every_shape(payload, expected, shape):
    assert _extract_plan_code(payload) == expected, shape


@pytest.mark.parametrize(
    "payload,shape",
    [
        ({}, "no plan key at all"),
        ({"plan": ""}, "one-off charge: empty string"),
        ({"plan": {}}, "one-off charge: empty object"),
        ({"plan": None}, "explicit null"),
        ({"plan": 12345}, "unexpected numeric id"),
        ({"plan": ["PLN_abc"]}, "unexpected list"),
    ],
)
def test_returns_empty_rather_than_raising(payload, shape):
    """An unrecognised shape must degrade to "no plan", never throw — a crash
    here 500s the callback page after the customer has already paid."""
    assert _extract_plan_code(payload) == "", shape


async def test_verify_survives_string_plan_end_to_end(
    client, billing_settings, paystack_mock, test_user, session_factory
):
    """The exact production scenario: a successful subscription payment whose
    verify response carries `plan` as a string."""
    from sqlalchemy import select

    from app.models.user import User

    response = await client.get("/api/v1/billing/verify?reference=ref_live")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "plan": "pro"}

    async with session_factory() as session:
        user = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
        assert user.plan == "pro"


async def test_charge_success_webhook_survives_string_plan(
    client, billing_settings, test_user, session_factory
):
    """The webhook is the primary activation path — it must tolerate the string
    shape too, otherwise a paying customer silently stays on free."""
    import hashlib
    import hmac
    import json

    from sqlalchemy import select

    from app.models.user import User

    event = {
        "event": "charge.success",
        "data": {
            "reference": "ref_str_plan",
            "amount": 450000,
            "currency": "NGN",
            "status": "success",
            "metadata": {"user_id": str(test_user.id)},
            "customer": {"email": test_user.email, "customer_code": "CUS_1"},
            "plan": "PLN_pro_m",  # string, not object
        },
    }
    body = json.dumps(event).encode()
    signature = hmac.new(b"sk_test_secret", body, hashlib.sha512).hexdigest()

    response = await client.post(
        "/api/v1/billing/webhook/paystack",
        content=body,
        headers={"content-type": "application/json", "x-paystack-signature": signature},
    )
    assert response.status_code == 200

    async with session_factory() as session:
        user = (await session.execute(select(User).where(User.id == test_user.id))).scalar_one()
        assert user.plan == "pro"
