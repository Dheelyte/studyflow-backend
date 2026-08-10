import hashlib
import hmac
import logging
from urllib.parse import quote

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

PAYSTACK_BASE_URL = "https://api.paystack.co"


class PaystackError(Exception):
    pass


class PaystackClient:
    """Thin async wrapper over the Paystack REST API.

    A fresh httpx.AsyncClient is opened per call: under Lambda, Mangum runs each
    invocation on its own event loop, so a shared client would go stale (same
    trap documented for the LLM client in config.py).
    """

    def __init__(self, secret_key: str | None = None):
        self.secret_key = secret_key or settings.PAYSTACK_SECRET_KEY

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, json: dict | None = None, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(base_url=PAYSTACK_BASE_URL, timeout=30.0) as client:
            response = await client.request(
                method, path, headers=self._headers, json=json, params=params
            )
        try:
            body = response.json()
        except ValueError:
            raise PaystackError(f"Paystack returned non-JSON ({response.status_code})")
        if response.status_code >= 400 or not body.get("status", False):
            message = body.get("message", "Unknown Paystack error")
            logger.error("Paystack %s %s failed: %s", method, path, message)
            raise PaystackError(message)
        return body.get("data", {})

    async def fetch_plan(self, plan_code: str) -> dict:
        # quote() every value interpolated into a path: these come from user
        # input / external payloads, and a value like "../subscription" would
        # otherwise steer our key-bearing client to a different endpoint.
        return await self._request("GET", f"/plan/{quote(plan_code, safe='')}")

    async def initialize_transaction(
        self,
        email: str,
        plan_code: str,
        amount_kobo: int,
        callback_url: str,
        metadata: dict | None = None,
    ) -> dict:
        """Start a checkout for a subscription plan. Paystack creates the
        subscription itself on the first successful charge.

        `amount` is required even though `plan` overrides it — omitting it (or
        sending zero) is rejected with "Invalid Amount Sent". We pass the plan's
        own amount so the value we send always agrees with what gets charged.
        """
        return await self._request(
            "POST",
            "/transaction/initialize",
            json={
                "email": email,
                "plan": plan_code,
                "amount": amount_kobo,
                "callback_url": callback_url,
                "metadata": metadata or {},
            },
        )

    async def verify_transaction(self, reference: str) -> dict:
        return await self._request(
            "GET", f"/transaction/verify/{quote(reference, safe='')}"
        )

    async def disable_subscription(self, subscription_code: str, email_token: str) -> dict:
        return await self._request(
            "POST",
            "/subscription/disable",
            json={"code": subscription_code, "token": email_token},
        )

    async def fetch_subscription(self, subscription_code: str) -> dict:
        return await self._request(
            "GET", f"/subscription/{quote(subscription_code, safe='')}"
        )

    async def list_subscriptions_for_customer(self, customer_id: int | str) -> list[dict]:
        data = await self._request("GET", "/subscription", params={"customer": customer_id})
        return data if isinstance(data, list) else []

    def verify_signature(self, raw_body: bytes, signature: str | None) -> bool:
        """Paystack signs the raw request body with HMAC-SHA512 of the secret key."""
        if not signature or not self.secret_key:
            return False
        expected = hmac.new(
            self.secret_key.encode("utf-8"), raw_body, hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
