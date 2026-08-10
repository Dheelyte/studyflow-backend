import hmac
import json
import logging

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from ..config import settings

from ..db.session import db_session
from ..dependencies.auth import AuthUserDep
from ..dependencies.billing import PlanCurrentUserDep
from ..rate_limit import limiter
from ..schema.billing import (
    BillingStatus,
    CheckoutRequest,
    CheckoutResponse,
    ReconcileReport,
    SubscriptionRead,
    VerifyResponse,
)
from ..services.billing import BillingServiceDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Billing"], dependencies=[Depends(db_session)])


@router.get("/billing/status", response_model=BillingStatus)
async def get_billing_status(auth_user: PlanCurrentUserDep, service: BillingServiceDep):
    return await service.status(auth_user)


@router.post("/billing/checkout", response_model=CheckoutResponse)
async def start_checkout(
    body: CheckoutRequest,
    auth_user: AuthUserDep,
    service: BillingServiceDep,
):
    return await service.checkout(auth_user, body.tier, body.interval)


@router.get("/billing/verify", response_model=VerifyResponse)
async def verify_checkout(
    auth_user: AuthUserDep,
    service: BillingServiceDep,
    # Paystack references are alphanumeric with a few separators. The pattern
    # rejects path-traversal / injection attempts before they reach the client.
    reference: str = Query(min_length=1, max_length=100, pattern=r"^[\w.=-]+$"),
):
    """Callback-page fallback in case the webhook hasn't landed yet."""
    return await service.verify(auth_user, reference)


@router.post("/billing/cancel", response_model=SubscriptionRead)
async def cancel_subscription(auth_user: AuthUserDep, service: BillingServiceDep):
    return await service.cancel(auth_user)


# Separate router: the webhook is called by Paystack, not a browser , no auth,
# and exempt from the global rate limit so webhook retries never 429 (behind
# API Gateway all callers can collapse onto one rate-limit key).
webhook_router = APIRouter(tags=["Billing"], dependencies=[Depends(db_session)])


@webhook_router.post("/billing/webhook/paystack")
@limiter.exempt
async def paystack_webhook(request: Request, service: BillingServiceDep):
    raw_body = await request.body()
    signature = request.headers.get("x-paystack-signature")
    if not service.paystack.verify_signature(raw_body, signature):
        logger.warning("Paystack webhook rejected: bad signature")
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    await service.handle_webhook(event)
    return {"status": "ok"}


@webhook_router.post("/billing/reconcile", response_model=ReconcileReport)
@limiter.exempt
async def reconcile_expired_plans(
    service: BillingServiceDep,
    x_reconcile_secret: str | None = Header(default=None),
    limit: int | None = Query(default=None, gt=0, le=1000),
):
    """Scheduled sweep for lapsed subscribers who never return.

    Called by a scheduler, not a browser, so it carries a shared secret instead
    of a session. Exempt from the rate limit for the same reason as the webhook:
    behind API Gateway every caller can collapse onto one key.
    """
    expected = settings.RECONCILE_SECRET
    # Fails closed: with no secret configured there is no way to authorise a
    # call, so the endpoint is effectively off rather than open.
    if not expected or not x_reconcile_secret or not hmac.compare_digest(
        x_reconcile_secret, expected
    ):
        logger.warning("Reconcile rejected: bad or missing secret")
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    return await service.sweep_expired_plans(limit)
