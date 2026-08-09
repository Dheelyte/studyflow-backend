"""The Paystack webhook must not be rate limited.

Behind API Gateway every webhook delivery can collapse onto a single
rate-limit key (the gateway's IP), so the global 60/minute default would start
429ing Paystack's retries and silently strand users on the free plan after a
successful charge.
"""
import hashlib
import hmac
import json

import pytest

from app.rate_limit import limiter

WEBHOOK_PATH = "/api/v1/billing/webhook/paystack"


@pytest.fixture
def live_limiter():
    """conftest disables the limiter globally; switch it back on for this test."""
    previous = limiter.enabled
    limiter.enabled = True
    limiter.reset()
    yield limiter
    limiter.enabled = previous
    limiter.reset()


async def test_webhook_survives_burst_of_deliveries(client, billing_settings, live_limiter):
    body = json.dumps({"event": "transfer.success", "data": {}}).encode()
    signature = hmac.new(b"sk_test_secret", body, hashlib.sha512).hexdigest()

    statuses = set()
    for _ in range(80):  # well past the global 60/minute default
        response = await client.post(
            WEBHOOK_PATH,
            content=body,
            headers={
                "content-type": "application/json",
                "x-paystack-signature": signature,
            },
        )
        statuses.add(response.status_code)

    assert 429 not in statuses, f"webhook was rate limited; saw {sorted(statuses)}"
    assert statuses == {200}


async def test_normal_routes_are_still_rate_limited(client, live_limiter):
    """Sanity check: the exemption is specific to the webhook, not global."""
    statuses = [(await client.get("/api/v1/billing/status")).status_code for _ in range(80)]
    assert 429 in statuses, "global rate limit is not active at all — exemption test is vacuous"


async def test_reconcile_endpoint_is_also_exempt(client, live_limiter, monkeypatch):
    """The sweep shares the webhook's router and the same API Gateway
    rate-limit-key problem, so it must be exempt too."""
    from app.config import settings

    monkeypatch.setattr(settings, "RECONCILE_SECRET", "sweep-token")

    statuses = set()
    for _ in range(80):
        response = await client.post(
            "/api/v1/billing/reconcile",
            headers={"x-reconcile-secret": "sweep-token"},
        )
        statuses.add(response.status_code)

    assert 429 not in statuses, f"reconcile was rate limited; saw {sorted(statuses)}"
